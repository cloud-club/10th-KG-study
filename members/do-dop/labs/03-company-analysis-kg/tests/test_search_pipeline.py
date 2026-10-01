import importlib.util
import sys
import unittest
from pathlib import Path


SRC = Path(__file__).parents[1] / "src"
sys.path.insert(0, str(SRC))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SRC / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


search_grep = load("search_grep")
index_es = load("index_es")
chunk_documents = load("chunk_documents")


class SearchPipelineTest(unittest.TestCase):
    def test_grep_searches_only_text(self):
        chunks = [
            {"id": "a", "title": "HBM4E 제목", "text": "본문에는 다른 내용"},
            {"id": "b", "title": "다른 제목", "text": "HBM4E 12단을 공급했다"},
        ]
        self.assertEqual(["b"], [item["id"] for item in search_grep.search(chunks, "HBM4E")])

    def test_es_document_keeps_search_metadata(self):
        chunk = {
            "id": "newsroom_001_chunk_01", "document_id": "newsroom_001",
            "title": "제목", "company": ["삼성전자"], "source": "newsroom",
            "date": "2026-01-01", "text": "본문", "url": "https://example.com",
        }
        document = index_es.to_es_document(chunk)
        self.assertEqual(chunk["id"], document["_id"])
        self.assertEqual(["삼성전자"], document["company"])

    def test_chunk_text_overlaps_previous_paragraph(self):
        text = "첫 문단입니다.\n두 번째 문단입니다.\n세 번째 문단입니다."
        chunks = chunk_documents.chunk_text(text, max_chars=22, overlap_paragraphs=1)
        self.assertGreaterEqual(len(chunks), 2)


if __name__ == "__main__":
    unittest.main()

