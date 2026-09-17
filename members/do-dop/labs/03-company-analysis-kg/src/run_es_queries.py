#!/usr/bin/env python3
"""평가 질문을 BM25로 실행하고 Hit@5·Recall@5를 기록한다."""

import argparse
import json
from pathlib import Path

import common_path  # noqa: F401
from index_es import DEFAULT_INDEX
from search_common.elasticsearch import DEFAULT_ES_URL
from search_common.evaluation import evaluate_at_k
from search_common.jsonl import write_jsonl
from search_es import search_chunks


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_QUERIES = Path(__file__).resolve().parents[1] / "config" / "evaluation_queries.json"
DEFAULT_OUTPUT = ROOT / "data" / "do-dop" / "company-analysis-kg" / "results" / "bm25.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--es-url", default=DEFAULT_ES_URL)
    parser.add_argument("--size", type=int, default=5)
    args = parser.parse_args()

    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    rows = []
    for query in queries:
        results = search_chunks(args.es_url, args.index, query["query"], args.size)
        retrieved = [item["id"] for item in results]
        rows.append(
            {
                "query_id": query["id"],
                "query": query["query"],
                "retrieved_chunk_ids": retrieved,
                "scores": [round(float(item["score"]), 6) for item in results],
                **evaluate_at_k(retrieved, query["relevant_chunk_ids"], args.size),
            }
        )
    write_jsonl(args.output, rows)
    print(f"질의 {len(rows)}개 결과 저장: {args.output}")


if __name__ == "__main__":
    main()
