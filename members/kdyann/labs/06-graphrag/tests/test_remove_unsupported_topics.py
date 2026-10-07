import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from remove_unsupported_topics import unexpected_topic_relationships


class TopicCleanupTests(unittest.TestCase):
    def test_expected_paths_are_allowed_but_legacy_or_unowned_edges_abort(self):
        topic, assertion = "topic-id", "assertion-id"
        base = {"topic_id": topic, "properties": {}, "other_id": None}
        expected = [
            {**base, "type": "OBJECT", "start_id": assertion, "end_id": topic,
             "other_id": assertion, "other_labels": ["Assertion"]},
            {**base, "type": "COVERS_TOPIC", "start_id": "reference", "end_id": topic,
             "other_labels": ["Post", "ReferencePost"],
             "properties": {"source_fact_id": assertion}},
            {**base, "type": "IN_AREA", "start_id": topic, "end_id": None,
             "other_labels": ["InterestArea"], "properties": {"profile_id": "junyounge"}},
        ]
        self.assertEqual(unexpected_topic_relationships(expected, [assertion]), [])
        legacy = {**expected[-1], "type": "W5_CURATED_IN_AREA"}
        own = {**expected[1], "other_labels": ["Post", "OwnPost"]}
        unowned = {**expected[-1], "properties": {}}
        self.assertEqual(unexpected_topic_relationships([legacy, own, unowned], [assertion]),
                         [legacy, own, unowned])


if __name__ == "__main__":
    unittest.main()
