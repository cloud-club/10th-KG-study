"""동일한 쿼리를 grep, Elasticsearch BM25, pgvector에 보내 결과를 비교한다."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from typing import Any

import psycopg

from common import (
    EMBED_MODEL,
    ES_INDEX,
    GREP_CORPUS,
    PG_DSN,
    PG_TABLE,
    load_documents,
    one_line,
    result_label,
)
from index_elasticsearch import request
from index_pgvector import load_model, vector_literal
from prepare_grep import prepare


def by_id() -> dict[str, dict[str, Any]]:
    return {document["id"]: document for document in load_documents()}


def search_grep(query: str, limit: int) -> tuple[list[dict[str, Any]], float]:
    if not GREP_CORPUS.exists():
        prepare()
    executable = shutil.which("rg") or shutil.which("grep")
    if not executable:
        raise RuntimeError("rg 또는 grep 실행 파일이 필요합니다.")
    command = (
        [executable, "--ignore-case", "--fixed-strings", "--color=never", query, str(GREP_CORPUS)]
        if executable.endswith("rg")
        else [executable, "-iF", query, str(GREP_CORPUS)]
    )
    started = time.perf_counter()
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    elapsed = (time.perf_counter() - started) * 1000
    if completed.returncode not in (0, 1):
        raise RuntimeError(completed.stderr.strip())
    documents = by_id()
    ids = [line.split("\t", 1)[0] for line in completed.stdout.splitlines()]
    return [documents[media_id] for media_id in ids[:limit] if media_id in documents], elapsed


def search_bm25(query: str, limit: int, field: str = "text") -> tuple[list[tuple[dict[str, Any], float]], float]:
    started = time.perf_counter()
    response = request(
        "POST",
        f"{ES_INDEX}/_search",
        {"size": limit, "query": {"match": {field: query}}},
    )
    elapsed = (time.perf_counter() - started) * 1000
    documents = by_id()
    rows = []
    for hit in response["hits"]["hits"]:
        document = documents.get(hit["_id"], hit["_source"])
        rows.append((document, float(hit["_score"])))
    return rows, elapsed


def search_vector(query: str, limit: int) -> tuple[list[tuple[dict[str, Any], float]], float]:
    model = load_model()
    vector = model.encode([f"query: {query}"], normalize_embeddings=True)[0]
    started = time.perf_counter()
    with psycopg.connect(PG_DSN) as connection, connection.cursor() as cursor:
        cursor.execute("SET hnsw.ef_search = 100")
        cursor.execute(
            f"""
            SELECT id, 1 - (embedding <=> %s::vector) AS score
            FROM {PG_TABLE}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector_literal(vector), vector_literal(vector), limit),
        )
        matches = cursor.fetchall()
    elapsed = (time.perf_counter() - started) * 1000
    documents = by_id()
    return [(documents[media_id], float(score)) for media_id, score in matches], elapsed


def show_result(rank: int, document: dict[str, Any], score: float | None = None) -> None:
    score_text = "" if score is None else f" · 점수 {score:.4f}"
    print(f"  {rank}. {result_label(document)}{score_text}")
    print(f"     {one_line(document['text'])[:120]}")
    print(f"     {document.get('permalink', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="세 방식에 동일하게 보낼 검색어 또는 질문")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--ngram", action="store_true", help="BM25와 n-gram 필드를 함께 비교")
    args = parser.parse_args()

    print(f'\n검색어: "{args.query}"\n')

    grep_rows, grep_ms = search_grep(args.query, args.limit)
    print(f"[0세대 grep] {len(grep_rows)}건 · {grep_ms:.1f}ms · 정확한 부분 문자열, 순위 없음")
    for rank, document in enumerate(grep_rows, 1):
        show_result(rank, document)

    bm25_rows, bm25_ms = search_bm25(args.query, args.limit)
    print(f"\n[1세대 Elasticsearch BM25/Nori] {len(bm25_rows)}건 · {bm25_ms:.1f}ms")
    for rank, (document, score) in enumerate(bm25_rows, 1):
        show_result(rank, document, score)

    if args.ngram:
        ngram_rows, ngram_ms = search_bm25(args.query, args.limit, "text.ngram")
        print(f"\n[1세대 Elasticsearch BM25/n-gram] {len(ngram_rows)}건 · {ngram_ms:.1f}ms")
        for rank, (document, score) in enumerate(ngram_rows, 1):
            show_result(rank, document, score)

    vector_rows, vector_ms = search_vector(args.query, args.limit)
    print(f"\n[2세대 pgvector] {len(vector_rows)}건 · {vector_ms:.1f}ms · {EMBED_MODEL}")
    for rank, (document, score) in enumerate(vector_rows, 1):
        show_result(rank, document, score)


if __name__ == "__main__":
    main()
