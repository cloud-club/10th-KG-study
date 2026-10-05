#!/usr/bin/env python3
"""Notion 문서 청크를 임베딩해 pgvector에 저장한다."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg


SRC_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_DIR))

from common import DOCUMENTS_PATH, embed, get_env, load_documents


EXPECTED_DIMENSION = 1024
REQUIRED_FIELDS = {"id", "page_id", "title", "content", "source", "chunk_index"}


def validate_documents(documents: list[dict]) -> None:
    if not documents:
        raise ValueError("색인할 문서가 없습니다.")

    seen_ids: set[str] = set()
    for line_number, document in enumerate(documents, start=1):
        missing = REQUIRED_FIELDS - document.keys()
        if missing:
            raise ValueError(f"JSONL {line_number}행에 필드가 없습니다: {sorted(missing)}")
        if document["id"] in seen_ids:
            raise ValueError(f"중복된 문서 id입니다: {document['id']}")
        seen_ids.add(document["id"])


def embedding_text(document: dict) -> str:
    return f"제목: {document['title']}\n본문: {document['content']}"


def vector_literal(vector: list[float]) -> str:
    if len(vector) != EXPECTED_DIMENSION:
        raise ValueError(
            f"임베딩 차원이 {len(vector)}입니다. "
            f"document_chunks는 {EXPECTED_DIMENSION}차원을 요구합니다."
        )
    return "[" + ",".join(str(value) for value in vector) + "]"


def index_documents(
    connection,
    documents: list[dict],
    batch_size: int = 8,
    keep_table: bool = False,
) -> int:
    if not keep_table:
        connection.execute("TRUNCATE TABLE document_chunks")

    indexed = 0
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        vectors = embed([embedding_text(document) for document in batch])
        if len(vectors) != len(batch):
            raise RuntimeError("Ollama가 요청한 문서 수와 다른 개수의 임베딩을 반환했습니다.")

        rows = [
            (
                document["id"],
                document["page_id"],
                document["title"],
                document["content"],
                document["source"],
                document["chunk_index"],
                vector_literal(vector),
            )
            for document, vector in zip(batch, vectors, strict=True)
        ]
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO document_chunks
                    (id, page_id, title, content, source, chunk_index, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (id) DO UPDATE SET
                    page_id = EXCLUDED.page_id,
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    source = EXCLUDED.source,
                    chunk_index = EXCLUDED.chunk_index,
                    embedding = EXCLUDED.embedding
                """,
                rows,
            )
        connection.commit()
        indexed += len(batch)
        print(f"임베딩 및 저장: {indexed}/{len(documents)}")

    return indexed


def main() -> None:
    parser = argparse.ArgumentParser(description="Notion 청크를 pgvector에 색인합니다.")
    parser.add_argument("--input", type=Path, default=DOCUMENTS_PATH)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--keep-table", action="store_true", help="기존 행을 삭제하지 않음")
    args = parser.parse_args()

    if args.batch_size <= 0:
        raise SystemExit("--batch-size는 1 이상이어야 합니다.")

    documents = load_documents(args.input)
    validate_documents(documents)
    dsn = get_env("POSTGRES_DSN", "postgresql://study:study@localhost:5432/personal_data")
    with psycopg.connect(dsn) as connection:
        count = index_documents(connection, documents, args.batch_size, args.keep_table)
        stored = connection.execute("SELECT count(*) FROM document_chunks").fetchone()[0]
    print(f"pgvector 색인 완료: 요청 {count}개, 테이블 문서 {stored}개")


if __name__ == "__main__":
    main()
