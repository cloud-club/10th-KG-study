#!/usr/bin/env python3
"""익명화된 카카오톡 메시지 JSONL을 Elasticsearch에 색인한다.

nori 형태소 분석기와 n-gram 분석기를 각각 적용한 두 필드(`text`, `text.ngram`)를
같은 문서에 함께 저장해 같은 질의로 두 토크나이저를 비교할 수 있게 한다.

외부 라이브러리 없이 표준 라이브러리(urllib)만 사용한다.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable, Iterator

DEFAULT_INDEX = "do-dop-kakao-messages"
DEFAULT_ES_URL = "http://localhost:9200"
BULK_BATCH_SIZE = 500

INDEX_BODY = {
    "settings": {
        # 2-gram만 사용하므로 min_gram과 max_gram의 차이는 0이다.
        "index": {"max_ngram_diff": 1},
        "analysis": {
            "tokenizer": {
                # 한국어 문장을 형태소 단위로 나누는 nori 토크나이저다.
                "nori_mixed": {
                    "type": "nori_tokenizer",
                    "decompound_mode": "mixed",
                },
                # 문장을 연속된 두 글자 단위로 나누는 토크나이저다.
                "bigram": {
                    "type": "ngram",
                    "min_gram": 2,
                    "max_gram": 2,
                    "token_chars": ["letter", "digit"],
                },
            },
            "analyzer": {
                # nori 토큰에 읽기 형태 변환과 영문 소문자화를 적용한다.
                "nori_analyzer": {
                    "type": "custom",
                    "tokenizer": "nori_mixed",
                    "filter": ["nori_readingform", "lowercase"],
                },
                # 2-gram 토큰의 영문을 소문자로 통일한다.
                "ngram_analyzer": {
                    "type": "custom",
                    "tokenizer": "bigram",
                    "filter": ["lowercase"],
                },
            },
        },
    },
    "mappings": {
        "properties": {
            # keyword는 값을 토큰화하지 않고 정확한 값 그대로 저장한다.
            "chunk_id": {"type": "keyword"},
            "sender_id": {"type": "keyword"},
            "sent_at": {"type": "date"},
            "text": {
                "type": "text",
                "analyzer": "nori_analyzer",
                # 같은 원문을 text.ngram이라는 별도 검색 필드로도 분석한다.
                "fields": {
                    "ngram": {"type": "text", "analyzer": "ngram_analyzer"},
                },
            },
        }
    },
}


def build_index_body() -> dict:
    # 인덱스를 만들 때 사용할 분석기와 필드 설정을 반환한다.
    return INDEX_BODY


def read_messages(input_path: Path) -> list[dict]:
    # JSONL 파일을 한 줄씩 읽어 메시지 문서 목록으로 만든다.
    messages = []
    with input_path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"{input_path}:{line_number} JSON 파싱 실패") from error
    return messages


def build_bulk_lines(messages: Iterable[dict], index_name: str) -> list[str]:
    """Elasticsearch _bulk NDJSON 형식의 줄 목록을 만든다 (액션 줄 + 문서 줄 반복)."""
    lines: list[str] = []
    for message in messages:
        # bulk API는 작업 정보 한 줄과 실제 문서 한 줄을 한 쌍으로 받는다.
        action = {"index": {"_index": index_name, "_id": message["chunk_id"]}}
        source = {
            "chunk_id": message["chunk_id"],
            "sender_id": message["sender_id"],
            "sent_at": message["sent_at"],
            "text": message["text"],
        }
        lines.append(json.dumps(action, ensure_ascii=False))
        lines.append(json.dumps(source, ensure_ascii=False))
    return lines


def batched(lines: list[str], batch_size: int) -> Iterator[list[str]]:
    # 액션 줄 + 문서 줄이 한 쌍이므로 문서 개수 기준 배치 크기의 2배씩 자른다.
    step = batch_size * 2
    for start in range(0, len(lines), step):
        yield lines[start : start + step]


def http_request(
    url: str, method: str = "GET", body: dict | None = None
) -> dict:
    # 인덱스 생성·삭제·새로고침에 사용하는 일반 JSON 요청 함수다.
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> HTTP {error.code}: {detail}") from error


def http_bulk(es_url: str, lines: list[str]) -> dict:
    # 여러 문서를 한 번에 저장하는 Elasticsearch _bulk API를 호출한다.
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    request = urllib.request.Request(
        f"{es_url}/_bulk", data=payload, method="POST"
    )
    request.add_header("Content-Type", "application/x-ndjson")
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {es_url}/_bulk -> HTTP {error.code}: {detail}") from error


def index_exists(es_url: str, index_name: str) -> bool:
    # 본문을 받지 않는 HEAD 요청으로 같은 이름의 인덱스가 있는지 확인한다.
    request = urllib.request.Request(f"{es_url}/{index_name}", method="HEAD")
    try:
        urllib.request.urlopen(request)
        return True
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise


def create_index(es_url: str, index_name: str, recreate: bool) -> None:
    # --recreate가 있으면 기존 인덱스를 지운 뒤 설정대로 다시 만든다.
    exists = index_exists(es_url, index_name)
    if exists and recreate:
        http_request(f"{es_url}/{index_name}", method="DELETE")
        exists = False
    if exists:
        raise RuntimeError(
            f"인덱스가 이미 있습니다: {index_name} (--recreate로 삭제 후 재생성)"
        )
    http_request(f"{es_url}/{index_name}", method="PUT", body=build_index_body())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="카카오톡 메시지 JSONL을 Elasticsearch(nori + ngram)에 색인합니다."
    )
    parser.add_argument("--input", required=True, type=Path, help="messages.jsonl 경로")
    parser.add_argument("--index", default=DEFAULT_INDEX, help="색인 이름")
    parser.add_argument("--es-url", default=DEFAULT_ES_URL, help="Elasticsearch base URL")
    parser.add_argument(
        "--recreate", action="store_true", help="기존 인덱스를 삭제하고 새로 만든다"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = args.input.resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")

    # 파싱된 메시지를 읽고 nori·2-gram 설정을 가진 인덱스를 생성한다.
    messages = read_messages(input_path)
    if not messages:
        raise ValueError("색인할 메시지가 없습니다.")

    create_index(args.es_url, args.index, args.recreate)

    # 문서를 bulk 형식으로 만든 뒤 500개씩 나눠 전송한다.
    lines = build_bulk_lines(messages, args.index)
    indexed = 0
    errors = 0
    for batch in batched(lines, BULK_BATCH_SIZE):
        response = http_bulk(args.es_url, batch)
        for item in response.get("items", []):
            action_result = item.get("index", {})
            if action_result.get("status", 500) >= 300:
                errors += 1
            else:
                indexed += 1

    # 방금 넣은 문서가 곧바로 검색되도록 인덱스를 새로고침한다.
    http_request(f"{args.es_url}/{args.index}/_refresh", method="POST")

    print(f"인덱스: {args.index}")
    print(f"색인 성공: {indexed}")
    print(f"색인 실패: {errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
