"""5주차 store_kg의 DB 비의존 단위 테스트."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import store_kg


def extraction(chunk_id, project_label, tech_label, purpose="캐시", status="implemented"):
    entities = [
        {"id": "kg:bad-project", "type": "Project", "label": project_label, "props": {}},
        {"id": "kg:bad-tech", "type": "Technology", "label": tech_label, "props": {}},
        {
            "id": "kg:bad-use",
            "type": "TechnologyUse",
            "label": "임의 사용례",
            "props": {"purpose": purpose, "status": status},
        },
    ]
    triples = [
        {"subject": "kg:bad-use", "predicate": "partOf", "object": "kg:bad-project", "evidence": "e1", "confidence": 1.0},
        {"subject": "kg:bad-use", "predicate": "usesTechnology", "object": "kg:bad-tech", "evidence": "e2", "confidence": 1.0},
        {"subject": "kg:bad-use", "predicate": "hasPurpose", "object": purpose, "evidence": "e3", "confidence": 0.9},
        {"subject": "kg:bad-use", "predicate": "hasStatus", "object": status, "evidence": "e4", "confidence": 0.9},
    ]
    return {"chunk_id": chunk_id, "entities": entities, "triples": triples, "rejected": [], "error": None}


class NormalizeTests(unittest.TestCase):
    def test_label_aliases_and_ids_are_canonicalized(self):
        data = store_kg.normalize_records([extraction("c1", "SeCause!!", "레디스")])

        self.assertIn("kg:secause", data.entities)
        self.assertIn("kg:tech-redis", data.entities)
        self.assertIn("kg:use-secause-redis-1", data.entities)
        self.assertEqual(data.entities["kg:tech-redis"]["label"], "redis")

    def test_same_use_across_chunks_merges_entity_but_keeps_evidence_edges(self):
        records = [
            extraction("c1", "SeCause", "Redis"),
            extraction("c2", "secause", "redis"),
        ]
        data = store_kg.normalize_records(records)

        uses = [e for e in data.entities.values() if e["type"] == "TechnologyUse"]
        self.assertEqual(len(uses), 1)
        self.assertEqual(data.merged_count, 3)
        part_of_edges = [e for e in data.edges if e["predicate"] == "partOf"]
        self.assertEqual({edge["chunk_id"] for edge in part_of_edges}, {"c1", "c2"})

    def test_different_purpose_gets_stable_separate_use_numbers(self):
        records = [
            extraction("c2", "직행", "Redis", purpose="통근 시간 캐시", status="proposed"),
            extraction("c1", "ZIGHANG", "레디스", purpose="테스트 결과 저장", status="implemented"),
        ]
        data = store_kg.normalize_records(records)

        uses = sorted(
            e["entity_id"] for e in data.entities.values() if e["type"] == "TechnologyUse"
        )
        self.assertEqual(
            uses,
            ["kg:use-jikhaeng-redis-1", "kg:use-jikhaeng-redis-2"],
        )

    def test_same_chunk_duplicate_edge_is_removed_before_db_insert(self):
        record = extraction("c1", "SeCause", "Redis")
        record["triples"].append(dict(record["triples"][0]))
        data = store_kg.normalize_records([record])

        count = len([edge for edge in data.edges if edge["predicate"] == "partOf"])
        self.assertEqual(count, 1)

    def test_error_record_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.jsonl"
            path.write_text(
                json.dumps({"chunk_id": "c1", "entities": [], "triples": [], "error": "boom"})
                + "\n",
                encoding="utf-8",
            )
            data = store_kg.normalize_records(store_kg.load_jsonl(path))

        self.assertEqual(data.skipped_errors, 1)
        self.assertEqual(data.entities, {})


if __name__ == "__main__":
    unittest.main()
