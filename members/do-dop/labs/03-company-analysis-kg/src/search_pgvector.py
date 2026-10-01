#!/usr/bin/env python3
"""질의를 임베딩하고 pgvector에서 가까운 기업분석 청크를 찾는다."""

import argparse

import common_path  # noqa: F401
from index_pgvector import DEFAULT_DSN, TABLE_NAME
from search_common.embeddings import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, embed, to_pgvector_literal

try:
    import psycopg
except ImportError as error:
    raise SystemExit("pgvector 단계는 `pip install -r requirements.txt`가 필요합니다.") from error


def search_chunks(conn: "psycopg.Connection", query_vector: list[float], size: int) -> list[dict]:
    vector = to_pgvector_literal(query_vector)
    rows = conn.execute(
        f"""
        SELECT chunk_id, document_id, title, content, url,
               embedding <=> %s AS distance
        FROM {TABLE_NAME}
        ORDER BY embedding <=> %s
        LIMIT %s
        """,
        (vector, vector, size),
    ).fetchall()
    return [
        {
            "id": row[0], "document_id": row[1], "title": row[2], "text": row[3],
            "url": row[4], "distance": float(row[5]), "score": 1 - float(row[5]),
        }
        for row in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--size", type=int, default=5)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    query_vector = embed(args.query, model=args.model, ollama_url=args.ollama_url)
    with psycopg.connect(args.dsn) as conn:
        results = search_chunks(conn, query_vector, args.size)
    for rank, result in enumerate(results, start=1):
        line = f"{rank}. cosine={result['score']:.4f} chunk={result['id']} title={result['title']}"
        if args.show:
            line += f" text={result['text'][:120].replace(chr(10), ' ')!r}"
        print(line)


if __name__ == "__main__":
    main()

