"""BM25, 벡터, RRF 하이브리드 검색에서 공유하는 함수."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import psycopg
import requests
from sentence_transformers import SentenceTransformer

from index_pgvector import MODEL_NAME, vector_literal

DEFAULT_ES_HOST = "http://127.0.0.1:9201"
DEFAULT_ES_INDEX = "kakao_chunks"
DEFAULT_DSN = "postgresql://study:study@127.0.0.1:5433/search_study"


def search_bm25(query: str, top_k: int, host: str = DEFAULT_ES_HOST, index: str = DEFAULT_ES_INDEX) -> list[dict[str, Any]]:
    """Elasticsearch BM25 상위 결과를 공통 형식으로 반환한다."""
    response = requests.get(
        f"{host}/{index}/_search",
        json={"size": top_k, "query": {"match": {"content": query}}},
        timeout=30,
    )
    response.raise_for_status()
    return [
        {"id": hit["_source"]["id"], "date": hit["_source"]["date"], "content": hit["_source"]["content"], "score": float(hit["_score"])}
        for hit in response.json()["hits"]["hits"]
    ]


def search_vector(query: str, top_k: int, model: SentenceTransformer, dsn: str = DEFAULT_DSN) -> list[dict[str, Any]]:
    """질문 임베딩과 pgvector 코사인 유사도로 상위 결과를 반환한다."""
    vector = model.encode([f"query: {query}"], normalize_embeddings=True)[0]
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute("SET hnsw.ef_search = 100")
        cursor.execute(
            "SELECT id, date, content, 1 - (embedding <=> %s::vector) AS cosine_similarity "
            "FROM document_chunks ORDER BY embedding <=> %s::vector LIMIT %s",
            (vector_literal(vector), vector_literal(vector), top_k),
        )
        rows = cursor.fetchall()
    return [{"id": row[0], "date": row[1], "content": row[2], "score": float(row[3])} for row in rows]


def reciprocal_rank_fusion(*rankings: list[dict[str, Any]], rank_constant: int = 60, top_k: int = 5) -> list[dict[str, Any]]:
    """여러 결과 목록을 RRF 점수로 융합한다. 각 목록의 1위는 rank 1이다."""
    if rank_constant < 1:
        raise ValueError("rank_constant는 1 이상이어야 합니다.")
    fused: dict[str, dict[str, Any]] = {}
    scores: defaultdict[str, float] = defaultdict(float)
    origins: defaultdict[str, list[str]] = defaultdict(list)
    for ranking_index, ranking in enumerate(rankings):
        name = ("bm25", "vector")[ranking_index] if ranking_index < 2 else f"retriever_{ranking_index + 1}"
        for rank, item in enumerate(ranking, start=1):
            item_id = item["id"]
            fused.setdefault(item_id, {key: item[key] for key in ("id", "date", "content")})
            scores[item_id] += 1 / (rank_constant + rank)
            origins[item_id].append(f"{name}:{rank}")
    result = [{**item, "score": scores[item_id], "origins": origins[item_id]} for item_id, item in fused.items()]
    return sorted(result, key=lambda item: (-item["score"], item["id"]))[:top_k]


def search_hybrid(query: str, top_k: int, rank_window: int, model: SentenceTransformer, rank_constant: int = 60, host: str = DEFAULT_ES_HOST, index: str = DEFAULT_ES_INDEX, dsn: str = DEFAULT_DSN) -> list[dict[str, Any]]:
    """BM25와 벡터 결과를 각각 rank_window개 가져와 RRF로 융합한다."""
    if rank_window < top_k:
        raise ValueError("rank_window은 top_k 이상이어야 합니다.")
    bm25 = search_bm25(query, rank_window, host=host, index=index)
    vector = search_vector(query, rank_window, model=model, dsn=dsn)
    return reciprocal_rank_fusion(bm25, vector, rank_constant=rank_constant, top_k=top_k)


def load_embedding_model(model_name: str = MODEL_NAME) -> SentenceTransformer:
    """검색·평가 실행 중 임베딩 모델을 한 번만 로드한다."""
    return SentenceTransformer(model_name)
