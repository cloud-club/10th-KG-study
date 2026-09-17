from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import hybrid_search as hs


def document(identifier, corpus="own", text="caption"):
    return {"id": identifier, "text": text, "permalink": "https://www.instagram.com/p/ABC/", "corpus": corpus,
            "provenance": [corpus], "published_at": None, "collected_at": None}


class FusionTests(unittest.TestCase):
    def test_rank_sum_ignores_incomparable_scores(self):
        keyword = [{**document("a"), "score": 2000}, {**document("b"), "score": 1}]
        semantic = [{**document("b"), "score": .9}, {**document("c"), "score": .8}]
        result = hs.reciprocal_rank_fusion(keyword, semantic)
        self.assertEqual([row["id"] for row in result], ["b", "a", "c"])
        self.assertAlmostEqual(result[0]["score"], 1 / 62 + 1 / 61)
        self.assertEqual((result[0]["bm25_rank"], result[0]["vector_rank"]), (2, 1))
        scaled = [{**row, "score": row["score"] * 1e9} for row in keyword]
        self.assertEqual(result, hs.reciprocal_rank_fusion(scaled, semantic))

    def test_duplicates_do_not_change_ranks_or_boost_scores(self):
        a, b = document("a"), document("b")
        self.assertEqual(hs.reciprocal_rank_fusion([a, a, b], [b, b]),
                         hs.reciprocal_rank_fusion([a, b], [b]))

    def test_missing_component_and_stable_ties(self):
        result = hs.reciprocal_rank_fusion([document("z")], [document("a")])
        self.assertEqual([row["id"] for row in result], ["a", "z"])
        self.assertIsNone(result[0]["bm25_rank"])
        self.assertAlmostEqual(result[0]["score"], 1 / 61)
        self.assertEqual(hs.reciprocal_rank_fusion([], []), [])


class CorpusTests(unittest.TestCase):
    def write(self, path, rows):
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    def test_overlap_preserves_own_text_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            own, reference = Path(directory) / "own.jsonl", Path(directory) / "ref.jsonl"
            self.write(own, [document("a", text="own original")])
            self.write(reference, [document("a", "reference", "external"), document("b", "reference")])
            with patch.object(hs, "SOURCES", {"own": own, "reference": reference}):
                rows = hs.load_corpus()
            self.assertEqual(rows[0]["text"], "own original")
            self.assertEqual(rows[0]["provenance"], ["own", "reference"])
            self.assertEqual(rows[1]["corpus"], "reference")

    def test_empty_duplicate_and_invalid_url_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            own, ref = Path(directory) / "own", Path(directory) / "ref"
            self.write(ref, [document("r", "reference")])
            cases = [[], [document("a"), document("a")], [{**document("a"), "permalink": "https://evil.test/p/A"}],
                     [{**document("a"), "text": " "}]]
            for rows in cases:
                with self.subTest(rows=rows), patch.object(hs, "SOURCES", {"own": own, "reference": ref}):
                    self.write(own, rows)
                    with self.assertRaises(ValueError):
                        hs.load_corpus()


class SearchContractTests(unittest.TestCase):
    def setUp(self):
        with patch.object(hs, "load_corpus", return_value=[document("a"), document("r", "reference")]):
            self.search = hs.HybridSearch()

    def test_invalid_parameters_never_connect(self):
        cases = [{"query": " "}, {"query": "q", "limit": 5, "candidates": 3}, {"query": "q", "limit": True},
                 {"query": "q", "mode": "unknown"}, {"query": "q", "scope": "selected"}]
        with patch.object(self.search, "_ensure_indexed") as connect:
            for values in cases:
                with self.subTest(values=values), self.assertRaises(ValueError):
                    self.search.search(**values)
            connect.assert_not_called()

    def test_scope_and_budget_passed_to_both_components(self):
        with patch.object(self.search, "_ensure_indexed"), patch.object(self.search, "_bm25", return_value=[document("r", "reference")]) as bm25, patch.object(self.search, "_vector", return_value=[]) as vector:
            result = self.search.search(" question ", candidates=8, limit=1, scope="reference")
            bm25.assert_called_once_with("question", 8, "reference")
            vector.assert_called_once_with("question", 8, "reference")
            self.assertEqual(result[0]["corpus"], "reference")
            self.assertIn("permalink", result[0])

    def test_out_of_scope_result_is_rejected(self):
        with patch.object(self.search, "_ensure_indexed"), patch.object(self.search, "_bm25", return_value=[document("r", "reference")]):
            with self.assertRaises(ValueError):
                self.search.search("q", mode="bm25", scope="own")

    def test_original_or_unsafe_store_names_are_rejected(self):
        for value in ["kdyann_instagram_posts", "public.kdyann_hybrid_posts", "kdyann_hybrid_posts; DROP TABLE x"]:
            with self.subTest(value=value), patch.dict(os.environ, {"W3_PG_TABLE": value}):
                with self.assertRaises(ValueError):
                    hs.settings()

    def test_ann_search_budget_covers_requested_candidate_count(self):
        backend = MagicMock()
        cursor = backend.connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [("a", .5)]
        model = MagicMock()
        model.encode.return_value = [[1.0] + [0.0] * 383]
        with patch.dict(sys.modules, {"psycopg": backend}), patch.object(hs, "embedding_model", return_value=model):
            result = self.search._vector("q", 250, "all")
        self.assertEqual(result[0]["id"], "a")
        self.assertIn(("SELECT set_config('hnsw.ef_search', %s, true)", ("250",)),
                      [(call.args[0], call.args[1]) for call in cursor.execute.call_args_list if len(call.args) == 2 and isinstance(call.args[0], str)])
        self.assertEqual(cursor.execute.call_args_list[-1].args[1][-1], 250)

    def test_search_refuses_stale_or_unowned_manifest(self):
        expected = self.search.manifest
        for actual in [{**expected, "fingerprint": "old", "status": "ready"}, {**expected, "owner": "other", "status": "ready"}, {**expected, "status": "building"}]:
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                hs.check_manifest(actual, expected)
        hs.check_manifest({**expected, "status": "ready"}, expected)


if __name__ == "__main__":
    unittest.main()
