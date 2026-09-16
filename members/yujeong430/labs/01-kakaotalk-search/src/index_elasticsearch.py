"""청크 JSONL을 Elasticsearch의 BM25 인덱스에 적재한다."""

from __future__ import annotations
import argparse, json
from pathlib import Path
import requests

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True); parser.add_argument("--host", default="http://127.0.0.1:9201"); parser.add_argument("--index", default="kakao_chunks")
    args = parser.parse_args()
    chunks = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    mapping = {
        "settings": {
            "analysis": {
                "tokenizer": {"korean_nori_tokenizer": {"type": "nori_tokenizer"}},
                "analyzer": {"korean_nori": {"type": "custom", "tokenizer": "korean_nori_tokenizer", "filter": ["nori_part_of_speech"]}},
            }
        },
        "mappings": {"properties": {"id": {"type": "keyword"}, "date": {"type": "keyword"}, "source": {"type": "keyword"}, "message_count": {"type": "integer"}, "char_count": {"type": "integer"}, "content": {"type": "text", "analyzer": "korean_nori", "search_analyzer": "korean_nori"}}},
    }
    response = requests.delete(f"{args.host}/{args.index}", timeout=30)
    if response.status_code not in (200, 404): response.raise_for_status()
    response = requests.put(f"{args.host}/{args.index}", json=mapping, timeout=30)
    if response.status_code not in (200, 201): response.raise_for_status()
    lines = []
    for chunk in chunks:
        lines.extend([json.dumps({"index": {"_index": args.index, "_id": chunk["id"]}}), json.dumps(chunk, ensure_ascii=False)])
    response = requests.post(f"{args.host}/_bulk", data="\n".join(lines) + "\n", headers={"Content-Type": "application/x-ndjson"}, timeout=60)
    response.raise_for_status()
    if response.json().get("errors"): raise RuntimeError("Elasticsearch bulk 적재 중 오류가 발생했습니다.")
    requests.post(f"{args.host}/{args.index}/_refresh", timeout=30).raise_for_status()
    count = requests.get(f"{args.host}/{args.index}/_count", timeout=30).json()["count"]
    print(f"Elasticsearch BM25 인덱스: {args.index}"); print(f"적재 청크 수: {count}")

if __name__ == "__main__": main()
