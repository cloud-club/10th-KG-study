"""chunks.jsonl 을 Elasticsearch(nori) BM25 인덱스에 적재한다."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from common import ES_INDEX, ES_URL
from search_grep import load_chunks

INDEX_CONFIG = {
    "settings": {
        "analysis": {
            "analyzer": {
                "korean": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["nori_part_of_speech", "nori_readingform", "lowercase"],
                }
            }
        }
    },
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "chunk_id": {"type": "keyword"},
            "source_path": {"type": "keyword"},
            "doc_type": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "korean"},
            "heading": {"type": "keyword"},
            "content": {"type": "text", "analyzer": "korean"},
            "date": {"type": "date", "ignore_malformed": True},
            "tags": {"type": "keyword"},
        },
    },
}


def request(method: str, path: str, body: Any = None, content_type: str = "application/json") -> dict[str, Any]:
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(
        f"{ES_URL}/{path.lstrip('/')}",
        data=data,
        method=method,
        headers={"Content-Type": content_type, "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Elasticsearch 요청 실패(HTTP {error.code}): {detail[:500]}") from error
    except URLError as error:
        raise RuntimeError(f"Elasticsearch에 연결할 수 없습니다: {ES_URL}") from error


def es_document(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": chunk["chunk_id"],
        "source_path": chunk["source_path"],
        "doc_type": chunk["doc_type"],
        "title": chunk["title"],
        "heading": chunk["heading"],
        "content": chunk["content"],
        "date": chunk["date"],
        "tags": chunk["tags"],
    }


def index_chunks(chunks: list[dict[str, Any]] | None = None, index_name: str = ES_INDEX) -> int:
    chunks = chunks if chunks is not None else load_chunks()
    try:
        request("DELETE", index_name)
    except RuntimeError as error:
        if "HTTP 404" not in str(error):
            raise
    request("PUT", index_name, INDEX_CONFIG)

    lines: list[str] = []
    for chunk in chunks:
        lines.append(json.dumps({"index": {"_index": index_name, "_id": chunk["chunk_id"]}}))
        lines.append(json.dumps(es_document(chunk), ensure_ascii=False))
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    response = request("POST", "_bulk", payload, "application/x-ndjson")
    if response.get("errors"):
        failures = [item for item in response.get("items", []) if item.get("index", {}).get("error")]
        raise RuntimeError(f"Elasticsearch bulk 적재 실패: {len(failures)}건 — {failures[:1]}")
    request("POST", f"{index_name}/_refresh")
    return request("GET", f"{index_name}/_count")["count"]


def main() -> None:
    count = index_chunks()
    print(f"[Elasticsearch] 적재 완료: {count}청크")
    print(f"인덱스: {ES_INDEX}")
    print("분석기: nori(mixed 미사용, part_of_speech+readingform)")


if __name__ == "__main__":
    main()
