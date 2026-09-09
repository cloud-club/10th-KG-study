"""Elasticsearch BM25로 청크를 검색한다."""
from __future__ import annotations
import argparse
import requests

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query"); parser.add_argument("--host", default="http://127.0.0.1:9201"); parser.add_argument("--index", default="kakao_chunks"); parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    response = requests.get(f"{args.host}/{args.index}/_search", json={"size": args.top_k, "query": {"match": {"content": args.query}}}, timeout=30)
    response.raise_for_status()
    for rank, hit in enumerate(response.json()["hits"]["hits"], 1):
        source = hit["_source"]; print(f"{rank}. score={hit['_score']:.3f} id={source['id']} date={source['date']}"); print(f"   {source['content'].replace(chr(10), ' ')[:180]}")

if __name__ == "__main__": main()
