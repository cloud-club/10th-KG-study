"""RRF 상위 청크에서 중복 대화를 줄이고 인용 가능한 컨텍스트를 만든다."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from models import Chunk, ContextItem, FusedHit


def sequence_overlap(left: Chunk, right: Chunk) -> float:
    if left.room != right.room:
        return 0.0
    overlap = max(0, min(left.end_seq, right.end_seq) - max(left.start_seq, right.start_seq) + 1)
    shorter = min(left.end_seq - left.start_seq + 1, right.end_seq - right.start_seq + 1)
    return overlap / shorter if shorter else 0.0


def select_context(
    fused: Sequence[FusedHit],
    chunks: Mapping[int, Chunk],
    *,
    top_k: int,
    max_chars: int,
    overlap_threshold: float = 0.6,
) -> list[ContextItem]:
    selected: list[tuple[FusedHit, Chunk]] = []
    used_chars = 0
    seen_hashes: set[str] = set()
    for hit in fused:
        chunk = chunks[hit.chunk_id]
        if chunk.content_hash in seen_hashes:
            continue
        if any(sequence_overlap(chunk, other) >= overlap_threshold for _, other in selected):
            continue
        if selected and used_chars + len(chunk.text) > max_chars:
            continue
        selected.append((hit, chunk))
        seen_hashes.add(chunk.content_hash)
        used_chars += len(chunk.text)
        if len(selected) >= top_k:
            break
    return [
        ContextItem(citation_id=f"C{index}", hit=hit, chunk=chunk)
        for index, (hit, chunk) in enumerate(selected, start=1)
    ]


def render_context(items: Sequence[ContextItem]) -> str:
    blocks = []
    for item in items:
        chunk = item.chunk
        blocks.append(
            f'<EVIDENCE id="{item.citation_id}" chunk_id="{chunk.chunk_id}" '
            f'room="{chunk.room}" start="{chunk.start_at.isoformat(timespec="minutes")}" '
            f'end="{chunk.end_at.isoformat(timespec="minutes")}">\n'
            f"{chunk.text}\n</EVIDENCE>"
        )
    return "\n\n".join(blocks)
