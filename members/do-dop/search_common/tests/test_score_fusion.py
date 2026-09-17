import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from search_common.score_fusion import normalized_score_fusion


class NormalizedScoreFusionTest(unittest.TestCase):
    def test_min_max_normalizes_within_each_list(self):
        # bm25: a=100(최댓값=1.0), b=1(최솟값=0.0). vector: 없음.
        fused = dict(normalized_score_fusion([("a", 100.0), ("b", 1.0)], []))
        self.assertAlmostEqual(0.5, fused["a"])  # 0.5*1.0 + 0.5*0(vector 없음)
        self.assertAlmostEqual(0.0, fused["b"])

    def test_all_equal_scores_tie(self):
        fused = dict(normalized_score_fusion([("a", 5.0), ("b", 5.0)], []))
        self.assertAlmostEqual(fused["a"], fused["b"])

    def test_missing_from_one_list_contributes_zero(self):
        fused = dict(normalized_score_fusion([("a", 10.0), ("b", 0.0)], [("c", 1.0)], bm25_weight=0.5))
        self.assertAlmostEqual(0.5, fused["a"])
        self.assertAlmostEqual(0.5, fused["c"])
        self.assertAlmostEqual(0.0, fused["b"])

    def test_doc_in_both_lists_beats_doc_in_one_list_when_both_are_top(self):
        # 'shared'는 두 리스트 모두에서 1등, 'only_bm25'는 BM25에서만 1등.
        bm25 = [("shared", 50.0), ("only_bm25", 10.0)]
        vector = [("shared", 0.9), ("only_vector", 0.1)]
        fused = normalized_score_fusion(bm25, vector)
        ranked_ids = [doc_id for doc_id, _ in fused]
        self.assertEqual("shared", ranked_ids[0])


if __name__ == "__main__":
    unittest.main()
