#!/usr/bin/env python3
"""질의를 임베딩해 pgvector 테이블에서 코사인 유사도로 가장 가까운 청크를 찾는다.

search_grep.sh / search_es.py와 같은 원칙으로, 기본 출력에는 원문을 담지 않는다.
"""

from __future__ import annotations

import argparse
import sys

import psycopg

from embed_ollama import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, embed, to_pgvector_literal
from index_pgvector import DEFAULT_DSN, TABLE_NAME


def search(
    conn: psycopg.Connection, query_embedding: list[float], size: int
) -> list[dict]:
    # <=>로 코사인 거리를 계산하고 거리가 가까운 청크부터 가져온다.
    vector_literal = to_pgvector_literal(query_embedding)
    rows = conn.execute(
        f"""
        SELECT chunk_id, sender_id, content, embedding <=> %s AS distance
        FROM {TABLE_NAME}
        ORDER BY embedding <=> %s
        LIMIT %s
        """,
        (vector_literal, vector_literal, size),
    ).fetchall()
    # 거리는 작을수록 가깝기 때문에 1 - 거리로 유사도를 계산한다.
    return [
        {
            "chunk_id": row[0],
            "sender_id": row[1],
            "content": row[2],
            "distance": row[3],
            "cosine_similarity": 1 - row[3],
        }
        for row in rows
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="pgvector 코사인 유사도로 카카오톡 청크를 검색합니다."
    )
    parser.add_argument("query", help="검색어")
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="PostgreSQL 연결 문자열")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama 임베딩 모델")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama base URL")
    parser.add_argument("--size", type=int, default=5, help="반환할 결과 수 (기본 5)")
    parser.add_argument(
        "--show", action="store_true", help="원문 일부를 함께 출력합니다 (기본은 유사도만)"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    # 저장된 청크와 같은 모델로 검색어도 임베딩한다.
    query_embedding = embed(args.query, model=args.model, ollama_url=args.ollama_url)

    # PostgreSQL에서 질의 벡터와 가까운 청크를 검색한다.
    with psycopg.connect(args.dsn) as conn:
        results = search(conn, query_embedding, args.size)

    print(f"상위 {len(results)}개:")
    for rank, result in enumerate(results, start=1):
        if args.show:
            snippet = result["content"][:40].replace("\n", " ")
            print(
                f"  {rank}. cosine={result['cosine_similarity']:.4f} "
                f"sender={result['sender_id']} text={snippet!r}"
            )
        else:
            print(
                f"  {rank}. cosine={result['cosine_similarity']:.4f} "
                f"sender={result['sender_id']} chunk={result['chunk_id']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
