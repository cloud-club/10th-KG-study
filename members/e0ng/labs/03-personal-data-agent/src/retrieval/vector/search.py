#!/usr/bin/env python3
"""pgvector 코사인 거리로 개인 문서 청크를 검색한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg


SRC_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_DIR))

from common import embed, get_env

from retrieval.vector.index_documents import vector_literal


def search_documents(connection, query: str, limit: int = 5) -> list[dict]:
    query_vector = vector_literal(embed([query])[0])
    rows = connection.execute(
        """
        SELECT
            id,
            title,
            source,
            chunk_index,
            content,
            1 - (embedding <=> %s::vector) AS score
        FROM document_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (query_vector, query_vector, limit),
    ).fetchall()
    return [
        {
            "id": row[0],
            "rank": rank,
            "score": float(row[5]),
            "title": row[1],
            "source": row[2],
            "chunk_index": row[3],
            "content": row[4],
        }
        for rank, row in enumerate(rows, start=1)
    ]


def print_text(results: list[dict]) -> None:
    if not results:
        print("검색 결과가 없습니다.")
        return

    for result in results:
        preview = " ".join(result["content"].split())[:180]
        print(f"[{result['rank']}] score={result['score']:.6f}")
        print(f"title: {result['title']}")
        print(f"source: {result['source']}#chunk-{result['chunk_index']}")
        print(f"content: {preview}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="pgvector로 개인 문서를 검색합니다.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="RRF에서 재사용할 JSON 형태로 출력")
    args = parser.parse_args()

    if args.limit <= 0:
        raise SystemExit("--limit는 1 이상이어야 합니다.")

    dsn = get_env("POSTGRES_DSN", "postgresql://study:study@localhost:5432/personal_data")
    with psycopg.connect(dsn) as connection:
        results = search_documents(connection, args.query, args.limit)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_text(results)


if __name__ == "__main__":
    main()
