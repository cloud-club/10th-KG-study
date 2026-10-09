"""All literals and source records in these public tests are synthetic."""
import unittest

from graph.validate_graph import validate_graph


class GraphValidationTests(unittest.TestCase):
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

    def test_graph_validation_rejects_unapproved_identity_merge(self):
        nodes = [
            {"id": "identity:a", "labels": ["Identity"], "properties": {}},
            {"id": "person:a", "labels": ["Person"], "properties": {}},
        ]
        edge = {"edge_id": "e1", "source_id": "identity:a", "target_id": "person:a", "type": "IDENTITY_OF",
                "properties": {"dataset_id": "kg", "case_ids": [], "source_system": "extractor",
                               "source_record_id": "r", "evidence_chunk_ids": [], "evidence_quote": "same name",
                               "extraction_method": "heuristic", "basis": "name_similarity",
                               "review_status": "candidate", "confidence": "medium"}}
        report = validate_graph(nodes, [edge], allowed_relationships={"IDENTITY_OF"}, evidence_ids=set())
        self.assertFalse(report["valid"])
        self.assertIn("unapproved_identity_merge:e1", report["errors"])


if __name__ == "__main__":
    unittest.main()
