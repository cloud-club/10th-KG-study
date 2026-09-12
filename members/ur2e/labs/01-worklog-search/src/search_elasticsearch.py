"""Elasticsearch(nori) BM25로 작업기록 청크를 검색한다."""

from __future__ import annotations

import argparse
import time
from typing import Any

from common import ES_INDEX
from index_elasticsearch import request
from search_grep import one_line


def search_bm25(
    query: str,
    limit: int = 3,
    index_name: str = ES_INDEX,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[tuple[dict[str, Any], float]], float]:
    """`date_from`/`date_to`(YYYY-MM-DD)를 주면 그 범위의 문서만 대상으로 BM25 순위를 매긴다.

    실험으로 확인한 문제: "1월에 무슨 일 있었지" 같은 질문은 본문에 "1월"이라는
    글자가 들어있는 아무 문서나(회고하는 2월 문서 등) 걸려서 틀린 문서가 1위로
    올라온다. `content`만 보는 매칭으로는 이걸 못 거른다 — `date` 필드를 검색
    조건(filter)으로 걸어야 한다.
    """
    filters = []
    if date_from or date_to:
        range_filter: dict[str, str] = {}
        if date_from:
            range_filter["gte"] = date_from
        if date_to:
            range_filter["lte"] = date_to
        filters.append({"range": {"date": range_filter}})

    body = {
        "size": limit,
        "query": {
            "bool": {
                "must": {"multi_match": {"query": query, "fields": ["content^1", "title^2"]}},
                "filter": filters,
            }
        },
    }
    started = time.perf_counter()
    response = request("POST", f"{index_name}/_search", body)
    elapsed = (time.perf_counter() - started) * 1000
    rows = [(hit["_source"], float(hit["_score"])) for hit in response["hits"]["hits"]]
    return rows, elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--date-from", default=None, help="YYYY-MM-DD, 이 날짜 이후 문서만")
    parser.add_argument("--date-to", default=None, help="YYYY-MM-DD, 이 날짜 이전 문서만")
    args = parser.parse_args()

    rows, elapsed = search_bm25(args.query, args.limit, date_from=args.date_from, date_to=args.date_to)
    print(f'[Elasticsearch BM25/nori] "{args.query}" · {len(rows)}건 · {elapsed:.2f}ms')
    for rank, (doc, score) in enumerate(rows, 1):
        heading = f"#{doc['heading']}" if doc["heading"] else ""
        print(f"{rank}. {doc['source_path']}{heading} · 점수 {score:.3f}")
        print(f"   {one_line(doc['content'])}")


if __name__ == "__main__":
    main()
