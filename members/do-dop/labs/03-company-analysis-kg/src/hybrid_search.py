"""BM25와 벡터 검색을 RRF로 합쳐 청크 내용까지 반환한다.

run_hybrid_queries.py는 청크 ID만으로 Recall@k를 계산하면 되지만, 챗봇은 LLM에
넘길 본문(title/text/url)이 필요하다. 그래서 융합된 ID를 chunks.jsonl에서 다시
찾아 원문을 붙여 돌려준다.
"""

from __future__ import annotations

from pathlib import Path

import common_path  # noqa: F401
from index_es import DEFAULT_INDEX
from search_common.elasticsearch import DEFAULT_ES_URL
from search_common.embeddings import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, embed
from search_common.jsonl import read_jsonl
from search_common.rrf import reciprocal_rank_fusion
from search_es import search_chunks as search_bm25_chunks
from search_pgvector import search_chunks as search_vector_chunks


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_CHUNKS_PATH = ROOT / "data" / "do-dop" / "company-analysis-kg" / "processed" / "chunks.jsonl"


def load_chunk_lookup(path: Path = DEFAULT_CHUNKS_PATH) -> dict[str, dict]:
    return {chunk["id"]: chunk for chunk in read_jsonl(path)}


def search_hybrid(
    conn,
    query: str,
    chunk_lookup: dict[str, dict],
    es_url: str = DEFAULT_ES_URL,
    index: str = DEFAULT_INDEX,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    pool_size: int = 20,
    size: int = 5,
    rrf_k: int = 60,
) -> list[dict]:
    bm25_ids = [item["id"] for item in search_bm25_chunks(es_url, index, query, pool_size)]

    query_vector = embed(query, model=model, ollama_url=ollama_url)
    vector_ids = [item["id"] for item in search_vector_chunks(conn, query_vector, pool_size)]

    fused = reciprocal_rank_fusion([bm25_ids, vector_ids], k=rrf_k)[:size]
    return [chunk_lookup[doc_id] for doc_id, _ in fused if doc_id in chunk_lookup]
