"""두 검색기를 같은 조건으로 실행하고 애플리케이션 계층에서 RRF로 합친다."""
from __future__ import annotations

from time import perf_counter

from common import RRF_CANDIDATE_K, RRF_RANK_CONSTANT, get_es, get_pg, validate_search_settings
from embedding import QueryEmbedder
from models import SearchFilters, SearchRun
from privacy import mask_query
from retrieval import assert_corpus_aligned, bm25_search, corpus_counts, fetch_chunks, vector_search
from rrf import reciprocal_rank_fusion


class HybridSearchEngine:
    def __init__(self, *, embedder: QueryEmbedder | None = None) -> None:
        validate_search_settings()
        self.es = get_es()
        self.conn = get_pg()
        self.embedder = embedder or QueryEmbedder()

    def close(self) -> None:
        self.conn.close()
        self.es.close()

    def __enter__(self) -> "HybridSearchEngine":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def preflight(self) -> dict[str, int]:
        counts = corpus_counts(self.conn, self.es)
        assert_corpus_aligned(counts)
        return counts

    def search(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        candidate_k: int = RRF_CANDIDATE_K,
        rank_constant: int = RRF_RANK_CONSTANT,
        exact_vector: bool = False,
    ) -> SearchRun:
        if not query.strip():
            raise ValueError("빈 질문은 검색할 수 없습니다.")
        filters = filters or SearchFilters()
        masked = mask_query(query.strip())

        started = perf_counter()
        bm25 = bm25_search(self.es, self.conn, masked, candidate_k, filters)
        bm25_done = perf_counter()
        query_vector = self.embedder.embed_one(masked)
        embedded = perf_counter()
        vector = vector_search(
            self.conn,
            query_vector,
            candidate_k,
            filters,
            exact=exact_vector,
        )
        vector_done = perf_counter()
        hybrid = reciprocal_rank_fusion(
            {"bm25": bm25, "vector": vector},
            rank_constant=rank_constant,
        )
        fused = perf_counter()

        chunk_ids = [hit.chunk_id for hit in bm25]
        chunk_ids.extend(hit.chunk_id for hit in vector)
        chunks = fetch_chunks(self.conn, chunk_ids)
        return SearchRun(
            original_query=query,
            masked_query=masked,
            bm25=tuple(bm25),
            vector=tuple(vector),
            hybrid=tuple(hybrid),
            chunks=chunks,
            timings_ms={
                "bm25": (bm25_done - started) * 1000,
                "embedding": (embedded - bm25_done) * 1000,
                "vector": (vector_done - embedded) * 1000,
                "rrf": (fused - vector_done) * 1000,
                "total": (fused - started) * 1000,
            },
        )
