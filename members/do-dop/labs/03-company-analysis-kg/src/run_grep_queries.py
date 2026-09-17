#!/usr/bin/env python3
"""평가 질문의 grep_query를 실행하고 Hit@5·Recall@5를 기록한다."""

import argparse
import json
from pathlib import Path

import common_path  # noqa: F401
from search_common.evaluation import evaluate_at_k
from search_common.jsonl import read_jsonl, write_jsonl
from search_grep import DEFAULT_INPUT, search


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_QUERIES = Path(__file__).resolve().parents[1] / "config" / "evaluation_queries.json"
DEFAULT_OUTPUT = ROOT / "data" / "do-dop" / "company-analysis-kg" / "results" / "grep.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--size", type=int, default=5)
    args = parser.parse_args()

    chunks = read_jsonl(args.input)
    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    rows = []
    for query in queries:
        grep_query = query["grep_query"]
        keyword_retrieved = [item["id"] for item in search(chunks, grep_query)[: args.size]]
        full_query_retrieved = [item["id"] for item in search(chunks, query["query"])[: args.size]]
        rows.append(
            {
                "query_id": query["id"],
                "query": query["query"],
                "grep_query": grep_query,
                "full_query_retrieved_chunk_ids": full_query_retrieved,
                **{
                    f"full_query_{key}": value
                    for key, value in evaluate_at_k(
                        full_query_retrieved, query["relevant_chunk_ids"], args.size
                    ).items()
                },
                "retrieved_chunk_ids": keyword_retrieved,
                **evaluate_at_k(keyword_retrieved, query["relevant_chunk_ids"], args.size),
            }
        )
    write_jsonl(args.output, rows)
    print(f"질의 {len(rows)}개 결과 저장: {args.output}")


if __name__ == "__main__":
    main()
