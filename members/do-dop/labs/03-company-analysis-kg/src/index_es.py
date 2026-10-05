#!/usr/bin/env python3
"""기업분석 청크를 Nori 분석기 기반 Elasticsearch 인덱스에 저장한다."""

import argparse
from pathlib import Path

import common_path  # noqa: F401
from search_common.elasticsearch import DEFAULT_ES_URL, bulk_index, create_index
from search_common.jsonl import read_jsonl


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_INPUT = ROOT / "data" / "do-dop" / "company-analysis-kg" / "processed" / "chunks.jsonl"
DEFAULT_INDEX = "do-dop-company-analysis-chunks"
INDEX_BODY = {
    "settings": {
        "analysis": {
            "tokenizer": {"nori_mixed": {"type": "nori_tokenizer", "decompound_mode": "mixed"}},
            "analyzer": {
                "nori_analyzer": {
                    "type": "custom",
                    "tokenizer": "nori_mixed",
                    "filter": ["nori_readingform", "lowercase"],
                }
            },
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "document_id": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "nori_analyzer"},
            "company": {"type": "keyword"},
            "source": {"type": "keyword"},
            "date": {"type": "date"},
            "text": {"type": "text", "analyzer": "nori_analyzer"},
            "url": {"type": "keyword", "index": False},
        }
    },
}


def to_es_document(chunk: dict) -> dict:
    return {
        "_id": chunk["id"],
        "id": chunk["id"],
        "document_id": chunk["document_id"],
        "title": chunk["title"],
        "company": chunk["company"],
        "source": chunk["source"],
        "date": chunk["date"],
        "text": chunk["text"],
        "url": chunk["url"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--es-url", default=DEFAULT_ES_URL)
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()

    chunks = read_jsonl(args.input)
    create_index(args.es_url, args.index, INDEX_BODY, args.recreate)
    indexed, errors = bulk_index(args.es_url, args.index, (to_es_document(chunk) for chunk in chunks))
    print(f"인덱스: {args.index}, 성공: {indexed}, 실패: {errors}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

