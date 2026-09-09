#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from elasticsearch import Elasticsearch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_env


INDEX = "chat-messages"


def main() -> None:
    parser = argparse.ArgumentParser(description="Elasticsearch BM25로 채팅을 검색합니다.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    client = Elasticsearch(get_env("ES_URL", "http://localhost:9200"))
    response = client.search(
        index=INDEX,
        size=args.limit,
        query={"match": {"message": {"query": args.query}}},
    )
    for rank, hit in enumerate(response["hits"]["hits"], start=1):
        source = hit["_source"]
        print(f"{rank}\t{hit['_score']:.6f}\t{source['timestamp']}\t{source['sender']}\t{source['message']}")


if __name__ == "__main__":
    main()
