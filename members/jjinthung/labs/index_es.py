#!/usr/bin/env python3
"""documents.jsonl의 청크를 Elasticsearch Nori BM25 인덱스에 저장합니다."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from elasticsearch import Elasticsearch, helpers

INDEX_NAME = "jjinthung-talk-chunks"


def wait_for_elasticsearch(client: Elasticsearch, timeout: int = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.ping():
            return
        time.sleep(2)
    raise RuntimeError(
        "Elasticsearch가 준비되지 않았습니다. 루트 폴더에서 "
        "'docker compose up -d elasticsearch'를 실행하세요."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="카카오톡 청크를 Nori BM25로 색인")
    parser.add_argument(
        "--documents",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "Data" / "documents.jsonl",
    )
    parser.add_argument("--url", default=os.getenv("ES_URL", "http://localhost:9200"))
    parser.add_argument("--index", default=INDEX_NAME)
    args = parser.parse_args()

    records = [
        json.loads(line)
        for line in args.documents.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    client = Elasticsearch(args.url)
    wait_for_elasticsearch(client)
    if client.indices.exists(index=args.index):
        client.indices.delete(index=args.index)
    client.indices.create(
        index=args.index,
        mappings={
            "properties": {
                "id": {"type": "keyword"},
                "start": {"type": "date"},
                "end": {"type": "date"},
                "message_count": {"type": "integer"},
                "text": {"type": "text", "analyzer": "nori"},
                "messages": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "date"},
                        "user": {"type": "keyword"},
                        "content": {"type": "text", "analyzer": "nori"},
                    },
                },
            }
        },
    )
    actions = (
        {"_index": args.index, "_id": record["id"], "_source": record}
        for record in records
    )
    success, _ = helpers.bulk(client, actions)
    client.indices.refresh(index=args.index)
    print(f"Elasticsearch Nori BM25 색인 완료: {success:,}개 ({args.index})")


if __name__ == "__main__":
    main()
