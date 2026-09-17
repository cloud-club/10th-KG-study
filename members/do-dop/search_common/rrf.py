"""Reciprocal Rank Fusion(RRF)으로 여러 순위 리스트를 하나로 합친다.

점수를 정규화해서 더하는 대신 순위(rank)만 이용한다. BM25 점수와 코사인 유사도는
스케일이 달라서(예: 27.5 대 0.75) 그대로 더하면 한쪽이 항상 우세해지는데, 순위는
검색 방식과 무관하게 항상 1부터 시작하므로 비교가 공정해진다.
"""

from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_id_lists: list[list[str]], k: int = 60
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranked_ids in ranked_id_lists:
        for rank, doc_id in enumerate(ranked_ids, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
