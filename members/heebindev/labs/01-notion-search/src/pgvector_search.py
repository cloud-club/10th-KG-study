"""질문을 임베딩하고 pgvector에서 의미가 가까운 청크를 검색한다."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HF_HOME", str(LAB_ROOT / ".cache" / "huggingface"))

import psycopg
from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_DSN = "postgresql://study:study@127.0.0.1:5432/knowledge_graph"


def vector_literal(vector) -> str:
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="검색할 자연어 질문")
    parser.add_argument("--limit", type=int, default=3, help="출력할 결과 수")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="임베딩 모델")
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="PostgreSQL 접속 문자열")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.limit <= 0:
        raise ValueError("--limit은 1 이상이어야 합니다.")

    model = SentenceTransformer(args.model)
    query_embedding = model.encode(
        f"query: {args.query}",
        normalize_embeddings=True,
    )
    query_vector = vector_literal(query_embedding)

    with psycopg.connect(args.dsn) as connection:
        results = connection.execute(
            """
            SELECT
                document_title,
                heading,
                content,
                1 - (embedding <=> %s::vector) AS similarity
            FROM document_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query_vector, query_vector, args.limit),
        ).fetchall()

    print(f"검색어: {args.query}")
    for rank, (title, heading, content, similarity) in enumerate(results, start=1):
        preview = " ".join(content.split())[:160]
        print(f"\n{rank}. 유사도={similarity:.4f}")
        print(f"   문서: {title}")
        print(f"   소제목: {heading}")
        print(f"   내용: {preview}...")


if __name__ == "__main__":
    main()
