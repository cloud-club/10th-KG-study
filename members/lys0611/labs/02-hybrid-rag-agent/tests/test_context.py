from datetime import datetime

from context import select_context, sequence_overlap
from models import Chunk, FusedHit


def chunk(chunk_id, content_hash, start_seq, end_seq):
    now = datetime(2025, 1, 1)
    return Chunk(chunk_id, content_hash, "방", now, now, start_seq, end_seq, ("가명",), "내용")


def fused(chunk_id, content_hash, score):
    return FusedHit(chunk_id, content_hash, score, {"bm25": 1}, {"bm25": 1.0})


def test_sequence_overlap_and_context_ids():
    first = chunk(1, "a" * 40, 1, 5)
    overlapping = chunk(2, "b" * 40, 3, 6)
    separate = chunk(3, "c" * 40, 10, 12)
    assert sequence_overlap(first, overlapping) == 0.75

    chunks = {1: first, 2: overlapping, 3: separate}
    items = select_context(
        [fused(1, first.content_hash, 1), fused(2, overlapping.content_hash, 0.9), fused(3, separate.content_hash, 0.8)],
        chunks,
        top_k=3,
        max_chars=100,
    )
    assert [item.citation_id for item in items] == ["C1", "C2"]
    assert [item.chunk.chunk_id for item in items] == [1, 3]
