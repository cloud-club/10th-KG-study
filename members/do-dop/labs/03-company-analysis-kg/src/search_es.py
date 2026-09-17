#!/usr/bin/env python3
"""Elasticsearch BM25로 기업분석 청크를 검색한다."""

import argparse

import common_path  # noqa: F401
from index_es import DEFAULT_INDEX
from search_common.elasticsearch import DEFAULT_ES_URL, search


def search_chunks(es_url: str, index_name: str, query: str, size: int) -> list[dict]:
    body = {
        "size": size,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title^2", "text"],
                "type": "best_fields",
            }
        },
    }
    response = search(es_url, index_name, body)
    return [
        {**hit.get("_source", {}), "score": hit.get("_score", 0.0)}
        for hit in response.get("hits", {}).get("hits", [])
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--es-url", default=DEFAULT_ES_URL)
    parser.add_argument("--size", type=int, default=5)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    for rank, result in enumerate(search_chunks(args.es_url, args.index, args.query, args.size), start=1):
        line = f"{rank}. score={result['score']:.4f} chunk={result['id']} title={result['title']}"
        if args.show:
            line += f" text={result['text'][:120].replace(chr(10), ' ')!r}"
        print(line)


if __name__ == "__main__":
    main()

