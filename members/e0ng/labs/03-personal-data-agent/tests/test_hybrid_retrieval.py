import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]

import types

psycopg_stub = types.ModuleType("psycopg")
psycopg_stub.connect = None
sys.modules.setdefault("psycopg", psycopg_stub)


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


hybrid_search = load_module("hybrid_search", "src/retrieval/hybrid/search.py")


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


class HybridRetrievalTest(unittest.TestCase):
    def test_rrf_rewards_documents_found_by_both_searches(self):
        results = hybrid_search.reciprocal_rank_fusion(
            {
                "keyword": [result("A", 1), result("B", 2)],
                "vector": [result("C", 1), result("B", 2)],
            },
            rank_constant=60,
            limit=3,
        )

        self.assertEqual(results[0]["id"], "B")
        self.assertEqual(results[0]["ranks"], {"keyword": 2, "vector": 2})
        self.assertEqual(results[0]["rank"], 1)

    def test_rrf_does_not_use_original_scores(self):
        keyword = result("A", 1)
        vector = result("B", 1)
        keyword["score"] = 1000.0
        vector["score"] = 0.01

        results = hybrid_search.reciprocal_rank_fusion(
            {"keyword": [keyword], "vector": [vector]},
            rank_constant=60,
            limit=2,
        )

        self.assertEqual(results[0]["score"], results[1]["score"])


if __name__ == "__main__":
    unittest.main()
