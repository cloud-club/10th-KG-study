#!/usr/bin/env python3
"""평가 질문을 벡터 검색하고 Hit@5·Recall@5를 기록한다."""

import argparse
import json
from pathlib import Path

import common_path  # noqa: F401
from index_pgvector import DEFAULT_DSN
from search_common.embeddings import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, embed
from search_common.evaluation import evaluate_at_k
from search_common.jsonl import write_jsonl
from search_pgvector import search_chunks

try:
    import psycopg
except ImportError as error:
    raise SystemExit("pgvector 단계는 `pip install -r requirements.txt`가 필요합니다.") from error


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_QUERIES = Path(__file__).resolve().parents[1] / "config" / "evaluation_queries.json"
DEFAULT_OUTPUT = ROOT / "data" / "do-dop" / "company-analysis-kg" / "results" / "vector.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--size", type=int, default=5)
    args = parser.parse_args()

    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    rows = []
    with psycopg.connect(args.dsn) as conn:
        for query in queries:
            vector = embed(query["query"], model=args.model, ollama_url=args.ollama_url)
            results = search_chunks(conn, vector, args.size)
            retrieved = [item["id"] for item in results]
            rows.append(
                {
                    "query_id": query["id"], "query": query["query"],
                    "retrieved_chunk_ids": retrieved,
                    "scores": [round(item["score"], 6) for item in results],
                    **evaluate_at_k(retrieved, query["relevant_chunk_ids"], args.size),
                }
            )
    write_jsonl(args.output, rows)
    print(f"질의 {len(rows)}개 결과 저장: {args.output}")


if __name__ == "__main__":
    main()
