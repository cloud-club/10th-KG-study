#!/usr/bin/env python3
"""기업분석 청크를 임베딩해 pgvector에 저장한다."""

import argparse
import json
from pathlib import Path

import common_path  # noqa: F401
from search_common.embeddings import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, embed, to_pgvector_literal
from search_common.jsonl import read_jsonl

try:
    import psycopg
except ImportError as error:
    raise SystemExit("pgvector 단계는 `pip install -r requirements.txt`가 필요합니다.") from error


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_INPUT = ROOT / "data" / "do-dop" / "company-analysis-kg" / "processed" / "chunks.jsonl"
DEFAULT_DSN = "postgresql://kg:kg@localhost:5432/kg"
TABLE_NAME = "do_dop_company_analysis_chunks"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def ensure_table(conn: "psycopg.Connection", recreate: bool) -> None:
    if recreate:
        conn.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def insert_chunks(conn: "psycopg.Connection", chunks: list[dict], model: str, ollama_url: str) -> int:
    inserted = 0
    with conn.cursor() as cursor:
        for index, chunk in enumerate(chunks, start=1):
            vector = embed(chunk["text"], model=model, ollama_url=ollama_url)
            cursor.execute(
                f"""
                INSERT INTO {TABLE_NAME}
                    (chunk_id, document_id, title, companies, source, published_at, content, url, embedding)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    document_id = EXCLUDED.document_id,
                    title = EXCLUDED.title,
                    companies = EXCLUDED.companies,
                    source = EXCLUDED.source,
                    published_at = EXCLUDED.published_at,
                    content = EXCLUDED.content,
                    url = EXCLUDED.url,
                    embedding = EXCLUDED.embedding
                """,
                (
                    chunk["id"], chunk["document_id"], chunk["title"],
                    json.dumps(chunk["company"], ensure_ascii=False), chunk["source"],
                    chunk["date"], chunk["text"], chunk["url"], to_pgvector_literal(vector),
                ),
            )
            inserted += 1
            if index % 10 == 0 or index == len(chunks):
                print(f"진행률: {index}/{len(chunks)}")
    conn.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()

    chunks = read_jsonl(args.input)
    with psycopg.connect(args.dsn) as conn:
        ensure_table(conn, args.recreate)
        inserted = insert_chunks(conn, chunks, args.model, args.ollama_url)
    print(f"삽입 완료: {inserted}")


if __name__ == "__main__":
    main()

