from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from evaluate_search import evaluate, recall_at_k, validate_questions
from hybrid_search import corpus_manifest


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.documents = [{"id": "a", "corpus": "own"}, {"id": "b", "corpus": "own"}, {"id": "r", "corpus": "reference"}]
        self.fixture = {"description": "manually labeled", "questions": [{"id": "q", "query": "question", "scope": "own", "relevant_ids": ["a", "b"]}]}

    def test_recall_denominator_all_gold_and_duplicate_results_do_not_inflate(self):
        self.assertEqual(recall_at_k(["a", "a", "x"], ["a", "b"], 3), .5)
        self.assertEqual(recall_at_k(["a", "b"], ["a", "b"], 1), .5)
        self.assertEqual(recall_at_k([], ["a"], 3), 0)
        for gold in ([], ["a", "a"]):
            with self.assertRaises(ValueError):
                recall_at_k([], gold, 1)

    def test_bad_gold_scope_duplicate_question_and_empty_fixture(self):
        variants = []
        for changes in [{"relevant_ids": []}, {"relevant_ids": ["a", "a"]}, {"relevant_ids": ["missing"]}, {"relevant_ids": ["r"]}, {"query": " "}, {"scope": "invalid"}]:
            value = copy.deepcopy(self.fixture)
            value["questions"][0].update(changes)
            variants.append(value)
        duplicate = copy.deepcopy(self.fixture)
        duplicate["questions"] *= 2
        variants.extend([duplicate, {"questions": []}, {}, None])
        for fixture in variants:
            with self.subTest(fixture=fixture), self.assertRaises(ValueError):
                validate_questions(fixture, self.documents)

    def test_each_mode_uses_same_scope_question_and_budget(self):
        search = Mock()
        search.manifest = corpus_manifest(self.documents)
        search.search.side_effect = [[{"id": "a", "score": 4}], [{"id": "b", "score": .9}], [{"id": "a", "score": .03}, {"id": "b", "score": .02}]]
        report = evaluate(self.fixture, self.documents, search, [1, 3], candidates=10)
        self.assertEqual(report["macro_recall_at_k"]["bm25"], {"1": .5, "3": .5})
        self.assertEqual(report["macro_recall_at_k"]["hybrid"], {"1": .5, "3": 1})
        for call in search.search.call_args_list:
            self.assertEqual(call.args, ("question",))
            self.assertEqual(call.kwargs["scope"], "own")
            self.assertEqual(call.kwargs["limit"], 3)
            self.assertEqual(call.kwargs["candidates"], 10)
        self.assertEqual([call.kwargs["mode"] for call in search.search.call_args_list], ["bm25", "vector", "hybrid"])

    def test_invalid_labels_fail_before_search(self):
        search = Mock()
        value = copy.deepcopy(self.fixture)
        value["questions"][0]["relevant_ids"] = ["missing"]
        with self.assertRaises(ValueError):
            evaluate(value, self.documents, search, [1], 10)
        search.search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
