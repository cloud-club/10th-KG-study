"""Elasticsearch의 JSON HTTP API를 호출하는 공통 함수."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterable, Iterator


DEFAULT_ES_URL = "http://localhost:9200"


def request_json(url: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request) as response:
            content = response.read()
            return json.loads(content.decode("utf-8")) if content else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> HTTP {error.code}: {detail}") from error


def index_exists(es_url: str, index_name: str) -> bool:
    request = urllib.request.Request(f"{es_url}/{index_name}", method="HEAD")
    try:
        urllib.request.urlopen(request)
        return True
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise


def create_index(es_url: str, index_name: str, body: dict, recreate: bool = False) -> None:
    exists = index_exists(es_url, index_name)
    if exists and recreate:
        request_json(f"{es_url}/{index_name}", method="DELETE")
        exists = False
    if exists:
        raise RuntimeError(f"인덱스가 이미 있습니다: {index_name} (--recreate 사용 가능)")
    request_json(f"{es_url}/{index_name}", method="PUT", body=body)


def batched(rows: list[dict], size: int) -> Iterator[list[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def bulk_index(es_url: str, index_name: str, documents: Iterable[dict], batch_size: int = 500) -> tuple[int, int]:
    rows = list(documents)
    indexed = 0
    errors = 0
    for batch in batched(rows, batch_size):
        lines = []
        for document in batch:
            source = dict(document)
            document_id = str(source.pop("_id"))
            lines.append(json.dumps({"index": {"_index": index_name, "_id": document_id}}, ensure_ascii=False))
            lines.append(json.dumps(source, ensure_ascii=False))
        payload = ("\n".join(lines) + "\n").encode("utf-8")
        request = urllib.request.Request(f"{es_url}/_bulk", data=payload, method="POST")
        request.add_header("Content-Type", "application/x-ndjson")
        try:
            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"POST {es_url}/_bulk -> HTTP {error.code}: {detail}") from error
        for item in result.get("items", []):
            status = item.get("index", {}).get("status", 500)
            if status < 300:
                indexed += 1
            else:
                errors += 1
    request_json(f"{es_url}/{index_name}/_refresh", method="POST")
    return indexed, errors


def search(es_url: str, index_name: str, body: dict) -> dict:
    return request_json(f"{es_url}/{index_name}/_search", method="POST", body=body)
