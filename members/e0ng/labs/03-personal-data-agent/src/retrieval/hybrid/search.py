#!/usr/bin/env python3
"""BM25와 벡터 검색 결과를 RRF로 결합한다."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import psycopg


SRC_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_DIR))

from common import get_env
from retrieval.vector.search import search_documents as vector_search


INDEX = "personal-documents"


def keyword_search(es_url: str, query: str, limit: int) -> list[dict]:
    payload = json.dumps(
        {
            "size": limit,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^2", "content"],
                }
            },
        }
    ).encode()
    request = urllib.request.Request(
        f"{es_url.rstrip('/')}/{INDEX}/_search",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = json.load(response)
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
        for rank, hit in enumerate(body["hits"]["hits"], start=1)
    ]


def reciprocal_rank_fusion(
    result_lists: dict[str, list[dict]],
    rank_constant: int = 60,
    limit: int = 5,
) -> list[dict]:
    fused: dict[str, dict] = {}

    for search_name, results in result_lists.items():
        for result in results:
            document_id = result["id"]
            if document_id not in fused:
                fused[document_id] = {
                    "id": document_id,
                    "score": 0.0,
                    "title": result["title"],
                    "source": result["source"],
                    "chunk_index": result["chunk_index"],
                    "content": result["content"],
                    "ranks": {},
                }
            rank = result["rank"]
            fused[document_id]["score"] += 1.0 / (rank_constant + rank)
            fused[document_id]["ranks"][search_name] = rank

    ordered = sorted(
        fused.values(),
        key=lambda result: (-result["score"], result["id"]),
    )[:limit]
    for rank, result in enumerate(ordered, start=1):
        result["rank"] = rank
    return ordered


def hybrid_search(
    es_url: str,
    postgres,
    query: str,
    limit: int = 5,
    rank_window: int = 20,
    rank_constant: int = 60,
) -> list[dict]:
    keyword_results = keyword_search(es_url, query, rank_window)
    vector_results = vector_search(postgres, query, rank_window)
    return reciprocal_rank_fusion(
        {"keyword": keyword_results, "vector": vector_results},
        rank_constant=rank_constant,
        limit=limit,
    )


def print_text(results: list[dict]) -> None:
    if not results:
        print("검색 결과가 없습니다.")
        return

    for result in results:
        preview = " ".join(result["content"].split())[:180]
        keyword_rank = result["ranks"].get("keyword", "-")
        vector_rank = result["ranks"].get("vector", "-")
        print(
            f"[{result['rank']}] rrf_score={result['score']:.6f} "
            f"keyword_rank={keyword_rank} vector_rank={vector_rank}"
        )
        print(f"title: {result['title']}")
        print(f"source: {result['source']}#chunk-{result['chunk_index']}")
        print(f"content: {preview}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="BM25와 벡터 결과를 RRF로 검색합니다.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=5, help="최종 결과 수")
    parser.add_argument("--rank-window", type=int, default=20, help="각 검색이 제공할 후보 수")
    parser.add_argument("--rank-constant", type=int, default=60, help="RRF 순위 완화 상수")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.limit <= 0:
        raise SystemExit("--limit는 1 이상이어야 합니다.")
    if args.rank_window < args.limit:
        raise SystemExit("--rank-window는 --limit 이상이어야 합니다.")
    if args.rank_constant < 0:
        raise SystemExit("--rank-constant는 0 이상이어야 합니다.")

    es_url = get_env("ES_URL", "http://localhost:9200")
    dsn = get_env("POSTGRES_DSN", "postgresql://study:study@localhost:5432/personal_data")
    with psycopg.connect(dsn) as postgres:
        results = hybrid_search(
            es_url,
            postgres,
            args.query,
            args.limit,
            args.rank_window,
            args.rank_constant,
        )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_text(results)


if __name__ == "__main__":
    main()
