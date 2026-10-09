import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from text2cypher import TEMPLATES, run_one, validate_generated


class RecordingGraph:
    def __init__(self):
        self.calls = []

    def query(self, cypher, **params):
        self.calls.append((cypher, params))
        return [{"count": 7}]


class Text2CypherValidationTests(unittest.TestCase):
    def test_free_aggregate_aliases_compile_to_scoped_query(self):
        cases = [
            ("MATCH (post:OwnPost) WHERE post.source_id IN $allowed_ids "
             "RETURN count(DISTINCT post) AS total LIMIT 20", "own_count", ""),
            ("MATCH (post:OwnPost:Post)-[:COVERS_TOPIC]->(topic:Topic) "
             "WHERE topic.name = $topic AND post.source_id IN $allowed_ids "
             "RETURN count(DISTINCT post) AS post_count LIMIT 20", "own_topic_count", "야구"),
            ("MATCH (post:OwnPost)-[:COVERS_TOPIC]->(topic:Topic) "
             "WHERE post.source_id IN $allowed_ids "
             "RETURN topic.name AS subject, count(DISTINCT post) AS n "
             "ORDER BY n DESC LIMIT 1", "top_own_topics", ""),
        ]
        for raw, route, topic in cases:
            with self.subTest(route=route):
                graph = RecordingGraph()
                result = run_one("질문", graph, {"b", "a"},
                                 lambda _q: {"cypher": raw, "topic": topic})
                self.assertEqual(result["status"], "success")
                self.assertEqual(result["route"], route)
                self.assertEqual(result["query_handling"], "compiled_safe_aggregate")
                self.assertEqual(result["generated"]["cypher"], raw)
                self.assertEqual(graph.calls[0][1]["allowed_ids"], ["a", "b"])
                self.assertNotIn("post:", graph.calls[0][0])
                if route == "top_own_topics":
                    self.assertTrue(graph.calls[0][0].endswith("LIMIT 1"))

    def test_exact_guided_template_is_identified(self):
        graph = RecordingGraph()
        result = run_one("질문", graph, {"a"},
                         lambda _q: {"cypher": TEMPLATES["own_topic_count"], "topic": "야구"})
        self.assertEqual(result["query_handling"], "exact_template")

    def test_profile_path_free_aggregates_keep_profile_existence(self):
        queries = [
            ("MATCH (profile:Profile)-[:PUBLISHED]->(p:OwnPost)-[:COVERS_TOPIC]->"
             "(t:Topic {name: $topic}) WHERE p.source_id IN $allowed_ids "
             "RETURN count(DISTINCT p) AS post_count LIMIT 20", "야구", "own_topic_count"),
            ("MATCH (pr:Profile)-[:PUBLISHED]->(p:OwnPost)-[:COVERS_TOPIC]->(t:Topic) "
             "WHERE p.source_id IN $allowed_ids WITH t.name AS topic, "
             "count(DISTINCT p) AS postCount RETURN topic, postCount "
             "ORDER BY postCount DESC LIMIT 20", "", "top_own_topics"),
        ]
        for raw, topic, route in queries:
            with self.subTest(route=route):
                graph = RecordingGraph()
                result = run_one("집계 질문", graph, {"a"},
                                 lambda _q: {"cypher": raw, "topic": topic})
                self.assertEqual(result["status"], "success")
                self.assertEqual(result["route"], route)
                self.assertEqual(result["query_handling"], "compiled_safe_aggregate")
                self.assertIn("(:Profile)-[:PUBLISHED]->", graph.calls[0][0])
                self.assertEqual(graph.calls[0][1]["allowed_ids"], ["a"])

    def test_mutations_schema_escapes_and_unscoped_queries_are_rejected(self):
        valid = ("MATCH (p:OwnPost)-[:COVERS_TOPIC]->(t:Topic) "
                 "WHERE p.source_id IN $allowed_ids AND t.name = $topic "
                 "RETURN count(DISTINCT p) AS count LIMIT 1")
        invalid = [
            valid + " SET p.flag = true",
            valid + " CALL db.labels()",
            valid.replace("OwnPost", "Person"),
            valid.replace("p.source_id IN $allowed_ids AND ", ""),
            valid.replace("COVERS_TOPIC", "MENTIONS"),
            valid.replace("count(DISTINCT p)", "count(p)"),
            valid.replace("LIMIT 1", "LIMIT 21"),
            valid.replace("$topic", "'야구'"),
            valid + "; MATCH (n) DETACH DELETE n",
            ("MATCH (pr:Profile)-[:PUBLISHED]->(p:OwnPost)-[:COVERS_TOPIC]->(t:Topic) "
             "WHERE p.source_id IN $allowed_ids WITH t.name AS topic, "
             "count(DISTINCT p) AS postCount RETURN topic, postCount "
             "ORDER BY postCount DESC LIMIT 20 CALL db.labels()"),
        ]
        for raw in invalid:
            with self.subTest(raw=raw):
                graph = RecordingGraph()
                result = run_one("질문", graph, {"a"},
                                 lambda _q: {"cypher": raw, "topic": "야구"})
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(graph.calls, [])

    def test_topic_parameter_is_required_for_topic_count(self):
        query = ("MATCH (p:OwnPost)-[:COVERS_TOPIC]->(t:Topic) "
                 "WHERE p.source_id IN $allowed_ids AND t.name = $topic "
                 "RETURN count(DISTINCT p) AS count LIMIT 20")
        with self.assertRaises(ValueError):
            validate_generated({"cypher": query, "topic": ""})


if __name__ == "__main__":
    unittest.main()
