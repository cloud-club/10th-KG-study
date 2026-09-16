import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]

elasticsearch_stub = types.ModuleType("elasticsearch")
elasticsearch_stub.Elasticsearch = object
elasticsearch_stub.helpers = types.SimpleNamespace()
sys.modules.setdefault("elasticsearch", elasticsearch_stub)


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


common = load_module("common", "src/common.py")
index_documents = load_module(
    "index_documents", "src/retrieval/keyword/index_documents.py"
)
keyword_search = load_module("keyword_search", "src/retrieval/keyword/search.py")


class FakeElasticsearch:
    def __init__(self):
        self.arguments = None

    def search(self, **arguments):
        self.arguments = arguments
        return {
            "hits": {
                "hits": [
                    {
                        "_score": 3.5,
                        "_source": {
                            "id": "chunk-1",
                            "title": "AWS Lambda",
                            "content": "Lambda 이미지 처리",
                            "source": "Study/AWS Lambda.md",
                            "chunk_index": 0,
                        },
                    }
                ]
            }
        }


class KeywordRetrievalTest(unittest.TestCase):
    def test_load_documents_reads_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "documents.jsonl"
            path.write_text(json.dumps({"id": "one"}) + "\n\n", encoding="utf-8")
            self.assertEqual(common.load_documents(path), [{"id": "one"}])

    def test_validate_documents_rejects_duplicate_id(self):
        document = {
            "id": "same",
            "page_id": "page",
            "title": "title",
            "content": "content",
            "source": "source.md",
            "chunk_index": 0,
        }
        with self.assertRaisesRegex(ValueError, "중복된 문서 id"):
            index_documents.validate_documents([document, document])

    def test_search_uses_title_boost_and_returns_common_shape(self):
        client = FakeElasticsearch()
        results = keyword_search.search_documents(client, "이미지 처리", limit=5)

        self.assertEqual(client.arguments["index"], "personal-documents")
        self.assertEqual(
            client.arguments["query"]["multi_match"]["fields"],
            ["title^2", "content"],
        )
        self.assertEqual(results[0]["id"], "chunk-1")
        self.assertEqual(results[0]["rank"], 1)


if __name__ == "__main__":
    unittest.main()
