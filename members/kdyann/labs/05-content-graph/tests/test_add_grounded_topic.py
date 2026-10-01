import json
import sys
import tempfile
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))
import add_grounded_topic
import pipeline


class AddGroundedTopicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name)
        documents = [{"id": "own-1", "corpus": "own", "text": "Claude Code로 디자인해요. #ai"}]
        pipeline.run(documents, {"own-1": {"facts": []}}, self.output)

    def test_adds_grounded_topic_and_regenerates_both_rdf_formats(self):
        result = add_grounded_topic.add_topic(self.output, "own-1", "AI", "#ai")
        self.assertEqual(result, {"documents": 1, "facts": 1, "added": True})
        fact = pipeline._read_jsonl(self.output / "facts.jsonl")[0]
        self.assertEqual(fact["predicate"], "coversTopic")
        self.assertEqual(fact["object_name"], "AI")
        self.assertEqual(fact["evidence"], "#ai")
        self.assertEqual("Claude Code로 디자인해요. #ai"[fact["start"]:fact["end"]], "#ai")
        self.assertIn("coversTopic", (self.output / "graph.ttl").read_text())
        self.assertIn(pipeline.BASE + "coversTopic", (self.output / "graph.jsonld").read_text())
        again = add_grounded_topic.add_topic(self.output, "own-1", "ai", "#ai")
        self.assertFalse(again["added"])
        self.assertEqual(again["facts"], 1)

    def test_rejects_missing_or_ambiguous_evidence_without_changes(self):
        before = {name: (self.output / name).read_bytes() for name in
                  ("facts.jsonl", "graph.ttl", "graph.jsonld")}
        with self.assertRaises(pipeline.ValidationError):
            add_grounded_topic.add_topic(self.output, "own-1", "AI", "없는 근거")
        with self.assertRaises(pipeline.ValidationError):
            add_grounded_topic.add_topic(self.output, "own-1", "AI", "디자인", start=0)
        for name, content in before.items():
            self.assertEqual((self.output / name).read_bytes(), content)
        (self.output / "documents.jsonl").write_text(json.dumps({
            "id": "own-1", "corpus": "own", "text": "#ai 그리고 #ai"
        }, ensure_ascii=False) + "\n")
        with self.assertRaisesRegex(pipeline.ValidationError, "여러 번"):
            add_grounded_topic.add_topic(self.output, "own-1", "AI", "#ai")
        self.assertTrue(add_grounded_topic.add_topic(self.output, "own-1", "AI", "#ai", start=8)["added"])


if __name__ == "__main__":
    unittest.main()
