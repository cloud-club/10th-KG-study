#!/usr/bin/env python3
"""Elasticsearch에 색인된 카카오톡 메시지를 BM25로 검색한다.

`--field text`(nori 분석)와 `--field text.ngram`(n-gram 분석)을 각각 지정해
같은 질의에서 두 토크나이저의 결과를 비교할 수 있다.

search_grep.sh와 같은 원칙으로, 기본 출력에는 원문을 포함하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_INDEX = "do-dop-kakao-messages"
DEFAULT_ES_URL = "http://localhost:9200"
FIELD_CHOICES = ["text", "text.ngram"]


def build_search_body(
    query: str, field: str, size: int, match_type: str = "match"
) -> dict:
    # Elasticsearch에 보낼 검색 JSON을 만든다.
    if match_type not in ("match", "match_phrase"):
        raise ValueError(f"알 수 없는 match_type: {match_type}")
    return {
        "size": size,
        "query": {match_type: {field: query}},
    }


def http_search(es_url: str, index_name: str, body: dict) -> dict:
    # 파이썬 전용 클라이언트 없이 표준 라이브러리로 _search API를 호출한다.
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{es_url}/{index_name}/_search", data=payload, method="POST"
    )
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"POST {es_url}/{index_name}/_search -> HTTP {error.code}: {detail}"
        ) from error


def parse_hits(response: dict) -> list[dict]:
    # Elasticsearch 응답에서 실습에 필요한 값만 꺼낸다.
    hits = response.get("hits", {}).get("hits", [])
    results = []
    for hit in hits:
        source = hit.get("_source", {})
        results.append(
            {
                "chunk_id": source.get("chunk_id"),
                "sender_id": source.get("sender_id"),
                "sent_at": source.get("sent_at"),
                "score": hit.get("_score"),
                "text": source.get("text"),
            }
        )
    return results


def total_hits(response: dict) -> int:
    # 검색 조건에 맞는 전체 문서 수를 반환한다.
    total = response.get("hits", {}).get("total", {})
    if isinstance(total, dict):
        return int(total.get("value", 0))
    return int(total)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Elasticsearch BM25로 카카오톡 메시지를 검색합니다."
    )
    parser.add_argument("query", help="검색어")
    parser.add_argument(
        "--field",
        choices=FIELD_CHOICES,
        default="text",
        help="text(nori) 또는 text.ngram(n-gram) 필드로 검색 (기본: text)",
    )
    parser.add_argument(
        "--match-phrase",
        action="store_true",
        help="개별 토큰 OR 매칭(match) 대신 구문 일치(match_phrase)로 검색",
    )
    parser.add_argument("--index", default=DEFAULT_INDEX, help="색인 이름")
    parser.add_argument("--es-url", default=DEFAULT_ES_URL, help="Elasticsearch base URL")
    parser.add_argument("--size", type=int, default=5, help="반환할 결과 수 (기본 5)")
    parser.add_argument(
        "--show", action="store_true", help="원문 일부를 함께 출력합니다 (기본은 건수/점수만)"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    # --match-phrase를 주지 않으면 기본 match 쿼리를 사용한다.
    match_type = "match_phrase" if args.match_phrase else "match"
    body = build_search_body(args.query, args.field, args.size, match_type)
    response = http_search(args.es_url, args.index, body)
    hits = parse_hits(response)

    print(f"필드: {args.field} ({match_type})")
    print(f"전체 일치: {total_hits(response)}")
    print(f"상위 {len(hits)}개:")
    # Elasticsearch가 계산한 BM25 점수가 높은 결과부터 출력한다.
    for rank, hit in enumerate(hits, start=1):
        if args.show:
            snippet = (hit["text"] or "")[:40]
            print(f"  {rank}. score={hit['score']:.4f} sender={hit['sender_id']} text={snippet!r}")
        else:
            print(f"  {rank}. score={hit['score']:.4f} sender={hit['sender_id']} chunk={hit['chunk_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
