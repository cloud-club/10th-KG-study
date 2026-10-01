#!/usr/bin/env python3
"""W2 학습용: 청크 50개를 로컬 임베딩하고 질문으로 Top-k 검색.

Python 표준 라이브러리만 사용. 기본 검색 범위는 입력 파일 앞 50개.
검색용 벡터/본문/ID를 로컬 캐시에 저장한다. DB 적재/답변 생성은 하지 않는다.
문서 입력은 기존 embedding_text 그대로, 질문만 Qwen 검색용 지시문을 붙인다.
실제 검색 품질은 사용자의 Ollama 실행 결과로 평가해야 한다.

References:
https://docs.ollama.com/api/embed
https://docs.ollama.com/api/tags
https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

BASE_DIR = Path(__file__).resolve().parent
BASE_URL = "http://127.0.0.1:11434"
MODEL = "qwen3-embedding:0.6b"
EXPECTED_DIM = 1024
TASK = "Given a question, retrieve relevant passages that answer the question"
SCHEMA = "rag-vector-search-lab-v1"
FIELDS = (
    "chunk_id", "document_id", "parent_document_id", "title", "document_path",
    "section_path", "section_index", "url_id", "raw_text", "embedding_text",
    "source_blocks", "source_span", "source_metadata", "content_hash", "chunking",
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# Fixed loopback only: no environment proxies, redirects, or remote model endpoints.
OPENER = build_opener(ProxyHandler({}), NoRedirect())


def call_api(route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(BASE_URL + route, data=data,
                      headers={"Content-Type": "application/json"},
                      method="GET" if payload is None else "POST")
    try:
        with OPENER.open(request, timeout=180) as response:
            result = json.load(response)
    except HTTPError as error:
        # Never echo a server error body: it could contain document text.
        if error.code == 404:
            hint = f"ollama list에서 {MODEL}이 있는지 확인해."
        elif error.code == 400:
            hint = "요청이 거부됐어. Ollama 로그에서 입력 길이/모델 지원 여부를 로컬로 확인해. 입력은 자동으로 자르지 않아."
        else:
            hint = "Ollama 실행 상태와 로컬 서버 로그를 확인해."
        raise RuntimeError(f"Ollama HTTP {error.code}: {hint}") from None
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"로컬 Ollama 연결/응답 오류: {error}") from None
    if not isinstance(result, dict):
        raise ValueError("Ollama 응답이 JSON 객체가 아니야.")
    return result


def model_digest() -> str:
    models = call_api("/api/tags").get("models")
    if isinstance(models, list):
        for item in models:
            if isinstance(item, dict) and MODEL in (item.get("name"), item.get("model")):
                digest = item.get("digest")
                if isinstance(digest, str) and digest:
                    return digest
    raise ValueError(f"로컬 모델 정보가 없어. 먼저 ollama pull {MODEL}을 실행해.")


def read_chunks(path: Path, limit: int) -> list[dict[str, Any]]:
    chunks, seen = [], set()
    with path.open(encoding="utf-8-sig") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                raise ValueError(f"입력 {line_no}행: 올바른 JSON이 아니야.") from None
            if not isinstance(item, dict):
                raise ValueError(f"입력 {line_no}행: JSON 객체가 필요해.")
            for key in ("chunk_id", "document_id", "raw_text", "embedding_text"):
                if not isinstance(item.get(key), str) or not item[key].strip():
                    raise ValueError(f"입력 {line_no}행: {key}가 없거나 비어 있어.")
            if item["chunk_id"] in seen:
                raise ValueError(f"입력 {line_no}행: 중복 chunk_id가 있어.")
            seen.add(item["chunk_id"])
            chunks.append({key: item[key] for key in FIELDS if key in item})
            if limit and len(chunks) >= limit:
                break
    if not chunks:
        raise ValueError("검색할 청크가 없어.")
    return chunks


def fingerprint(chunks: list[dict[str, Any]]) -> str:
    raw = json.dumps(chunks, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_vectors(vectors: Any, expected_count: int) -> list[list[float]]:
    if not isinstance(vectors, list) or len(vectors) != expected_count:
        raise ValueError("입력 청크 수와 벡터 수가 달라.")
    for vector in vectors:
        if not isinstance(vector, list) or len(vector) != EXPECTED_DIM:
            raise ValueError(f"이번 실습은 {EXPECTED_DIM}차원 벡터가 필요해.")
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in vector):
            raise ValueError("벡터에 유효하지 않은 숫자가 있어.")
        norm = math.hypot(*vector)
        if not math.isfinite(norm) or norm == 0:
            raise ValueError("벡터 크기가 0이거나 유효하지 않아.")
    return vectors


def embed_texts(texts: list[str]) -> list[list[float]]:
    result = call_api("/api/embed", {"model": MODEL, "input": texts, "truncate": False})
    return validate_vectors(result.get("embeddings"), len(texts))


def write_exclusive_json(path: Path, value: dict[str, Any]) -> None:
    """Publish a complete JSON file atomically, without replacing any existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".rag-vector-", delete=False) as stream:
            temporary = stream.name
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Fails safely if destination exists.
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def load_or_embed(chunks: list[dict[str, Any]], cache: Path,
                  digest: str, batch_size: int) -> list[list[float]]:
    expected = {"schema": SCHEMA, "model": MODEL, "model_digest": digest,
                "dimensions": EXPECTED_DIM, "truncate": False,
                "document_input": "embedding_text (unchanged)",
                "chunks_sha256": fingerprint(chunks), "count": len(chunks)}
    if cache.exists():
        with cache.open(encoding="utf-8") as stream:
            saved = json.load(stream)
        if not isinstance(saved, dict) or saved.get("settings") != expected:
            raise ValueError("캐시의 모델/입력/설정이 달라. 기존 파일은 보존하고 다른 --cache 경로를 지정해.")
        records = saved.get("records")
        if not isinstance(records, list) or len(records) != len(chunks):
            raise ValueError("캐시의 청크 수가 달라.")
        if any(not isinstance(record, dict) for record in records):
            raise ValueError("캐시 레코드 형식이 잘못됐어.")
        restored_chunks = [{k: record[k] for k in FIELDS if k in record} for record in records]
        if restored_chunks != chunks:
            raise ValueError("캐시 본문/출처와 입력 청크가 달라.")
        vectors = validate_vectors([record.get("embedding") for record in records], len(chunks))
        print(f"문서 벡터 {len(vectors)}개: 저장된 캐시 재사용", flush=True)
        return vectors

    vectors = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        vectors.extend(embed_texts([item["embedding_text"] for item in batch]))
        print(f"문서 임베딩: {len(vectors)}/{len(chunks)}", flush=True)
    # Refuse to combine model versions if the tag changed during indexing.
    if model_digest() != digest:
        raise ValueError("실행 중 모델이 변경됐어. 결과를 저장하지 않았어.")
    value = {"settings": expected,
             "records": [{**chunk, "embedding": vector}
                         for chunk, vector in zip(chunks, vectors)]}
    write_exclusive_json(cache, value)
    print(f"벡터 + 본문 + 출처 저장: {cache}", flush=True)
    return vectors


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("비교할 벡터 차원이 달라.")
    norm_a, norm_b = math.hypot(*a), math.hypot(*b)
    if not norm_a or not norm_b:
        raise ValueError("크기가 0인 벡터는 코사인 유사도를 계산할 수 없어.")
    # Normalize before multiplication for numerical stability.
    score = math.fsum((x / norm_a) * (y / norm_b) for x, y in zip(a, b))
    return max(-1.0, min(1.0, score))


