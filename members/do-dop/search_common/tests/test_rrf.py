import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from search_common.rrf import reciprocal_rank_fusion


class ReciprocalRankFusionTest(unittest.TestCase):
    def test_agreement_across_lists_ranks_higher(self):
        bm25 = ["a", "b", "c"]
        vector = ["b", "a", "d"]
        fused = reciprocal_rank_fusion([bm25, vector])
        ranked_ids = [doc_id for doc_id, _ in fused]
        self.assertEqual(["a", "b", "c", "d"], ranked_ids)

    def test_score_uses_rank_not_raw_score(self):
        fused = dict(reciprocal_rank_fusion([["a", "b"]], k=60))
        self.assertAlmostEqual(1 / 61, fused["a"])
        self.assertAlmostEqual(1 / 62, fused["b"])

    def test_missing_from_one_list_still_counted(self):
        fused = dict(reciprocal_rank_fusion([["a"], ["b"]], k=60))
        self.assertAlmostEqual(1 / 61, fused["a"])
        self.assertAlmostEqual(1 / 61, fused["b"])


if __name__ == "__main__":
    unittest.main()
