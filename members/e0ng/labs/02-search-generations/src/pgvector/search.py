#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import embed, get_env


def main() -> None:
    parser = argparse.ArgumentParser(description="pgvector 코사인 유사도로 채팅을 검색합니다.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    query_vector = embed([args.query])[0]
    dsn = get_env("POSTGRES_DSN", "postgresql://study:study@localhost:5432/chat_search")
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, sender, message, timestamp,
                   1 - (embedding <=> %s::vector) AS cosine_similarity
            FROM chat_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (str(query_vector), str(query_vector), args.limit),
        )
        for rank, (row_id, sender, message, timestamp, score) in enumerate(cursor, start=1):
            print(f"{rank}\t{float(score):.6f}\t{row_id}\t{timestamp.isoformat()}\t{sender}\t{message}")


if __name__ == "__main__":
    main()
