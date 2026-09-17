"""검색 결과의 Hit@k와 Recall@k 계산."""

from __future__ import annotations


def evaluate_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> dict[str, float]:
    retrieved = set(retrieved_ids[:k])
    relevant = set(relevant_ids)
    found = retrieved & relevant
    return {
        f"hit_at_{k}": 1.0 if found else 0.0,
        f"recall_at_{k}": len(found) / len(relevant) if relevant else 0.0,
    }
