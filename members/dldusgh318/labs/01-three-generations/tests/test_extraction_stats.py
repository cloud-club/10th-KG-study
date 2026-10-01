"""추출 통계 계산의 DB 비의존 단위 테스트."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import extraction_stats


class ExtractionStatsTests(unittest.TestCase):
    def test_counts_candidates_rejections_and_hallucination_rate(self):
        records = [
            {
                "chunk_id": "c1",
                "triples": [
                    {"predicate": "partOf"},
                    {"predicate": "usesTechnology"},
                ],
                "rejected": [
                    {"reason": "evidence_not_found", "triple": {}},
                    {"reason": "range_mismatch", "triple": {}},
                ],
                "error": None,
            },
            {"chunk_id": "c2", "triples": [], "rejected": [], "error": "failed"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "extracted.jsonl"
            path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            stats = extraction_stats.load_extraction_stats(path)

        self.assertEqual(stats.total_extracted_triples, 4)
        self.assertEqual(stats.validation_passed, 2)
        self.assertEqual(stats.validation_rejected, 2)
        self.assertEqual(stats.pass_rate_percent, 50.0)
        self.assertEqual(stats.evidence_not_found, 1)
        self.assertEqual(stats.hallucination_rate_percent, 25.0)
        self.assertEqual(stats.error_chunks, 1)

    def test_zero_candidates_do_not_divide_by_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.jsonl"
            path.write_text(
                json.dumps(
                    {"chunk_id": "c1", "triples": [], "rejected": [], "error": None}
                )
                + "\n",
                encoding="utf-8",
            )
            stats = extraction_stats.load_extraction_stats(path)

        self.assertEqual(stats.pass_rate_percent, 0.0)
        self.assertEqual(stats.hallucination_rate_percent, 0.0)


if __name__ == "__main__":
    unittest.main()
