"""chunker 단위 테스트. 실행: python3 -m unittest discover -s members/sese2204/labs/02-kakao-chunk-embed/src"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from chunker import ChunkParams, MessageRow, chunk_messages, format_line

T0 = datetime(2023, 8, 9, 0, 34)


def rows(*specs: tuple[int, str, str]) -> list[MessageRow]:
    """(분 오프셋, 이름, 내용) 목록 → seq 1부터."""
    return [MessageRow(i, T0 + timedelta(minutes=m), who, what) for i, (m, who, what) in enumerate(specs, 1)]


LOOSE = ChunkParams(gap_minutes=30, max_chars=10_000, max_messages=10_000, min_chars=0)


class BoundaryTests(unittest.TestCase):
    def test_everything_within_gap_is_one_chunk(self):
        (c,) = chunk_messages(rows((0, "갑", "안녕"), (5, "을", "반가워"), (29, "갑", "응")), LOOSE)
        self.assertEqual((c.chunk_idx, c.start_seq, c.end_seq, c.message_count), (0, 1, 3, 3))
        self.assertEqual((c.started_at, c.ended_at), (T0, T0 + timedelta(minutes=29)))
        self.assertEqual(c.text, "갑: 안녕\n을: 반가워\n갑: 응")

    def test_gap_over_threshold_starts_new_chunk(self):
        a, b = chunk_messages(rows((0, "갑", "안녕"), (31, "을", "늦었다")), LOOSE)
        self.assertEqual((a.end_seq, b.start_seq, b.chunk_idx), (1, 2, 1))

    def test_gap_exactly_at_threshold_does_not_split(self):
        self.assertEqual(len(chunk_messages(rows((0, "갑", "안녕"), (30, "을", "정시")), LOOSE)), 1)

    def test_max_chars_splits_before_exceeding(self):
        p = ChunkParams(gap_minutes=1e9, max_chars=20, max_messages=1000, min_chars=0)
        # "갑: 12345678" = 11자, 줄바꿈 포함 12 → 두 개면 24 > 20
        a, b = chunk_messages(rows((0, "갑", "12345678"), (1, "갑", "12345678")), p)
        self.assertEqual([a.message_count, b.message_count], [1, 1])

    def test_single_message_longer_than_max_chars_still_becomes_its_own_chunk(self):
        p = ChunkParams(gap_minutes=1e9, max_chars=5, max_messages=1000, min_chars=0)
        (c,) = chunk_messages(rows((0, "갑", "아주아주긴메시지")), p)
        self.assertEqual(c.message_count, 1)

    def test_max_messages_splits(self):
        p = ChunkParams(gap_minutes=1e9, max_chars=10_000, max_messages=2, min_chars=0)
        chunks = chunk_messages(rows((0, "갑", "a"), (1, "갑", "b"), (2, "갑", "c"), (3, "갑", "d"), (4, "갑", "e")), p)
        self.assertEqual([c.message_count for c in chunks], [2, 2, 1])
        self.assertEqual([c.chunk_idx for c in chunks], [0, 1, 2])


class FilterTests(unittest.TestCase):
    def test_tiny_chunks_are_dropped_and_idx_stays_dense(self):
        p = ChunkParams(gap_minutes=30, max_chars=10_000, max_messages=10_000, min_chars=5)
        chunks = chunk_messages(rows((0, "갑", "ㅋㅋ"), (100, "을", "충분히 긴 메시지"), (200, "갑", "ㅗ")), p)
        self.assertEqual([(c.chunk_idx, c.text) for c in chunks], [(0, "을: 충분히 긴 메시지")])

    def test_min_chars_counts_content_only_not_sender_names(self):
        p = ChunkParams(gap_minutes=30, max_chars=10_000, max_messages=10_000, min_chars=3)
        self.assertEqual(len(chunk_messages(rows((0, "아주긴이름입니다", "ㅋ")), p)), 0)
        self.assertEqual(len(chunk_messages(rows((0, "갑", "ㅋㅋㅋ")), p)), 1)

    def test_empty_input_yields_nothing(self):
        self.assertEqual(chunk_messages([], LOOSE), ())


class FormatTests(unittest.TestCase):
    def test_multiline_content_is_kept_as_is(self):
        row = MessageRow(1, T0, "갑", "첫 줄\n둘째 줄")
        self.assertEqual(format_line(row), "갑: 첫 줄\n둘째 줄")


if __name__ == "__main__":
    unittest.main()
