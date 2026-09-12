"""pgvector 코사인 유사도로 작업기록 청크를 검색한다."""

from __future__ import annotations

import argparse
import time
from typing import Any

import psycopg

from common import PG_DSN, PG_TABLE
from embed import embed_query
from index_pgvector import assert_safe_table_name, vector_literal
from search_grep import one_line


def search_vector(
    query: str,
    limit: int = 3,
    table_name: str = PG_TABLE,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[tuple[dict[str, Any], float]], float]:
    """`date_from`/`date_to`(YYYY-MM-DD)를 주면 `date` 컬럼(text)을 문자열 비교로
    걸러낸 뒤 코사인 거리로 정렬한다. `date`가 NULL인 청크는 필터를 걸면 자동으로
    빠진다 — 날짜를 모르는 문서까지 시간 질문에 답할 순 없다는 뜻이라 의도된 동작."""
    assert_safe_table_name(table_name)
    vector = embed_query(query)

    where_clauses = []
    params: list[Any] = [vector_literal(vector)]
    if date_from:
        where_clauses.append("date >= %s")
        params.append(date_from)
    if date_to:
        where_clauses.append("date <= %s")
        params.append(date_to)
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    params.extend([vector_literal(vector), limit])

    started = time.perf_counter()
    with psycopg.connect(PG_DSN) as connection, connection.cursor() as cursor:
        cursor.execute("SET hnsw.ef_search = 100")
        cursor.execute(
            f"""
            SELECT chunk_id, source_path, doc_type, title, heading, content, date, tags,
                   1 - (embedding <=> %s::vector) AS score
            FROM {table_name}
            {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            params,
        )
        rows = cursor.fetchall()
    elapsed = (time.perf_counter() - started) * 1000
    columns = ["chunk_id", "source_path", "doc_type", "title", "heading", "content", "date", "tags"]
    results = [(dict(zip(columns, row[:-1])), float(row[-1])) for row in rows]
    return results, elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--date-from", default=None, help="YYYY-MM-DD, 이 날짜 이후 문서만")
    parser.add_argument("--date-to", default=None, help="YYYY-MM-DD, 이 날짜 이전 문서만")
    args = parser.parse_args()

    rows, elapsed = search_vector(args.query, args.limit, date_from=args.date_from, date_to=args.date_to)
    print(f'[pgvector/HNSW] "{args.query}" · {len(rows)}건 · {elapsed:.2f}ms')
    for rank, (doc, score) in enumerate(rows, 1):
        heading = f"#{doc['heading']}" if doc["heading"] else ""
        print(f"{rank}. {doc['source_path']}{heading} · 유사도 {score:.4f}")
        print(f"   {one_line(doc['content'])}")


if __name__ == "__main__":
    main()
