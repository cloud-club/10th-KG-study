"""BM25와 pgvector 결과를 RRF로 결합하는 하이브리드 검색."""

from __future__ import annotations

import argparse
import time
from collections import defaultdict
from typing import Any

from common import ES_INDEX, PG_TABLE
from search_elasticsearch import search_bm25
from search_pgvector import search_vector


SearchRows = list[tuple[dict[str, Any], float]]


def reciprocal_rank_fusion(
    result_lists: dict[str, SearchRows],
    rank_constant: int = 60,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """검색 점수 대신 각 결과의 순위만 이용해 결과를 합친다.

    같은 청크가 여러 검색기에 나타나면 ``1 / (rank_constant + rank)``를
    모두 더한다. 원래 점수는 비교 UI에서 보여주기 위해 보존하지만 최종
    순위 계산에는 쓰지 않는다.
    """
    if rank_constant < 0:
        raise ValueError("rank_constant는 0 이상이어야 합니다.")
    if limit is not None and limit <= 0:
        raise ValueError("limit은 1 이상이어야 합니다.")

    scores: defaultdict[str, float] = defaultdict(float)
    documents: dict[str, dict[str, Any]] = {}
    ranks: defaultdict[str, dict[str, int]] = defaultdict(dict)
    original_scores: defaultdict[str, dict[str, float]] = defaultdict(dict)

    for method, rows in result_lists.items():
        seen_in_method: set[str] = set()
        for rank, (document, original_score) in enumerate(rows, start=1):
            chunk_id = document["chunk_id"]
            if chunk_id in seen_in_method:
                continue
            seen_in_method.add(chunk_id)
            scores[chunk_id] += 1.0 / (rank_constant + rank)
            ranks[chunk_id][method] = rank
            original_scores[chunk_id][method] = float(original_score)
            documents.setdefault(chunk_id, document)

    fused = [
        {
            **documents[chunk_id],
            "rrf_score": score,
            "ranks": ranks[chunk_id],
            "original_scores": original_scores[chunk_id],
        }
        for chunk_id, score in scores.items()
    ]
    fused.sort(key=lambda row: (-row["rrf_score"], row["chunk_id"]))
    return fused[:limit] if limit is not None else fused


def search_hybrid(
    query: str,
    limit: int = 5,
    candidate_limit: int = 20,
    rank_constant: int = 60,
    index_name: str = ES_INDEX,
    table_name: str = PG_TABLE,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """BM25·벡터 후보를 가져와 RRF 최종 순위로 반환한다."""
    if limit <= 0:
        raise ValueError("limit은 1 이상이어야 합니다.")
    if candidate_limit < limit:
        raise ValueError("candidate_limit은 limit 이상이어야 합니다.")

    started = time.perf_counter()
    bm25_rows, _ = search_bm25(
        query,
        limit=candidate_limit,
        index_name=index_name,
        date_from=date_from,
        date_to=date_to,
    )
    vector_rows, _ = search_vector(
        query,
        limit=candidate_limit,
        table_name=table_name,
        date_from=date_from,
        date_to=date_to,
    )
    rows = reciprocal_rank_fusion(
        {"bm25": bm25_rows, "vector": vector_rows},
        rank_constant=rank_constant,
        limit=limit,
    )
    return rows, (time.perf_counter() - started) * 1000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--candidate-limit", type=int, default=20)
    parser.add_argument("--rrf-k", type=int, default=60)
    args = parser.parse_args()

    rows, elapsed = search_hybrid(
        args.query,
        limit=args.limit,
        candidate_limit=args.candidate_limit,
        rank_constant=args.rrf_k,
    )
    print(f'[Hybrid/RRF] "{args.query}" · {len(rows)}건 · {elapsed:.1f}ms')
    for rank, row in enumerate(rows, start=1):
        heading = f"#{row['heading']}" if row.get("heading") else ""
        print(
            f"{rank}. {row['source_path']}{heading} · RRF {row['rrf_score']:.6f} "
            f"· BM25 {row['ranks'].get('bm25', '-')}위 "
            f"· Vector {row['ranks'].get('vector', '-')}위"
        )


if __name__ == "__main__":
    main()
