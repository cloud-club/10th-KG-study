import importlib.util
import json
import sys
import unittest
from pathlib import Path


def _load(module_name: str):
    module_path = Path(__file__).parents[1] / "src" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


index_es = _load("index_es")


class BuildIndexBodyTest(unittest.TestCase):
    def test_defines_nori_and_ngram_analyzers_on_text_field(self):
        body = index_es.build_index_body()

        analyzers = body["settings"]["analysis"]["analyzer"]
        self.assertIn("nori_analyzer", analyzers)
        self.assertIn("ngram_analyzer", analyzers)

        text_field = body["mappings"]["properties"]["text"]
        self.assertEqual("nori_analyzer", text_field["analyzer"])
        self.assertEqual(
            "ngram_analyzer", text_field["fields"]["ngram"]["analyzer"]
        )


class BuildBulkLinesTest(unittest.TestCase):
    def test_pairs_action_and_source_lines_per_message(self):
        messages = [
            {
                "chunk_id": "msg-000001",
                "sender_id": "user-001",
                "sent_at": "2026-09-10T00:05:00",
                "text": "첫 메시지",
            },
            {
                "chunk_id": "msg-000002",
                "sender_id": "user-002",
                "sent_at": "2026-09-10T00:06:00",
                "text": "두 번째 메시지",
            },
        ]

        lines = index_es.build_bulk_lines(messages, "do-dop-kakao-messages")

        self.assertEqual(4, len(lines))
        first_action = json.loads(lines[0])
        self.assertEqual("msg-000001", first_action["index"]["_id"])
        self.assertEqual("do-dop-kakao-messages", first_action["index"]["_index"])
        first_source = json.loads(lines[1])
        self.assertEqual("첫 메시지", first_source["text"])
        self.assertNotIn("source_line_start", first_source)

    def test_batched_splits_by_document_count(self):
        lines = [f"line-{i}" for i in range(10)]  # 5 docs worth of action+source pairs

        batches = list(index_es.batched(lines, batch_size=2))

        self.assertEqual([4, 4, 2], [len(batch) for batch in batches])


if __name__ == "__main__":
    unittest.main()
