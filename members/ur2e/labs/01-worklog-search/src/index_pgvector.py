"""chunks.jsonl 을 임베딩해 PostgreSQL/pgvector 에 적재한다.

OPENAI_API_KEY 가 필요하다. 청크 125개 기준 text-embedding-3-small 호출
비용은 매우 작지만(청크당 몇백 토큰), 매 실행마다 전체를 다시 임베딩하므로
반복 실행 시 비용이 쌓일 수 있다는 점은 알고 있어야 한다.
"""

from __future__ import annotations

import re
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from common import EMBED_DIMENSION, EMBED_MODEL, PG_DSN, PG_TABLE
from embed import embed_texts
from search_grep import load_chunks

TABLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def assert_safe_table_name(table_name: str) -> None:
    """테이블명을 SQL에 직접 이어붙이므로(파라미터 바인딩 불가) 안전한 식별자인지 먼저 확인한다."""
    if not TABLE_NAME_RE.match(table_name):
        raise ValueError(f"안전하지 않은 테이블명: {table_name!r}")


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(float(v)) for v in vector) + "]"


def index_chunks(chunks: list[dict[str, Any]] | None = None, table_name: str = PG_TABLE) -> int:
    assert_safe_table_name(table_name)
    chunks = chunks if chunks is not None else load_chunks()
    print(f"임베딩 모델: {EMBED_MODEL} ({len(chunks)}청크)")
    embeddings = embed_texts([chunk["content"] for chunk in chunks])

    ddl = f"""
    CREATE EXTENSION IF NOT EXISTS vector;
    DROP TABLE IF EXISTS {table_name};
    CREATE TABLE {table_name} (
        chunk_id text PRIMARY KEY,
        source_path text NOT NULL,
        doc_type text NOT NULL,
        title text NOT NULL,
        heading text,
        content text NOT NULL,
        date text,
        tags text[] NOT NULL DEFAULT '{{}}',
        frontmatter jsonb NOT NULL,
        embedding vector({EMBED_DIMENSION}) NOT NULL
    );
    """
    hnsw_ddl = f"""
    CREATE INDEX {table_name}_embedding_hnsw
    ON {table_name}
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
    """

    with psycopg.connect(PG_DSN) as connection:
        with connection.cursor() as cursor:
            cursor.execute(ddl)
            for chunk, embedding in zip(chunks, embeddings):
                cursor.execute(
                    f"""
                    INSERT INTO {table_name} (
                        chunk_id, source_path, doc_type, title, heading,
                        content, date, tags, frontmatter, embedding
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                    """,
                    (
                        chunk["chunk_id"], chunk["source_path"], chunk["doc_type"],
                        chunk["title"], chunk["heading"], chunk["content"], chunk["date"],
                        chunk["tags"], Jsonb(chunk["frontmatter"]), vector_literal(embedding),
                    ),
                )
            cursor.execute(hnsw_ddl)
            cursor.execute(f"SELECT count(*) FROM {table_name}")
            count = cursor.fetchone()[0]
        connection.commit()
    return count


def main() -> None:
    count = index_chunks()
    print(f"[pgvector] 적재 완료: {count}행")
    print(f"테이블: {PG_TABLE}")
    print("인덱스: HNSW + 코사인 거리")


if __name__ == "__main__":
    main()
