from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from hybrid_search import reciprocal_rank_fusion  # noqa: E402


def document(chunk_id: str) -> dict:
    return {
        "chunk_id": chunk_id,
        "source_path": f"{chunk_id}.md",
        "heading": None,
        "content": chunk_id,
    }


class ReciprocalRankFusionTest(unittest.TestCase):
    def test_document_found_by_both_searches_ranks_first(self) -> None:
        rows = reciprocal_rank_fusion(
            {
                "bm25": [(document("a"), 12.0), (document("shared"), 8.0)],
                "vector": [(document("shared"), 0.9), (document("b"), 0.8)],
            },
            rank_constant=60,
        )
        self.assertEqual("shared", rows[0]["chunk_id"])
        self.assertEqual({"bm25": 2, "vector": 1}, rows[0]["ranks"])

    def test_original_scores_do_not_change_rank_formula(self) -> None:
        rows = reciprocal_rank_fusion(
            {
                "bm25": [(document("a"), 9999.0)],
                "vector": [(document("b"), 0.01)],
            },
            rank_constant=60,
        )
        self.assertAlmostEqual(rows[0]["rrf_score"], rows[1]["rrf_score"])
        self.assertEqual(["a", "b"], [row["chunk_id"] for row in rows])

    def test_limit_and_invalid_parameters(self) -> None:
        rows = reciprocal_rank_fusion(
            {"bm25": [(document("a"), 1.0), (document("b"), 0.5)]},
            limit=1,
        )
        self.assertEqual(1, len(rows))
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion({}, rank_constant=-1)


if __name__ == "__main__":
    unittest.main()
