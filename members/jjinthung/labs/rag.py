#!/usr/bin/env python3
"""저장된 BM25 JSON과 vector 인덱스를 함께 검색합니다. LLM은 사용하지 않습니다."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from elasticsearch import Elasticsearch
import numpy as np
from sentence_transformers import SentenceTransformer

_HYBRID_DIR = Path(__file__).resolve().parent / "02-rag-hybrid"
sys.path.insert(0, str(_HYBRID_DIR))
from rag_retriever import reciprocal_rank_fusion  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

INDEX_NAME = "jjinthung-talk-chunks"


def main() -> None:
    parser = argparse.ArgumentParser(description="저장된 BM25 + vector 인덱스 검색")
    parser.add_argument("query")
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "Data" / "index",
    )
    parser.add_argument("--es-url", default=os.getenv("ES_URL", "http://localhost:9200"))
    parser.add_argument("--es-index", default=INDEX_NAME)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=30)
    args = parser.parse_args()

    bm25_path = args.index_dir / "bm25.json"
    vectors_path = args.index_dir / "vectors.npy"
    metadata_path = args.index_dir / "metadata.json"
    for path in (bm25_path, vectors_path, metadata_path):
        if not path.exists():
            raise FileNotFoundError(
                f"인덱스가 없습니다: {path}. 먼저 build_index.py를 실행하세요."
            )

    index = json.loads(bm25_path.read_text(encoding="utf-8"))
    records = index["documents"]
    record_indexes = {record["id"]: index for index, record in enumerate(records)}
    vectors = np.load(vectors_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if len(records) != len(vectors):
        raise ValueError("BM25 문서 수와 vector 수가 일치하지 않습니다.")

    candidate_k = min(args.candidate_k, len(records))
    client = Elasticsearch(args.es_url)
    if not client.ping():
        raise RuntimeError(
            "Elasticsearch에 연결할 수 없습니다. 먼저 "
            "'docker compose up -d elasticsearch'를 실행하세요."
        )
    response = client.search(
        index=args.es_index,
        size=candidate_k,
        query={"match": {"text": {"query": args.query}}},
    )
    bm25_results = [
        (
            record_indexes[hit["_source"]["id"]],
            float(hit["_score"] or 0.0),
        )
        for hit in response["hits"]["hits"]
    ]
    model = SentenceTransformer(metadata["model"])
    query_vector = model.encode([args.query], normalize_embeddings=True)[0]
    vector_results = sorted(
        enumerate(vectors @ query_vector),
        key=lambda item: (-float(item[1]), item[0]),
    )[:candidate_k]
    fused = reciprocal_rank_fusion(
        ([index for index, _ in bm25_results], [index for index, _ in vector_results]),
        min(args.top_k, len(records)),
    )
    bm25_scores = dict(bm25_results)
    vector_scores = {index: float(score) for index, score in vector_results}
    for rank, (index, rrf_score) in enumerate(fused, start=1):
        print(
            json.dumps(
                {
                    "rank": rank,
                    "rrf_score": rrf_score,
                    "bm25_score": bm25_scores.get(index, 0.0),
                    "vector_score": vector_scores.get(index, 0.0),
                    **records[index],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
