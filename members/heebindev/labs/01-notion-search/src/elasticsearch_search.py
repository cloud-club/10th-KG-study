"""Elasticsearch에서 BM25 키워드 검색을 실행한다."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="검색할 키워드 또는 문장")
    parser.add_argument("--limit", type=int, default=3, help="출력할 결과 수")
    parser.add_argument("--url", default="http://127.0.0.1:9200")
    parser.add_argument("--index", default="notion_chunks")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.limit <= 0:
        raise ValueError("--limit은 1 이상이어야 합니다.")

    body = {
        "size": args.limit,
        "_source": ["document_title", "heading", "content"],
        "query": {"match": {"content": args.query}},
    }
    request = urllib.request.Request(
        f"{args.url.rstrip('/')}/{args.index}/_search",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Elasticsearch 검색 실패 ({error.code}): {message}") from error

    print(f"검색어: {args.query}")
    print(f"검색된 청크 수: {result['hits']['total']['value']}")

    for rank, hit in enumerate(result["hits"]["hits"], start=1):
        source = hit["_source"]
        preview = " ".join(source["content"].split())[:160]
        print(f"\n{rank}. BM25 점수={hit['_score']:.4f}")
        print(f"   문서: {source['document_title']}")
        print(f"   소제목: {source['heading']}")
        print(f"   내용: {preview}...")


if __name__ == "__main__":
    main()
