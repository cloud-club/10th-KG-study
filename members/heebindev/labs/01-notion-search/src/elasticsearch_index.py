"""JSONL 청크를 Elasticsearch에 저장한다."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path


INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "source": {"type": "keyword"},
            "document_title": {"type": "text"},
            "heading": {"type": "text"},
            "content": {"type": "text"},
            "char_count": {"type": "integer"},
        }
    }
}


def request(
    method: str,
    url: str,
    body: bytes | None = None,
    content_type: str = "application/json",
) -> tuple[int, dict]:
    headers = {"Content-Type": content_type}
    http_request = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(http_request) as response:
            response_body = response.read()
            return response.status, json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Elasticsearch 요청 실패 ({error.code}): {error_body}") from error


def create_index_if_missing(elasticsearch_url: str, index_name: str) -> None:
    try:
        request("HEAD", f"{elasticsearch_url}/{index_name}")
        print(f"기존 인덱스를 사용합니다: {index_name}")
    except RuntimeError as error:
        if "(404)" not in str(error):
            raise
        body = json.dumps(INDEX_MAPPING).encode("utf-8")
        request("PUT", f"{elasticsearch_url}/{index_name}", body)
        print(f"새 인덱스를 생성했습니다: {index_name}")


def load_chunks(path: Path) -> list[dict]:
    chunks: list[dict] = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            chunk = json.loads(line)
            if "id" not in chunk or "content" not in chunk:
                raise ValueError(f"{line_number}번째 줄에 id 또는 content가 없습니다.")
            chunks.append(chunk)
    return chunks


def bulk_index(elasticsearch_url: str, index_name: str, chunks: list[dict]) -> None:
    lines: list[str] = []
    for chunk in chunks:
        lines.append(json.dumps({"index": {"_index": index_name, "_id": chunk["id"]}}))
        lines.append(json.dumps(chunk, ensure_ascii=False))

    body = ("\n".join(lines) + "\n").encode("utf-8")
    _, response = request(
        "POST",
        f"{elasticsearch_url}/_bulk?refresh=true",
        body,
        content_type="application/x-ndjson",
    )

    if response.get("errors"):
        failures = [
            item
            for item in response.get("items", [])
            if item.get("index", {}).get("error")
        ]
        raise RuntimeError(f"일부 문서 적재 실패: {failures[:3]}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="청크 JSONL 파일")
    parser.add_argument("--url", default="http://127.0.0.1:9200", help="Elasticsearch 주소")
    parser.add_argument("--index", default="notion_chunks", help="인덱스 이름")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    elasticsearch_url = args.url.rstrip("/")
    chunks = load_chunks(args.input)

    create_index_if_missing(elasticsearch_url, args.index)
    bulk_index(elasticsearch_url, args.index, chunks)

    _, count_result = request("GET", f"{elasticsearch_url}/{args.index}/_count")
    print(f"이번 실행에서 청크 {len(chunks)}개를 적재했습니다.")
    print(f"현재 저장된 문서 수: {count_result['count']}개")


if __name__ == "__main__":
    main()