def single_line(value: Any) -> str:
    if isinstance(value, list):
        value = " / ".join(str(item) for item in value)
    return " ".join(str(value or "").split())


def main() -> int:
    parser = argparse.ArgumentParser(description="W2: 로컬 벡터 생성·저장·Top-k 검색")
    parser.add_argument("--input", type=Path, default=BASE_DIR / "outputs/chunked_documents_v1.jsonl")
    parser.add_argument("--limit", type=int, default=50, help="파일 앞 N개 청크. 0이면 전체.")
    parser.add_argument("--query", help="없으면 터미널에서 질문 입력")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--cache", type=Path, help="생략하면 청크 수별 로컬 캐시 경로 사용")
    parser.add_argument("--preview-chars", type=int, default=350, help="0이면 본문 미표시")
    args = parser.parse_args()
    try:
        if args.limit < 0 or args.top_k < 1 or args.batch_size < 1 or args.preview_chars < 0:
            raise ValueError("limit/preview-chars는 0 이상, top-k/batch-size는 1 이상이어야 해.")
        query = (args.query if args.query is not None else input("검색 질문: ")).strip()
        if not query:
            raise ValueError("질문이 비어 있어.")
        source = args.input.expanduser().resolve()
        chunks = read_chunks(source, args.limit)
        cache = (args.cache or BASE_DIR / "outputs" / f"vectors_qwen3_{len(chunks)}.json").expanduser().resolve()
        if source == cache:
            raise ValueError("캐시와 입력 파일 경로는 달라야 해.")
        scope = "전체" if not args.limit else f"앞 {args.limit}개 한정"
        print(f"검색 범위: {scope} (실제 {len(chunks)}개 청크)", flush=True)
        print(f"모델: {MODEL} / 차원: {EXPECTED_DIM}", flush=True)
        digest = model_digest()
        vectors = load_or_embed(chunks, cache, digest, args.batch_size)

        # Search instruction belongs only on the query side for this model.
        query_input = f"Instruct: {TASK}\nQuery: {query}"
        started = time.perf_counter()
        query_vector = embed_texts([query_input])[0]
        if model_digest() != digest:
            raise ValueError("질문 처리 중 모델이 변경돼 비교를 중단했어.")
        ranked = sorted(((cosine_similarity(query_vector, vector), index)
                         for index, vector in enumerate(vectors)), reverse=True)
        print(f"질문 벡터: 1개 / {len(query_vector)}차원")
        print(f"질문 임베딩·모델 확인·유사도 계산: {time.perf_counter() - started:.2f}초")
        print("\n검색 결과 (유사도는 정답 확률이 아니야)")
        for rank, (score, index) in enumerate(ranked[:args.top_k], 1):
            chunk = chunks[index]
            print(f"\n[{rank}위] 코사인 유사도: {score:.4f}")
            print("문서:", single_line(chunk.get("title")))
            print("섹션:", single_line(chunk.get("section_path")) or "(본문)")
            print("chunk_id:", chunk["chunk_id"])
            if args.preview_chars:
                body = single_line(chunk["raw_text"])
                print("본문:", body[:args.preview_chars] + (" …" if len(body) > args.preview_chars else ""))
        print("\n완료: 벡터 검색과 연결된 본문 확인. DB 적재/LLM 답변 생성은 하지 않았어.")
        print("주의: 캐시에 회사 본문이 포함돼. 공개 저장소 업로드 금지. 공유할 때는 민감정보를 가려줘.")
        return 0
    except (OSError, ValueError, RuntimeError, EOFError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n사용자가 중단했어. 원본은 수정하지 않았어.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
