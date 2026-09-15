#!/usr/bin/env python3
"""nori와 n-gram 분석기가 같은 문장을 어떻게 토큰화하는지 나란히 비교한다.

인덱스에 정의된 nori_analyzer / ngram_analyzer를 `_analyze` API로 호출한다.
개인 대화 원문이 아니라 직접 입력한 예시 문장에만 사용한다.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_INDEX = "do-dop-kakao-messages"
DEFAULT_ES_URL = "http://localhost:9200"
ANALYZERS = {"nori": "nori_analyzer", "ngram": "ngram_analyzer"}


def analyze(es_url: str, index_name: str, analyzer: str, text: str) -> list[str]:
    # 지정한 분석기로 문장을 나눠 달라고 Elasticsearch에 요청한다.
    body = {"analyzer": analyzer, "text": text}
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{es_url}/{index_name}/_analyze", data=payload, method="POST"
    )
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"POST {es_url}/{index_name}/_analyze -> HTTP {error.code}: {detail}"
        ) from error
    # 위치·품사 같은 부가 정보는 빼고 생성된 토큰 문자열만 반환한다.
    return [token["token"] for token in result.get("tokens", [])]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="같은 문장을 nori와 ngram 분석기로 각각 토큰화해 비교합니다."
    )
    parser.add_argument("text", help="분석할 예시 문장 (개인 대화 원문 대신 직접 지은 예시 권장)")
    parser.add_argument("--index", default=DEFAULT_INDEX, help="색인 이름")
    parser.add_argument("--es-url", default=DEFAULT_ES_URL, help="Elasticsearch base URL")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    print(f"입력: {args.text}")
    # 같은 문장을 두 분석기에 넣어 토큰 결과를 나란히 출력한다.
    for label, analyzer in ANALYZERS.items():
        tokens = analyze(args.es_url, args.index, analyzer, args.text)
        print(f"  {label:5s} ({analyzer}): {tokens}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
