"""검색 평가 지표. evidence group 안의 여러 해시는 대체 가능한 근거다."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from statistics import mean


def _top_unique(retrieved: Sequence[str], k: int) -> list[str]:
    if k < 0:
        raise ValueError("k는 0 이상이어야 합니다.")
    return list(dict.fromkeys(retrieved))[:k]


def document_recall_at_k(
    retrieved: Sequence[str], relevant: Iterable[str], k: int
) -> float | None:
    gold = set(relevant)
    if not gold:
        return None
    return len(set(_top_unique(retrieved, k)) & gold) / len(gold)


def evidence_recall_at_k(
    retrieved: Sequence[str], evidence_groups: Sequence[Sequence[str]], k: int
) -> float | None:
    groups = [set(group) for group in evidence_groups if group]
    if not groups:
        return None
    top = set(_top_unique(retrieved, k))
    return sum(bool(top & group) for group in groups) / len(groups)


def all_evidence_at_k(
    retrieved: Sequence[str], evidence_groups: Sequence[Sequence[str]], k: int
) -> int | None:
    recall = evidence_recall_at_k(retrieved, evidence_groups, k)
    if recall is None:
        return None
    return int(recall == 1.0)


def reciprocal_rank(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float | None:
    gold = set(relevant)
    if not gold:
        return None
    for rank, item in enumerate(_top_unique(retrieved, k), start=1):
        if item in gold:
            return 1.0 / rank
    return 0.0


def ann_recall_at_k(approx: Sequence[str], exact: Sequence[str], k: int) -> float:
    exact_top = set(_top_unique(exact, k))
    if not exact_top:
        return 1.0
    return len(set(_top_unique(approx, k)) & exact_top) / len(exact_top)


def macro(values: Iterable[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return mean(present) if present else None
