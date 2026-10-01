#!/usr/bin/env python3
"""TREC pooling + LLM-as-a-Judge로 Recall/nDCG 평가용 Ground Truth를 만든다.

절차:
  1. 토픽(소스 폴더)별 층화 샘플링으로 기준 청크를 고른다.
  2. 청크마다 단일 키워드/복합 키워드/자연어 질문 3종 쿼리를 LLM으로 생성한다.
  3. 각 쿼리로 키워드·벡터·하이브리드 검색을 top-N씩 돌려 후보를 union한다 (TREC pooling).
  4. 후보 전체를 LLM이 0~3점(Irrelevant/Marginal/Relevant/Perfect)으로 채점한다.
  5. 2점 이상을 reference_chunk_ids로, 채점 전체를 graded_relevance로 저장한다.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import psycopg
from elasticsearch import Elasticsearch


SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from common import LAB_ROOT, get_env, load_documents, read_local_setting
from retrieval.hybrid.search import hybrid_search
from retrieval.keyword.search import search_documents as keyword_search
from retrieval.vector.search import search_documents as vector_search


API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4.1-mini"
OUTPUT_PATH = LAB_ROOT / "data" / "evaluation" / "questions_pooled.jsonl"

QUERY_TYPES = ["single_keyword", "compound_keyword", "natural_language"]
QUERY_TYPE_CODE = {"single_keyword": "kw", "compound_keyword": "ck", "natural_language": "nl"}

QUERY_GEN_INSTRUCTIONS = """당신은 검색 평가용 쿼리를 만드는 도우미입니다.
주어진 문서 조각 하나를 바탕으로, 이 문서를 찾아낼 수 있는 검색 쿼리 3개를 서로 다른 스타일로 만드세요.

- single_keyword: 검색창에 칠 법한 단일 키워드나 짧은 구
- compound_keyword: 키워드 2~3개를 조합한 구
- natural_language: 실제 사용자가 물어볼 법한 자연어 질문

문서에 없는 사실을 지어내지 말고, 문서 내용에 실제로 등장하는 용어를 최대한 활용하세요.
JSON만 출력하세요: {"single_keyword": "...", "compound_keyword": "...", "natural_language": "..."}"""

JUDGE_INSTRUCTIONS = """당신은 검색 결과의 관련도를 평가하는 심사자입니다.
주어진 검색 쿼리에 대해, 후보 문서 조각들이 얼마나 관련 있는지 0~3점으로 채점하세요.

0 = Irrelevant: 쿼리와 무관
1 = Marginal: 쿼리 주제와 약하게만 관련
2 = Relevant: 쿼리에 실제로 답하거나 직접 관련된 정보를 담음
3 = Perfect: 쿼리에 가장 정확하고 완전하게 답함

