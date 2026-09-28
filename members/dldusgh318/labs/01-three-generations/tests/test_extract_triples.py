"""5주차 extract_triples의 API 비의존 단위 테스트."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import extract_triples as et


class ParseResponseTests(unittest.TestCase):
    def test_parses_plain_json(self):
        self.assertEqual(et.parse_json_response('{"entities":[],"triples":[]}'), et.EMPTY_OUTPUT)

    def test_strips_json_code_fence(self):
        fenced = "응답입니다.\n```json\n{\"entities\": [], \"triples\": []}\n```"
        self.assertEqual(et.parse_json_response(fenced), et.EMPTY_OUTPUT)


class RetryTests(unittest.TestCase):
    @mock.patch.object(et, "call_openai")
    def test_normal_response_calls_api_once(self, call):
        call.return_value = '{"entities":[],"triples":[]}'
        result = et.extract_with_retries("key", "model", "text", 100, 10)
        self.assertEqual(result, et.EMPTY_OUTPUT)
        self.assertEqual(call.call_count, 1)

    @mock.patch.object(et, "call_openai")
    def test_json_parse_failure_retries_at_most_twice(self, call):
        call.return_value = "not json"
        with self.assertRaises(et.ExtractionError):
            et.extract_with_retries("key", "model", "text", 100, 10)
        self.assertEqual(call.call_count, 3)  # 최초 1회 + 재시도 2회


class SchemaTests(unittest.TestCase):
    def test_type_and_predicate_are_enums(self):
        entity = et.OUTPUT_SCHEMA["properties"]["entities"]["items"]
        triple = et.OUTPUT_SCHEMA["properties"]["triples"]["items"]
        self.assertEqual(entity["properties"]["type"]["enum"], list(et.ENTITY_TYPES))
        self.assertEqual(triple["properties"]["predicate"]["enum"], list(et.PREDICATES))

    def test_request_uses_openai_strict_structured_output(self):
        request = et.build_request("gpt-test", "본문", 100)
        output_format = request["text"]["format"]
        self.assertEqual(output_format["type"], "json_schema")
        self.assertTrue(output_format["strict"])
        self.assertEqual(output_format["schema"], et.OUTPUT_SCHEMA)
        self.assertNotIn("output_config", request)

    def test_messages_contain_positive_and_empty_few_shots(self):
        messages = et.build_messages("실제 청크")
        self.assertEqual(len(messages), 5)
        self.assertEqual(json.loads(messages[1]["content"]), et.POSITIVE_OUTPUT)
        self.assertEqual(json.loads(messages[3]["content"]), {"entities": [], "triples": []})


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.entities = [
            {"id": "kg:p", "type": "Project", "label": "P", "props": {}},
            {"id": "kg:tech-redis", "type": "Technology", "label": "Redis", "props": {}},
            {"id": "kg:use-p-redis-1", "type": "TechnologyUse", "label": "사용", "props": {}},
        ]
        self.text = "P는 작업 큐에\nRedis를 사용한다."

    def triple(self, **overrides):
        value = {
            "subject": "kg:use-p-redis-1",
            "predicate": "usesTechnology",
            "object": "kg:tech-redis",
            "evidence": "P는 작업 큐에 Redis를 사용한다.",
            "confidence": 0.9,
        }
        value.update(overrides)
        return value

    def validate_one(self, triple):
        return et.validate_extraction({"entities": self.entities, "triples": [triple]}, self.text)

    def test_accepts_evidence_after_whitespace_normalization(self):
        accepted, rejected = self.validate_one(self.triple())
        self.assertEqual(len(accepted), 1)
        self.assertEqual(rejected, [])

    def test_rejects_in_required_order(self):
        cases = [
            (self.triple(predicate="invented", subject="kg:missing", evidence="없음"), "unknown_predicate"),
            (self.triple(subject="kg:missing", evidence="없음"), "dangling_subject"),
            (self.triple(subject="kg:p", evidence="없는 근거"), "evidence_not_found"),
            (self.triple(subject="kg:p"), "domain_mismatch"),
            (self.triple(object="kg:p"), "range_mismatch"),
        ]
        for triple, reason in cases:
            with self.subTest(reason=reason):
                accepted, rejected = self.validate_one(triple)
                self.assertEqual(accepted, [])
                self.assertEqual(rejected[0]["reason"], reason)

    def test_status_accepts_only_fixed_values(self):
        triple = self.triple(predicate="hasStatus", object="done")
        _, rejected = self.validate_one(triple)
        self.assertEqual(rejected[0]["reason"], "range_mismatch")


class ResumeTests(unittest.TestCase):
    def test_reads_legacy_id_as_chunk_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chunks.jsonl"
            path.write_text('{"id":"legacy-1","text":"본문"}\n', encoding="utf-8")
            self.assertEqual(et.read_jsonl(path)[0]["chunk_id"], "legacy-1")

    def test_reads_completed_chunk_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "extracted.jsonl"
            path.write_text('{"chunk_id":"c1"}\n{"chunk_id":"c2"}\n', encoding="utf-8")
            self.assertEqual(et.completed_chunk_ids(path), {"c1", "c2"})

    def test_failed_chunks_are_retried_and_removed_before_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "extracted.jsonl"
            path.write_text(
                '{"chunk_id":"ok","error":null}\n'
                '{"chunk_id":"retry","error":"HTTP 401"}\n',
                encoding="utf-8",
            )
            self.assertEqual(et.completed_chunk_ids(path), {"ok"})
            self.assertEqual(et.remove_failed_results(path), 1)
            self.assertEqual(path.read_text(encoding="utf-8"), '{"chunk_id":"ok","error":null}\n')


if __name__ == "__main__":
    unittest.main()
