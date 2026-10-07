import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "05-content-graph" / "src"))
from enrich_interests import GRAPH_ID_PREFIX, PRESENTATION_FACTS, load_config, load_neo4j, post_caption, validate_config
from pipeline import BASE
from persist import RELATIONS


class InterestConfigTests(unittest.TestCase):
    def test_reviewed_mapping_is_valid(self):
        config = load_config(Path(__file__).resolve().parents[1] / "interests.json")
        self.assertEqual(config["profile_id"], "junyounge")
        self.assertEqual(config["topic_areas"]["NextJS"], "개발")
        self.assertEqual(config["interests"], ["개발", "앱", "AI", "게임", "야구"])
        self.assertEqual(config["topic_areas"]["야구"], "야구")
        self.assertEqual(config["topic_areas"]["AI 아이돌"], "AI")
        self.assertNotIn("computer software", config["topic_areas"])

    def test_post_caption_skips_comment_call_to_action(self):
        self.assertEqual(post_caption('Comment “PYTHON” to get the PDF.\n\nPython Complete Notes', 'id'),
                         'Python Complete Notes')

    def test_unlisted_area_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_config({"profile_id": "x", "interests": ["개발"],
                             "topic_areas": {"NextJS": "AI"}})

    def test_all_node_relationships_have_plain_presentation_types(self):
        self.assertEqual(GRAPH_ID_PREFIX, BASE)
        self.assertEqual(set(PRESENTATION_FACTS),
                         {name for name, (_, object_type) in RELATIONS.items() if object_type != "Literal"})

    def test_initial_and_repeat_load_accept_prepared_document_ids(self):
        class FakeDriver:
            def __init__(self):
                self.calls = []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def verify_connectivity(self):
                pass

            def execute_query(self, query, **params):
                self.calls.append((query, params))
                if "RETURN count(t) AS linked" in query:
                    return ([{"linked": 1}], None, None)
                if "RETURN count(r) AS count" in query or "RETURN count(fact) AS count" in query:
                    return ([{"count": 0}], None, None)
                return ([], None, None)

        driver = FakeDriver()
        config = {"profile_id": "junyounge", "interests": ["개발"], "topic_areas": {"Python": "개발"}}
        module = SimpleNamespace(GraphDatabase=SimpleNamespace(driver=lambda *_args, **_kwargs: driver))
        with patch.dict(sys.modules, {"neo4j": module}):
            for _ in range(2):
                result = load_neo4j(config, "bolt://example", "neo4j", "secret", documents=[
                    {"source_id": "post-1", "text": "Python 공부하기"}])
                self.assertEqual(result["mapped_topics"], 1)
        captions = [params for query, params in driver.calls if "SET n.display_name = CASE" in query]
        self.assertEqual(len(captions), 2)
        self.assertTrue(all(params["source_id"] == "post-1" for params in captions))
        self.assertTrue(all("n.post_number" in query for query, _ in driver.calls
                            if "SET n.display_name = CASE" in query))
        for query, params in driver.calls:
            if ("DELETE r" in query and ("W5_FACT" in query or "W5_CURATED_IN_AREA" in query)
                    or "REMOVE n:W5Entity" in query):
                self.assertEqual(params.get("graph_prefix"), GRAPH_ID_PREFIX)
        area_migrations = [query for query, _ in driver.calls if "REMOVE n:W5InterestArea" in query]
        self.assertTrue(area_migrations)
        self.assertTrue(all("NOT EXISTS" in query and "other.id" in query for query in area_migrations))
        curated_deletes = [query for query, _ in driver.calls
                           if "W5_CURATED_IN_AREA" in query and "DELETE r" in query]
        self.assertTrue(curated_deletes)
        self.assertTrue(all("r.profile_id" in query and "r.profile_id IS NULL" not in query
                            for query in curated_deletes))
        published = [(query, params) for query, params in driver.calls if ":PUBLISHED" in query]
        self.assertEqual(len(published), 2)
        self.assertTrue(all(params["profile_id"] == "junyounge"
                            and params["graph_prefix"] == GRAPH_ID_PREFIX for _, params in published))


if __name__ == "__main__":
    unittest.main()
