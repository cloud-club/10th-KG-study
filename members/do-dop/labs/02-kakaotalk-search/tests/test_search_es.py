import importlib.util
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


search_es = _load("search_es")


class BuildSearchBodyTest(unittest.TestCase):
    def test_builds_match_query_on_requested_field(self):
        body = search_es.build_search_body("저녁 약속", "text.ngram", size=5)

        self.assertEqual(5, body["size"])
        self.assertEqual({"저녁 약속"}, {body["query"]["match"]["text.ngram"]})

    def test_builds_match_phrase_query_when_requested(self):
        body = search_es.build_search_body(
            "저녁 약속", "text", size=5, match_type="match_phrase"
        )

        self.assertIn("match_phrase", body["query"])
        self.assertEqual("저녁 약속", body["query"]["match_phrase"]["text"])

    def test_rejects_unknown_match_type(self):
        with self.assertRaises(ValueError):
            search_es.build_search_body("q", "text", size=5, match_type="bogus")


class ParseHitsTest(unittest.TestCase):
    def test_extracts_expected_fields_without_dropping_score(self):
        response = {
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {
                        "_score": 8.3,
                        "_source": {
                            "chunk_id": "msg-000001",
                            "sender_id": "user-001",
                            "sent_at": "2026-09-10T00:05:00",
                            "text": "저녁 약속 시간 정하자",
                        },
                    }
                ],
            }
        }

        results = search_es.parse_hits(response)

        self.assertEqual(1, len(results))
        self.assertEqual("msg-000001", results[0]["chunk_id"])
        self.assertEqual(8.3, results[0]["score"])

    def test_total_hits_reads_nested_value(self):
        response = {"hits": {"total": {"value": 17}, "hits": []}}

        self.assertEqual(17, search_es.total_hits(response))

    def test_total_hits_handles_plain_int_for_older_es_versions(self):
        response = {"hits": {"total": 4, "hits": []}}

        self.assertEqual(4, search_es.total_hits(response))


if __name__ == "__main__":
    unittest.main()
