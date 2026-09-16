"""JSONL 청크를 임베딩하여 PostgreSQL과 pgvector에 저장한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg
from sentence_transformers import SentenceTransformer


EMBEDDING_DIMENSION = 384


def load_chunks(path: Path) -> list[dict]:
    chunks: list[dict] = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            chunk = json.loads(line)
            if "id" not in chunk or "content" not in chunk:
                raise ValueError(f"{line_number}번째 줄에 id 또는 content가 없습니다.")
            chunks.append(chunk)
    return chunks


def create_table(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                document_title TEXT NOT NULL,
                heading TEXT NOT NULL,
                content TEXT NOT NULL,
                char_count INTEGER NOT NULL,
                embedding VECTOR({EMBEDDING_DIMENSION}) NOT NULL
            )
            """
        )
    connection.commit()


def vector_literal(vector) -> str:
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def save_chunks(
    connection: psycopg.Connection,
    chunks: list[dict],
    embeddings,
) -> None:
    rows = [
        (
            chunk["id"],
            chunk["source"],
            chunk["document_title"],
            chunk["heading"],
            chunk["content"],
            chunk["char_count"],
            vector_literal(embedding),
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]

    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO document_chunks (
                id, source, document_title, heading, content, char_count, embedding
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
            ON CONFLICT (id) DO UPDATE SET
                source = EXCLUDED.source,
                document_title = EXCLUDED.document_title,
                heading = EXCLUDED.heading,
                content = EXCLUDED.content,
                char_count = EXCLUDED.char_count,
                embedding = EXCLUDED.embedding
            """,
            rows,
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx
            ON document_chunks USING hnsw (embedding vector_cosine_ops)
            """
        )
    connection.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="청크 JSONL 파일")
    parser.add_argument(
        "--model",
        default="intfloat/multilingual-e5-small",
        help="Sentence Transformers 모델",
    )
    parser.add_argument(
        "--dsn",
        default="postgresql://study:study@127.0.0.1:5432/knowledge_graph",
        help="PostgreSQL 접속 문자열",
    )
    parser.add_argument("--batch-size", type=int, default=32, help="임베딩 묶음 크기")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = load_chunks(args.input)

    print(f"임베딩 모델을 불러옵니다: {args.model}")
    model = SentenceTransformer(args.model)
    dimension = model.get_embedding_dimension()
    if dimension != EMBEDDING_DIMENSION:
        raise ValueError(
            f"임베딩 차원이 다릅니다: 예상={EMBEDDING_DIMENSION}, 실제={dimension}"
        )

    passages = [
        f"passage: {chunk['document_title']}\n{chunk['heading']}\n{chunk['content']}"
        for chunk in chunks
    ]
    embeddings = model.encode(
        passages,
        batch_size=args.batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    with psycopg.connect(args.dsn) as connection:
        create_table(connection)
        save_chunks(connection, chunks, embeddings)
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM document_chunks")
            count = cursor.fetchone()[0]

    print(f"이번 실행에서 청크 {len(chunks)}개를 임베딩했습니다.")
    print(f"PostgreSQL에 저장된 청크 수: {count}개")
    print(f"임베딩 차원: {dimension}")


if __name__ == "__main__":
    main()
