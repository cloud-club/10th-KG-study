#!/usr/bin/env python3
"""Elasticsearch BM25로 개인 문서 청크를 검색한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from elasticsearch import Elasticsearch


SRC_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_DIR))

from common import get_env


INDEX = "personal-documents"


def search_documents(client: Elasticsearch, query: str, limit: int = 5) -> list[dict]:
    response = client.search(
        index=INDEX,
        size=limit,
        query={
            "multi_match": {
                "query": query,
                "fields": ["title^2", "content"],
            }
        },
    )
    return [
        {
            "id": hit["_source"]["id"],
            "rank": rank,
            "score": hit["_score"],
            "title": hit["_source"]["title"],
            "source": hit["_source"]["source"],
            "chunk_index": hit["_source"]["chunk_index"],
            "content": hit["_source"]["content"],
        }
        for rank, hit in enumerate(response["hits"]["hits"], start=1)
    ]


def print_text(results: list[dict]) -> None:
    if not results:
        print("검색 결과가 없습니다.")
        return

    for result in results:
        preview = " ".join(result["content"].split())[:180]
        print(f"[{result['rank']}] score={result['score']:.6f}")
        print(f"title: {result['title']}")
        print(f"source: {result['source']}#chunk-{result['chunk_index']}")
        print(f"content: {preview}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Elasticsearch BM25로 개인 문서를 검색합니다.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="RRF에서 재사용할 JSON 형태로 출력")
    args = parser.parse_args()

    if args.limit <= 0:
        raise SystemExit("--limit는 1 이상이어야 합니다.")

    client = Elasticsearch(get_env("ES_URL", "http://localhost:9200"))
    results = search_documents(client, args.query, args.limit)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_text(results)


if __name__ == "__main__":
    main()
