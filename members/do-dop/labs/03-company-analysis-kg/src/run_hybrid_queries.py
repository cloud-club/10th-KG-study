#!/usr/bin/env python3
"""BM25와 벡터 검색 결과를 RRF로 융합하고 Hit@5·Recall@5를 기록한다."""

import argparse
import json
from pathlib import Path

import common_path  # noqa: F401
from index_es import DEFAULT_INDEX
from index_pgvector import DEFAULT_DSN
from search_common.elasticsearch import DEFAULT_ES_URL
from search_common.embeddings import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, embed
from search_common.evaluation import evaluate_at_k
from search_common.jsonl import write_jsonl
from search_common.rrf import reciprocal_rank_fusion
from search_es import search_chunks as search_bm25_chunks
from search_pgvector import search_chunks as search_vector_chunks

try:
    import psycopg
except ImportError as error:
    raise SystemExit("pgvector 단계는 `pip install -r requirements.txt`가 필요합니다.") from error


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_QUERIES = Path(__file__).resolve().parents[1] / "config" / "evaluation_queries.json"
DEFAULT_OUTPUT = ROOT / "data" / "do-dop" / "company-analysis-kg" / "results" / "hybrid.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--es-url", default=DEFAULT_ES_URL)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument(
        "--pool-size", type=int, default=20,
        help="RRF로 합치기 전 BM25·벡터 각각에서 가져올 후보 개수",
    )
    parser.add_argument("--size", type=int, default=5, help="평가에 쓸 최종 top-k")
    parser.add_argument("--rrf-k", type=int, default=60)
    args = parser.parse_args()

    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    rows = []
    with psycopg.connect(args.dsn) as conn:
        for query in queries:
            bm25_results = search_bm25_chunks(args.es_url, args.index, query["query"], args.pool_size)
            bm25_ids = [item["id"] for item in bm25_results]

            query_vector = embed(query["query"], model=args.model, ollama_url=args.ollama_url)
            vector_results = search_vector_chunks(conn, query_vector, args.pool_size)
            vector_ids = [item["id"] for item in vector_results]

            fused = reciprocal_rank_fusion([bm25_ids, vector_ids], k=args.rrf_k)[: args.size]
            retrieved = [doc_id for doc_id, _ in fused]

            rows.append(
                {
                    "query_id": query["id"],
                    "query": query["query"],
                    "bm25_chunk_ids": bm25_ids[: args.size],
                    "vector_chunk_ids": vector_ids[: args.size],
                    "retrieved_chunk_ids": retrieved,
                    "scores": [round(score, 6) for _, score in fused],
                    **evaluate_at_k(retrieved, query["relevant_chunk_ids"], args.size),
                }
            )
    write_jsonl(args.output, rows)
    print(f"질의 {len(rows)}개 결과 저장: {args.output}")


if __name__ == "__main__":
    main()
