"""실제 DB 없이 적재 전 자료 무결성과 재실행 안정성을 확인한다."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))
import persist


class PersistPreparationTests(unittest.TestCase):
    def setUp(self):
        self.documents = [
            {"id": "own-1", "corpus": "own", "text": "AI 디자인을 다룹니다.",
             "published_at": "2026-09-20T00:00:00+0000"},
            {"id": "ref-1", "corpus": "reference", "text": "AI 디자인 사례입니다.",
             "published_at": "2026-09-29T00:00:00+0000",
             "collected_at": "2026-09-30T00:00:00+00:00",
             "selection": {"score": 0.03, "observed_likes": 1200, "observed_comments": 80}},
        ]
        self.facts = [
            {"source_id": "own-1", "subject_type": "Post", "subject_name": "own-1",
             "predicate": "coversTopic", "object_type": "Topic", "object_name": "AI 디자인",
             "evidence": "AI 디자인", "start": 0, "end": 6},
            {"source_id": "ref-1", "subject_type": "Post", "subject_name": "ref-1",
             "predicate": "coversTopic", "object_type": "Topic", "object_name": "AI 디자인",
             "evidence": "AI 디자인", "start": 0, "end": 6},
        ]

    def test_shared_topic_has_two_sourced_edges_and_metrics(self):
        records = persist.prepare(self.documents, self.facts)
        topics = [x for x in records["entities"] if x["entity_type"] == "Topic"]
        self.assertEqual(len(topics), 1)
        self.assertEqual(len(records["edges"]), 2)
        self.assertEqual({x["source_id"] for x in records["evidence"]}, {"own-1", "ref-1"})
        self.assertEqual(records["documents"][1]["observed_likes"], 1200)
        self.assertEqual(records["documents"][1]["selection_score"], 0.03)
        self.assertEqual(persist.prepare(self.documents, self.facts), records)

    def test_evidence_rejected_when_offset_does_not_match(self):
        broken = [dict(self.facts[0], start=1), self.facts[1]]
        with self.assertRaises(persist.ValidationError):
            persist.prepare(self.documents, broken)

    def test_repeated_fact_coalesces_edge_but_preserves_distinct_evidence(self):
        doc = {"id": "x", "corpus": "own", "text": "AI 디자인. AI 디자인."}
        fact = {"source_id": "x", "subject_type": "Post", "subject_name": "x",
                "predicate": "coversTopic", "object_type": "Topic", "object_name": "AI 디자인",
                "evidence": "AI 디자인", "start": 0, "end": 6}
        second = dict(fact, start=8, end=14)
        result = persist.prepare([doc], [fact, second])
        self.assertEqual(len(result["edges"]), 1)
        self.assertEqual(len(result["evidence"]), 2)

    def test_literal_becomes_assertion_not_entity(self):
        doc = {"id": "x", "corpus": "own", "text": "iOS에서 출시했습니다."}
        fact = {"source_id": "x", "subject_type": "Post", "subject_name": "x",
                "predicate": "availableOn", "object_type": "Literal", "object_name": "iOS",
                "evidence": "iOS에서 출시했습니다.", "start": 0, "end": len(doc["text"])}
        with patch.dict(persist.RELATIONS, {"availableOn": ("Post", "Literal")}):
            result = persist.prepare([doc], [fact])
        self.assertEqual(len(result["entities"]), 1)
        self.assertIsNone(result["edges"][0]["object_id"])
        self.assertEqual(result["edges"][0]["object_literal"], "iOS")


if __name__ == "__main__":
    unittest.main()
