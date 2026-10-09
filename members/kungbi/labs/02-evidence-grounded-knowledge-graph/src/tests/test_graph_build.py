"""All literals and source records in these public tests are synthetic."""
import json
import re
import unittest

from graph.build_graph import make_identity_id, normalize_pr_link, unique_slack_threads
from graph.validate_graph import validate_graph


class GraphBuildTests(unittest.TestCase):
    def test_pr_link_normalizes_repository_and_number(self):
        result = normalize_pr_link("<https://github.com/example-org/Synthetic_Client/pull/7|#7>")
        self.assertEqual(result, ("synthetic_client", 7))

    def test_identity_id_is_opaque_and_source_scoped(self):
        slack = make_identity_id("slack", "synthetic-slack-user")
        github = make_identity_id("github", "synthetic-github-user")
        self.assertNotIn("synthetic-slack-user", slack)
        self.assertNotIn("synthetic-github-user", github)
        self.assertNotEqual(slack, github)

    def test_slack_threads_deduplicate_by_channel_and_parent_timestamp(self):
        records = [
            {"channel_id": "C1", "thread_ts": "1.0", "id": "chunk-a"},
            {"channel_id": "C1", "thread_ts": "1.0", "id": "chunk-b"},
            {"channel_id": "C2", "thread_ts": "1.0", "id": "chunk-c"},
        ]
        unique = unique_slack_threads(records)
        self.assertEqual(len(unique), 2)
        self.assertEqual({(x["channel_id"], x["thread_ts"]) for x in unique}, {("C1", "1.0"), ("C2", "1.0")})

    def test_graph_validation_rejects_dangling_edge(self):
        nodes = [{"id": "case:one", "labels": ["Case"], "properties": {"dataset_id": "kg"}}]
        edges = [{"edge_id": "e1", "source_id": "case:one", "target_id": "missing", "type": "INCLUDES", "properties": {}}]
        report = validate_graph(nodes, edges, allowed_relationships={"INCLUDES"}, evidence_ids=set())
        self.assertFalse(report["valid"])
        self.assertIn("dangling_target:missing", report["errors"])

    def test_graph_validation_rejects_raw_identity_fields(self):
        nodes = [{"id": "identity:slack:abc", "labels": ["Identity"], "properties": {"dataset_id": "kg", "github_login": "synthetic-handle"}}]
        report = validate_graph(nodes, [], allowed_relationships=set(), evidence_ids=set())
        self.assertFalse(report["valid"])
        self.assertIn("private_field:github_login", report["errors"])


if __name__ == "__main__":
    unittest.main()
