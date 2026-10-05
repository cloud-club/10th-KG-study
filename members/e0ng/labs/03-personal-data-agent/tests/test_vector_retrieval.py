import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]

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


index_documents = load_module(
    "index_documents", "src/retrieval/vector/index_documents.py"
)
vector_search = load_module("vector_search", "src/retrieval/vector/search.py")


class FakeResult:
    def fetchall(self):
        return [
            ("chunk-1", "AWS Lambda", "Study/AWS Lambda.md", 0, "이미지 처리", 0.82)
        ]


class FakeConnection:
    def __init__(self):
        self.query = None
        self.parameters = None

    def execute(self, query, parameters):
        self.query = query
        self.parameters = parameters
        return FakeResult()


class VectorRetrievalTest(unittest.TestCase):
    def test_embedding_text_contains_title_and_content(self):
        document = {"title": "AWS Lambda", "content": "이미지 처리"}
        self.assertEqual(
            index_documents.embedding_text(document),
            "제목: AWS Lambda\n본문: 이미지 처리",
        )

    def test_vector_literal_rejects_wrong_dimension(self):
        with self.assertRaisesRegex(ValueError, "임베딩 차원"):
            index_documents.vector_literal([0.1, 0.2])

    def test_search_returns_common_shape_and_cosine_score(self):
        connection = FakeConnection()
        fake_vector = [0.0] * index_documents.EXPECTED_DIMENSION
        with patch.object(vector_search, "embed", return_value=[fake_vector]):
            results = vector_search.search_documents(connection, "이미지 처리", limit=5)

        self.assertIn("embedding <=>", connection.query)
        self.assertEqual(connection.parameters[2], 5)
        self.assertEqual(results[0]["id"], "chunk-1")
        self.assertEqual(results[0]["rank"], 1)
        self.assertEqual(results[0]["score"], 0.82)


if __name__ == "__main__":
    unittest.main()
