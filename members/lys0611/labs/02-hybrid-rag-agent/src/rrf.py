"""Reciprocal Rank Fusion. 원 점수는 섞지 않고 순위만 합친다."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from models import FusedHit, RankedHit


def reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[RankedHit]],
    *,
    rank_constant: int = 60,
    limit: int | None = None,
) -> list[FusedHit]:
    if rank_constant < 1:
        raise ValueError("rank_constant는 1 이상이어야 합니다.")
    if limit is not None and limit < 0:
        raise ValueError("limit는 0 이상이어야 합니다.")

    scores: dict[str, float] = {}
    source_ranks: dict[str, dict[str, int]] = {}
    raw_scores: dict[str, dict[str, float]] = {}
    chunk_ids: dict[str, int] = {}

    for source, hits in rankings.items():
        seen: set[str] = set()
        for rank, hit in enumerate(hits, start=1):
            if hit.content_hash in seen:
                continue
            seen.add(hit.content_hash)
            previous_id = chunk_ids.setdefault(hit.content_hash, hit.chunk_id)
            if previous_id != hit.chunk_id:
                raise RuntimeError(
                    f"같은 content_hash가 서로 다른 chunk_id를 가리킵니다: {hit.content_hash}"
                )
            scores[hit.content_hash] = scores.get(hit.content_hash, 0.0) + 1.0 / (
                rank_constant + rank
            )
            source_ranks.setdefault(hit.content_hash, {})[source] = rank
            raw_scores.setdefault(hit.content_hash, {})[source] = hit.score

    fused = [
        FusedHit(
            chunk_id=chunk_ids[content_hash],
            content_hash=content_hash,
            score=score,
            ranks=source_ranks[content_hash],
            raw_scores=raw_scores[content_hash],
        )
        for content_hash, score in scores.items()
    ]
    fused.sort(
        key=lambda hit: (
            -hit.score,
            min(hit.ranks.values()),
            hit.content_hash,
        )
    )
    return fused if limit is None else fused[:limit]
