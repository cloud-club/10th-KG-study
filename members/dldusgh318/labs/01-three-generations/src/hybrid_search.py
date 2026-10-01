"""Elasticsearch BM25와 pgvector 결과를 RRF로 합친다.

사용:
    ./.venv/bin/python src/hybrid_search.py "캐시 전략"
"""
import argparse
from collections.abc import Iterable

from gen1_es import search_bm25
from gen2_pgvector import search_vector

RRF_K = 60
RETRIEVER_LIMIT = 50


def reciprocal_rank_fusion(
    rankings: Iterable[list[dict]], *, k: int = RRF_K, limit: int | None = None
) -> list[dict]:
    """원 점수는 버리고 각 검색기의 1-based rank만 합산한다."""
    if k < 0:
        raise ValueError("RRF k는 0 이상이어야 합니다.")
    fused: dict[str, dict] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for fallback_rank, item in enumerate(ranking, start=1):
            chunk_id = item["id"]
            if chunk_id in seen:
                raise ValueError(f"한 ranking 안에 ID가 중복되었습니다: {chunk_id}")
            seen.add(chunk_id)
            rank = int(item.get("rank", fallback_rank))
            if rank < 1:
                raise ValueError("rank는 1 이상이어야 합니다.")
            entry = fused.setdefault(chunk_id, {**item, "rrf_score": 0.0, "ranks": []})
            entry["rrf_score"] += 1.0 / (k + rank)
            entry["ranks"].append(rank)

    ordered = sorted(
        fused.values(),
        key=lambda row: (-row["rrf_score"], -len(row["ranks"]), min(row["ranks"]), row["id"]),
    )
    for rank, row in enumerate(ordered, start=1):
        row["rank"] = rank
    return ordered[:limit] if limit is not None else ordered


def fuse_search_results(bm25: list[dict], vector: list[dict], limit: int = 10) -> list[dict]:
    """이미 조회한 두 검색 결과를 RRF로 합친다."""
    bm25_ranks = {row["id"]: row["rank"] for row in bm25}
    vector_ranks = {row["id"]: row["rank"] for row in vector}
    results = reciprocal_rank_fusion([bm25, vector], limit=limit)
    for row in results:
        row["bm25_rank"] = bm25_ranks.get(row["id"])
        row["vector_rank"] = vector_ranks.get(row["id"])
    return results


def hybrid_search(query: str, limit: int = 10, retrieve_limit: int = RETRIEVER_LIMIT) -> list[dict]:
    bm25 = search_bm25(query, retrieve_limit)
    vector = search_vector(query, retrieve_limit)
    return fuse_search_results(bm25, vector, limit)


def main() -> None:
    parser = argparse.ArgumentParser(description="BM25 + Vector RRF 검색")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    print(f'Query: {args.query}')
    for row in hybrid_search(args.query, args.limit):
        print(f'{row["rank"]}. {row["id"]}')
        print(f'   RRF {row["rrf_score"]:.5f}  BM25 {row["bm25_rank"] or "-"}  Vector {row["vector_rank"] or "-"}')
        print(f'   {row["title"]} > {row["heading"]}'.rstrip(" >"))


if __name__ == "__main__":
    main()
