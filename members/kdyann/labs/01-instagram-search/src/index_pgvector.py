"""Instagram 검색 문서를 임베딩해 PostgreSQL/pgvector에 적재한다."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from sentence_transformers import SentenceTransformer

from common import EMBED_DIMENSION, EMBED_MODEL, PG_DSN, PG_TABLE, load_documents


DDL = f"""
CREATE EXTENSION IF NOT EXISTS vector;
DROP TABLE IF EXISTS {PG_TABLE};
CREATE TABLE {PG_TABLE} (
    id text PRIMARY KEY,
    source text NOT NULL,
    text text NOT NULL,
    hashtags text[] NOT NULL DEFAULT '{{}}',
    media_type text,
    media_product_type text,
    permalink text,
    published_at timestamptz,
    collected_at timestamptz NOT NULL,
    metrics jsonb NOT NULL,
    rates jsonb NOT NULL,
    embedding vector({EMBED_DIMENSION}) NOT NULL
);
"""

HNSW_DDL = f"""
CREATE INDEX {PG_TABLE}_embedding_hnsw
ON {PG_TABLE}
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
"""


def vector_literal(vector: Any) -> str:
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def load_model() -> SentenceTransformer:
    print(f"임베딩 모델 로딩: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)
    dimension = model.get_sentence_embedding_dimension()
    if dimension != EMBED_DIMENSION:
        raise ValueError(f"모델 차원이 {dimension}입니다. 예상값: {EMBED_DIMENSION}")
    return model


def index_documents() -> int:
    documents = load_documents()
    model = load_model()
    embeddings = model.encode(
        [f"passage: {document['text']}" for document in documents],
        batch_size=16,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    with psycopg.connect(PG_DSN) as connection:
        with connection.cursor() as cursor:
            cursor.execute(DDL)
            for document, embedding in zip(documents, embeddings):
                cursor.execute(
                    f"""
                    INSERT INTO {PG_TABLE} (
                        id, source, text, hashtags, media_type, media_product_type,
                        permalink, published_at, collected_at, metrics, rates, embedding
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector
                    )
                    """,
                    (
                        document["id"], document["source"], document["text"],
                        document.get("hashtags", []), document.get("media_type"),
                        document.get("media_product_type"), document.get("permalink"),
                        document.get("published_at"), document.get("collected_at"),
                        Jsonb(document.get("metrics", {})), Jsonb(document.get("rates", {})),
                        vector_literal(embedding),
                    ),
                )
            cursor.execute(HNSW_DDL)
            cursor.execute(f"SELECT count(*) FROM {PG_TABLE}")
            count = cursor.fetchone()[0]
        connection.commit()
    return count


def main() -> None:
    count = index_documents()
    print(f"[pgvector] 적재 완료: {count}행")
    print(f"테이블: {PG_TABLE}")
    print(f"벡터: {EMBED_MODEL}, {EMBED_DIMENSION}차원")
    print("인덱스: HNSW + 코사인 거리")


if __name__ == "__main__":
    main()
