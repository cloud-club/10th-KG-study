#!/usr/bin/env python3
import argparse
import sys
import time
from pathlib import Path

from elasticsearch import Elasticsearch, helpers

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_env, load_messages


INDEX = "chat-messages"


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


def main() -> None:
    parser = argparse.ArgumentParser(description="채팅 JSON을 Elasticsearch에 색인합니다.")
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()

    client = Elasticsearch(get_env("ES_URL", "http://localhost:9200"))
    wait_until_ready(client)
    if client.indices.exists(index=INDEX):
        client.indices.delete(index=INDEX)

    client.indices.create(
        index=INDEX,
        mappings={
            "properties": {
                "timestamp": {"type": "date"},
                "sender": {"type": "keyword"},
                "message": {"type": "text", "analyzer": "nori"},
            }
        },
    )
    messages = load_messages(args.input) if args.input else load_messages()
    actions = (
        {"_index": INDEX, "_id": number, "_source": message}
        for number, message in enumerate(messages, start=1)
    )
    success, _ = helpers.bulk(client, actions)
    client.indices.refresh(index=INDEX)
    print(f"Elasticsearch 색인 완료: {success}개")


if __name__ == "__main__":
    main()
