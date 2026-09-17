#!/usr/bin/env python3
"""에이전틱 검색: 근거가 부족하면 LLM이 다음 검색어를 만들어 재검색한다.

일반 RAG(chat.py)는 질문 한 번으로 검색을 끝내기 때문에, 서로 다른 문서를
조인해야 답이 나오는 멀티홉 질문에서 실패한다(failed_questions.md 1번 사례).
여기서는 매 홉마다 LLM에게 "지금 근거로 답할 수 있는지"를 먼저 판단시키고,
부족하면 다음에 검색할 질의를 LLM이 직접 만들어 재검색하게 한다.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import common_path  # noqa: F401
from chat import build_context, print_sources
from hybrid_search import load_chunk_lookup, search_hybrid
from index_es import DEFAULT_INDEX
from index_pgvector import DEFAULT_DSN
from prompts import AGENTIC_SYSTEM_PROMPT, DECOMPOSE_SYSTEM_PROMPT
from search_common.elasticsearch import DEFAULT_ES_URL
from search_common.embeddings import DEFAULT_MODEL, DEFAULT_OLLAMA_URL
from search_common.llm import DEFAULT_CHAT_MODEL, chat

try:
    import psycopg
except ImportError as error:
    raise SystemExit("pgvector 단계는 `pip install -r requirements.txt`가 필요합니다.") from error


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_TRACE_DIR = ROOT / "data" / "do-dop" / "company-analysis-kg" / "traces"


def parse_action(response: str) -> tuple[str, str]:
    text = response.strip()
    match = re.match(r"(?is)^search\s*:\s*(.+)", text)
    if match:
        return "search", match.group(1).strip().splitlines()[0].strip()
    match = re.match(r"(?is)^answer\s*:\s*(.+)", text)
    if match:
        return "answer", match.group(1).strip()
    return "answer", text  # 형식을 안 지키면 그대로 최종 답변 취급


def decompose_query(question: str, chat_model: str, ollama_url: str) -> list[str]:
    response = chat(
        [
            {"role": "system", "content": DECOMPOSE_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        model=chat_model, ollama_url=ollama_url,
    )
    sub_queries = [line.strip("-* \t") for line in response.strip().splitlines() if line.strip()]
    return sub_queries or [question]


def run_agentic_search(
    conn,
    question: str,
    chunk_lookup: dict[str, dict],
    *,
    es_url: str,
    index: str,
    embed_model: str,
    chat_model: str,
    ollama_url: str,
    size: int,
    max_hops: int,
    decompose: bool = False,
    verbose: bool = False,
) -> tuple[str, list[dict], list[str], list[dict]]:
    """에이전트의 답변과 함께, 판단 과정을 그대로 기록한 trace를 반환한다.

    trace의 각 원소는 {"type": ...}을 가진 딕셔너리다. "search"는 어떤 질의로 검색해서
    어떤 청크를 새로 얻었는지, "judge"는 LLM이 그 시점에 SEARCH/ANSWER 중 뭘 골랐는지와
    원문 응답을 그대로 담는다 — 나중에 "왜 이렇게 답했는지"를 그대로 재구성할 수 있게 하기 위함이다.
    """
    seen_ids: set[str] = set()
    chunks: list[dict] = []
    queries_tried = [question]
    trace: list[dict] = []

    if decompose:
        sub_queries = decompose_query(question, chat_model, ollama_url)
        trace.append({"type": "decompose", "sub_queries": sub_queries})
        if verbose:
            print(f"[분해] {len(sub_queries)}개 하위 질의: {sub_queries}")
        for sub_query in sub_queries:
            sub_chunks = search_hybrid(
                conn, sub_query, chunk_lookup,
                es_url=es_url, index=index, model=embed_model, ollama_url=ollama_url, size=size,
            )
            new_ids = [chunk["id"] for chunk in sub_chunks if chunk["id"] not in seen_ids]
            for chunk in sub_chunks:
                if chunk["id"] not in seen_ids:
                    seen_ids.add(chunk["id"])
                    chunks.append(chunk)
            trace.append({"type": "search", "phase": "decompose", "query": sub_query, "new_chunk_ids": new_ids})
            if verbose:
                print(f"[분해 검색] {sub_query!r} -> 새 청크 {len(sub_chunks)}개 (누적 {len(chunks)}개)")

    for hop in range(1, max_hops + 1):
        query = queries_tried[-1]
        new_chunks = search_hybrid(
            conn, query, chunk_lookup,
            es_url=es_url, index=index, model=embed_model, ollama_url=ollama_url, size=size,
        )
        new_ids = [chunk["id"] for chunk in new_chunks if chunk["id"] not in seen_ids]
        for chunk in new_chunks:
            if chunk["id"] not in seen_ids:
                seen_ids.add(chunk["id"])
                chunks.append(chunk)
        trace.append({"type": "search", "phase": "hop", "hop": hop, "query": query, "new_chunk_ids": new_ids})
        if verbose:
            print(f"[hop {hop}] 검색어: {query!r} -> 새 청크 {len(new_chunks)}개 (누적 {len(chunks)}개)")

        user_prompt = f"[원래 질문]\n{question}\n\n[지금까지 모은 근거]\n{build_context(chunks)}"
        response = chat(
            [
                {"role": "system", "content": AGENTIC_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=chat_model, ollama_url=ollama_url,
        )
        action, payload = parse_action(response)
        trace.append({"type": "judge", "hop": hop, "raw_response": response, "action": action, "payload": payload})
        if verbose:
            print(f"[hop {hop}] 판단: {action.upper()} -> {payload}")

        if action == "answer":
            trace.append({"type": "final_answer", "answer": payload, "reason": "answered"})
            return payload, chunks, queries_tried, trace
        queries_tried.append(payload)

    # 최대 홉에 도달 -> 지금까지 모은 근거로 강제 답변
    user_prompt = (
        f"[원래 질문]\n{question}\n\n[모은 근거]\n{build_context(chunks)}\n\n"
        "더 검색할 기회는 끝났다. 위 근거만으로 ANSWER 형식으로 최종 답변해라."
    )
    response = chat(
        [
            {"role": "system", "content": AGENTIC_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model=chat_model, ollama_url=ollama_url,
    )
    _, payload = parse_action(response)
    trace.append({"type": "judge", "hop": None, "raw_response": response, "action": "forced_answer", "payload": payload})
    trace.append({"type": "final_answer", "answer": payload, "reason": "max_hops_reached"})
    return payload, chunks, queries_tried, trace


def save_trace(question: str, trace: list[dict], answer: str, output_dir: Path = DEFAULT_TRACE_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "_", question)[:30].strip("_")
    path = output_dir / f"{timestamp}_{slug}.json"
    path.write_text(
        json.dumps({"question": question, "answer": answer, "trace": trace}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--es-url", default=DEFAULT_ES_URL)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--embed-model", default=DEFAULT_MODEL)
    parser.add_argument("--chat-model", default=DEFAULT_CHAT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--size", type=int, default=5, help="검색 1회당 가져올 청크 수")
    parser.add_argument("--max-hops", type=int, default=3)
    parser.add_argument(
        "--decompose", action="store_true",
        help="첫 홉 전에 질문을 독립적인 하위 질의 여러 개로 나눠 각각 검색한다",
    )
    parser.add_argument("--verbose", action="store_true", help="중간 검색어와 판단 과정도 출력")
    parser.add_argument(
        "--no-save-trace", dest="save_trace", action="store_false",
        help="판단 과정을 JSON 파일로 남기지 않는다 (기본은 저장함)",
    )
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_TRACE_DIR)
    args = parser.parse_args()

    chunk_lookup = load_chunk_lookup()
    with psycopg.connect(args.dsn) as conn:
        answer, chunks, queries_tried, trace = run_agentic_search(
            conn, args.question, chunk_lookup,
            es_url=args.es_url, index=args.index,
            embed_model=args.embed_model, chat_model=args.chat_model, ollama_url=args.ollama_url,
            size=args.size, max_hops=args.max_hops, decompose=args.decompose, verbose=args.verbose,
        )

    if args.verbose:
        print(f"\n[검색어 이력] {queries_tried}")
    print(answer)
    print_sources(chunks)

    if args.save_trace:
        path = save_trace(args.question, trace, answer, args.trace_dir)
        print(f"\n[판단 과정 기록] {path}")


if __name__ == "__main__":
    main()
