"""점수를 정규화해서 더하는 하이브리드 융합 (RRF와 비교하기 위한 대안).

BM25 점수(예: 27.5)와 코사인 점수(예: 0.75)는 스케일이 다르므로, 각 리스트 안에서
최댓값·최솟값 기준으로 0~1로 정규화한 뒤 가중합을 낸다. RRF와 달리 "한쪽에서 압도적인
1등"이 그대로 반영된다는 장점이 있지만, 정규화 기준(이번 검색 결과의 최댓값)이 질의마다
달라져 점수 분포가 들쭉날쭉할 수 있다는 단점이 있다.
"""

from __future__ import annotations


def _normalize(results: list[tuple[str, float]]) -> dict[str, float]:
    if not results:
        return {}
    scores = [score for _, score in results]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return {doc_id: 1.0 for doc_id, _ in results}
    return {doc_id: (score - lo) / (hi - lo) for doc_id, score in results}


def normalized_score_fusion(
    bm25_results: list[tuple[str, float]],
    vector_results: list[tuple[str, float]],
    bm25_weight: float = 0.5,
) -> list[tuple[str, float]]:
    bm25_norm = _normalize(bm25_results)
    vector_norm = _normalize(vector_results)
    all_ids = set(bm25_norm) | set(vector_norm)
    fused = {
        doc_id: bm25_weight * bm25_norm.get(doc_id, 0.0) + (1 - bm25_weight) * vector_norm.get(doc_id, 0.0)
        for doc_id in all_ids
    }
    return sorted(fused.items(), key=lambda item: item[1], reverse=True)
