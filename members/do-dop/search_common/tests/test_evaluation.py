import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from search_common.evaluation import evaluate_at_k


class EvaluationTest(unittest.TestCase):
    def test_hit_and_recall(self):
        result = evaluate_at_k(["a", "x", "b"], ["a", "b", "c"], 3)
        self.assertEqual(1.0, result["hit_at_3"])
        self.assertAlmostEqual(2 / 3, result["recall_at_3"])

    def test_respects_k(self):
        result = evaluate_at_k(["x", "answer"], ["answer"], 1)
        self.assertEqual(0.0, result["hit_at_1"])


if __name__ == "__main__":
    unittest.main()