모든 후보에 대해 점수를 매기고, JSON 배열만 출력하세요: [{"id": "청크ID", "score": 0}, ...]"""


def topic_group(source: str) -> str:
    parts = source.split("/")
    return parts[1] if len(parts) > 2 else "(root)"


def stratified_sample(documents: list[dict], per_group: int, seed: int) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for document in documents:
        groups.setdefault(topic_group(document["source"]), []).append(document)

    rng = random.Random(seed)
    sampled: list[dict] = []
    for group in sorted(groups):
        pool = groups[group]
        sampled.extend(rng.sample(pool, min(per_group, len(pool))))
    return sampled


def _extract_text(payload: dict) -> str:
    parts = [
        part["text"]
        for item in payload.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") == "output_text" and part.get("text")
    ]
    text = "\n".join(parts).strip()
    if not text:
        raise RuntimeError("OpenAI API가 텍스트 응답을 반환하지 않았습니다.")
    return text


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()


def call_openai_json(instructions: str, input_text: str, api_key: str, model: str, max_output_tokens: int = 2000):
    payload = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
        "max_output_tokens": max_output_tokens,
        "store": False,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        try:
            detail = json.load(error).get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detail = ""
        raise RuntimeError(f"OpenAI API 오류 ({error.code}): {detail or error.reason}") from error

    text = _strip_code_fence(_extract_text(body))
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"OpenAI 응답이 JSON이 아닙니다: {text[:200]}") from error


def generate_queries(chunk: dict, api_key: str, model: str) -> dict[str, str]:
    input_text = f"제목: {chunk['title']}\n본문:\n{chunk['content']}"
    payload = call_openai_json(QUERY_GEN_INSTRUCTIONS, input_text, api_key, model)
    missing = [query_type for query_type in QUERY_TYPES if query_type not in payload]
    if missing:
        raise RuntimeError(f"쿼리 생성 응답에 다음 항목이 없습니다: {missing}")
    return {query_type: payload[query_type] for query_type in QUERY_TYPES}


def build_candidate_pool(query: str, es_client: Elasticsearch, es_url: str, postgres, rank_window: int) -> list[dict]:
    keyword_results = keyword_search(es_client, query, rank_window)
    vector_results = vector_search(postgres, query, rank_window)
    hybrid_results = hybrid_search(es_url, postgres, query, limit=rank_window, rank_window=rank_window)

    pool: dict[str, dict] = {}
    for results in (keyword_results, vector_results, hybrid_results):
        for result in results:
            pool.setdefault(result["id"], result)
    return list(pool.values())


def judge_candidates(query: str, query_type: str, candidates: list[dict], api_key: str, model: str) -> dict[str, int]:
    if not candidates:
        return {}

    listing = "\n\n".join(
        f"id: {candidate['id']}\n제목: {candidate['title']}\n본문: {candidate['content'][:400]}"
        for candidate in candidates
    )
    input_text = f"쿼리 유형: {query_type}\n쿼리: {query}\n\n후보 목록:\n{listing}"
    payload = call_openai_json(JUDGE_INSTRUCTIONS, input_text, api_key, model)

    known_ids = {candidate["id"] for candidate in candidates}
    scores = {item["id"]: int(item["score"]) for item in payload}
    unknown = set(scores) - known_ids
    if unknown:
        print(f"    경고: 채점 응답에 후보에 없는 id가 있어 무시합니다: {sorted(unknown)}")
        scores = {chunk_id: score for chunk_id, score in scores.items() if chunk_id in known_ids}
    for chunk_id in known_ids - set(scores):
        scores[chunk_id] = 0

    return {chunk_id: score for chunk_id, score in scores.items() if score > 0}


def print_sampled(sampled: list[dict]) -> None:
    for chunk in sampled:
        print(f"[{topic_group(chunk['source'])}] {chunk['id']}  {chunk['title']} (chunk {chunk['chunk_index']})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="토픽별 층화 샘플링 + TREC pooling + LLM-as-a-Judge로 Ground Truth를 생성합니다."
    )
    parser.add_argument("--per-group", type=int, default=4, help="토픽 그룹별 샘플링할 청크 수")
    parser.add_argument("--seed", type=int, default=42, help="샘플링 난수 시드")
    parser.add_argument("--rank-window", type=int, default=20, help="TREC pooling 후보 범위 (검색 방식당)")
    parser.add_argument("--model", help="OpenAI 모델; 기본값 gpt-4.1-mini")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="결과를 저장할 JSONL 경로")
    parser.add_argument("--dry-run", action="store_true", help="OpenAI를 호출하지 않고 샘플링 결과만 확인")
    args = parser.parse_args()

    if args.per_group <= 0:
        raise SystemExit("--per-group은 1 이상이어야 합니다.")

    documents = load_documents()
    sampled = stratified_sample(documents, args.per_group, args.seed)
    groups = sorted({topic_group(chunk["source"]) for chunk in sampled})
    print(f"{len(sampled)}개 청크를 샘플링했습니다 ({', '.join(groups)}).")

    if args.dry_run:
        print_sampled(sampled)
        return

    api_key = read_local_setting("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY가 없습니다. 이 랩의 .env에 설정하세요.")
    model = args.model or read_local_setting("OPENAI_MODEL", DEFAULT_MODEL)

    es_url = get_env("ES_URL", "http://localhost:9200")
    dsn = get_env("POSTGRES_DSN", "postgresql://study:study@localhost:5432/personal_data")
    es_client = Elasticsearch(es_url)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with psycopg.connect(dsn) as postgres, args.output.open("w", encoding="utf-8") as stream:
        for chunk in sampled:
            queries = generate_queries(chunk, api_key, model)
            for query_type in QUERY_TYPES:
                query_text = queries[query_type]
                candidates = build_candidate_pool(query_text, es_client, es_url, postgres, args.rank_window)
                judgments = judge_candidates(query_text, query_type, candidates, api_key, model)
                reference_ids = sorted(chunk_id for chunk_id, score in judgments.items() if score >= 2)

                if not reference_ids:
                    print(f"  [{query_type}] 경고: 정답 후보가 없어 건너뜁니다 — {query_text!r}")
                    continue

                context_ids = sorted(chunk_id for chunk_id, score in judgments.items() if score == 1)
                question = {
                    "id": f"{chunk['id'][:8]}-{QUERY_TYPE_CODE[query_type]}",
                    "source_chunk_id": chunk["id"],
                    "query_type": query_type,
                    "question": query_text,
                    "reference_chunk_ids": reference_ids,
                    "context_chunk_ids": context_ids,
                    "graded_relevance": judgments,
                }
                # 실패 시에도 이미 채점한 질문은 남도록 쿼리마다 바로 기록한다.
                stream.write(json.dumps(question, ensure_ascii=False) + "\n")
                stream.flush()
                written += 1
                print(
                    f"  [{query_type}] {query_text!r} "
                    f"-> 후보 {len(candidates)}개 중 정답 {len(reference_ids)}개"
                )

    print(f"{written}개 질문을 {args.output}에 저장했습니다.")


if __name__ == "__main__":
    main()
