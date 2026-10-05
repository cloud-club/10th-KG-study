"""Search Elasticsearch BM25 and dense vectors, then fuse ranks with RRF."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

LABS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LABS / "02-rag-hybrid"))
from rag_retriever import reciprocal_rank_fusion

INDEX_NAME = "jjinthung-talk-chunks"


def search(
    query: str,
    index_dir: Path,
    top_k: int,
    candidate_k: int,
    es_url: str = "http://localhost:9200",
    es_index: str = INDEX_NAME,
) -> list[dict]:
    bm25_data = json.loads((index_dir / "bm25.json").read_text(encoding="utf-8"))
    records = bm25_data["documents"]
    vectors = np.load(index_dir / "vectors.npy")
    metadata = json.loads((index_dir / "metadata.json").read_text(encoding="utf-8"))
    if len(records) != len(vectors):
        raise ValueError("BM25 문서와 vector 수가 일치하지 않습니다.")

    record_indexes = {record["id"]: index for index, record in enumerate(records)}
    client = Elasticsearch(es_url)
    if not client.ping():
        raise RuntimeError("Elasticsearch에 연결할 수 없습니다.")
    response = client.search(
        index=es_index,
        size=min(candidate_k, len(records)),
        query={"match": {"text": {"query": query}}},
    )
    bm25_results = [
        (record_indexes[hit["_source"]["id"]], float(hit["_score"] or 0.0))
        for hit in response["hits"]["hits"]
    ]

    model = SentenceTransformer(metadata["model"])
    query_vector = model.encode([query], normalize_embeddings=True)[0]
    vector_results = sorted(
        enumerate(vectors @ query_vector),
        key=lambda item: (-float(item[1]), item[0]),
    )[:candidate_k]
    fused = reciprocal_rank_fusion(
        (
            [index for index, _ in bm25_results],
            [index for index, _ in vector_results],
        ),
        min(top_k, len(records)),
    )
    bm25_scores = dict(bm25_results)
    vector_scores = {index: float(score) for index, score in vector_results}
    return [
        {
            "rank": rank,
            "rrf_score": rrf_score,
            "bm25_score": bm25_scores.get(index, 0.0),
            "vector_score": vector_scores.get(index, 0.0),
            **records[index],
        }
        for rank, (index, rrf_score) in enumerate(fused, start=1)
    ]
