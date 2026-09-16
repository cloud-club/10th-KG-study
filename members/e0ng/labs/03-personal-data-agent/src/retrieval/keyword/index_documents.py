#!/usr/bin/env python3
"""Notion 문서 청크를 Elasticsearch BM25 인덱스에 저장한다."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from elasticsearch import Elasticsearch, helpers


SRC_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_DIR))

from common import DOCUMENTS_PATH, get_env, load_documents


INDEX = "personal-documents"
REQUIRED_FIELDS = {"id", "page_id", "title", "content", "source", "chunk_index"}
MAPPINGS = {
    "dynamic": "strict",
    "properties": {
        "id": {"type": "keyword"},
        "page_id": {"type": "keyword"},
        "title": {"type": "text", "analyzer": "nori"},
        "content": {"type": "text", "analyzer": "nori"},
        "source": {"type": "keyword"},
        "chunk_index": {"type": "integer"},
    },
}


def wait_until_ready(client: Elasticsearch, timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if client.ping():
            return
        time.sleep(2)
    raise RuntimeError(
        "Elasticsearch가 준비되지 않았습니다. 'docker compose ps'와 "
        "'docker compose logs elasticsearch'를 확인하세요."
    )


def validate_documents(documents: list[dict]) -> None:
    if not documents:
        raise ValueError("색인할 문서가 없습니다.")

    seen_ids: set[str] = set()
    for line_number, document in enumerate(documents, start=1):
        missing = REQUIRED_FIELDS - document.keys()
        if missing:
            raise ValueError(f"JSONL {line_number}행에 필드가 없습니다: {sorted(missing)}")
        if document["id"] in seen_ids:
            raise ValueError(f"중복된 문서 id입니다: {document['id']}")
        seen_ids.add(document["id"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Notion 청크를 Elasticsearch에 색인합니다.")
    parser.add_argument("--input", type=Path, default=DOCUMENTS_PATH)
    parser.add_argument("--keep-index", action="store_true", help="기존 인덱스를 삭제하지 않음")
    args = parser.parse_args()

    documents = load_documents(args.input)
    validate_documents(documents)

    client = Elasticsearch(get_env("ES_URL", "http://localhost:9200"))
    wait_until_ready(client)

    if client.indices.exists(index=INDEX) and not args.keep_index:
        client.indices.delete(index=INDEX)
    if not client.indices.exists(index=INDEX):
        client.indices.create(index=INDEX, mappings=MAPPINGS)

    actions = (
        {"_index": INDEX, "_id": document["id"], "_source": document}
        for document in documents
    )
    success, _ = helpers.bulk(client, actions)
    client.indices.refresh(index=INDEX)
    count = client.count(index=INDEX)["count"]
    print(f"Elasticsearch 색인 완료: 요청 {success}개, 인덱스 문서 {count}개")


if __name__ == "__main__":
    main()
