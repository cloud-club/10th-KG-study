import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]

elasticsearch_stub = types.ModuleType("elasticsearch")
elasticsearch_stub.Elasticsearch = object
sys.modules.setdefault("elasticsearch", elasticsearch_stub)

psycopg_stub = types.ModuleType("psycopg")
psycopg_stub.connect = None
sys.modules.setdefault("psycopg", psycopg_stub)


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    sys.modules[name] = module
    return module


load_module("common", "src/common.py")
load_module("index_documents", "src/retrieval/keyword/index_documents.py")
load_module("keyword_search_module", "src/retrieval/keyword/search.py")
load_module("vector_index_documents", "src/retrieval/vector/index_documents.py")
load_module("vector_search_module", "src/retrieval/vector/search.py")
load_module("hybrid_search_module", "src/retrieval/hybrid/search.py")
recall_at_k = load_module("recall_at_k", "src/evaluation/recall_at_k.py")


def result(document_id: str, rank: int) -> dict:
    return {
        "id": document_id,
        "rank": rank,
        "score": 1.0,
        "title": document_id,
        "source": f"{document_id}.md",
        "chunk_index": 0,
        "content": document_id,
    }


class RecallAtKTest(unittest.TestCase):
    def test_recall_at_k_counts_reference_ids_found_within_top_k(self):
        retrieved_ids = ["A", "B", "C", "D"]
        self.assertEqual(recall_at_k.recall_at_k(retrieved_ids, ["A", "C"], k=2), 0.5)
        self.assertEqual(recall_at_k.recall_at_k(retrieved_ids, ["A", "C"], k=3), 1.0)
        self.assertEqual(recall_at_k.recall_at_k(retrieved_ids, ["Z"], k=4), 0.0)

    def test_recall_at_k_rejects_empty_reference_ids(self):
        with self.assertRaisesRegex(ValueError, "reference_chunk_ids"):
            recall_at_k.recall_at_k(["A"], [], k=1)

    def test_evaluate_averages_recall_across_questions_per_method(self):
        questions = [
            {"question": "q1", "reference_chunk_ids": ["A"]},
            {"question": "q2", "reference_chunk_ids": ["Z"]},
        ]

        keyword_results = [result("A", 1)]
        vector_results = [result("B", 1)]
        hybrid_results = [result("A", 1)]

        with (
            patch.object(recall_at_k, "keyword_search", return_value=keyword_results),
            patch.object(recall_at_k, "vector_search", return_value=vector_results),
            patch.object(recall_at_k, "hybrid_search", return_value=hybrid_results),
        ):
            scores = recall_at_k.evaluate(
                questions,
                es_client=object(),
                es_url="http://localhost:9200",
                postgres=object(),
                ks=[1],
                rank_window=20,
                rank_constant=60,
            )

        self.assertEqual(scores["keyword"][1], 0.5)
        self.assertEqual(scores["vector"][1], 0.0)
        self.assertEqual(scores["hybrid"][1], 0.5)


if __name__ == "__main__":
    unittest.main()
