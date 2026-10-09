"""All literals and source records in these public tests are synthetic."""
import json
import unittest
from pathlib import Path

from graph.loader import build_node_cypher, build_relationship_cypher, build_schema_statements


class LoaderQueryTests(unittest.TestCase):
    def test_node_query_uses_allowlisted_labels_and_properties(self):
        query, params = build_node_cypher([{"id": "case:1", "labels": ["Case"], "properties": {"dataset_id": "kg", "label": "demo"}}])
        self.assertIn(":GraphNode:Case", query)
        self.assertEqual(params["rows"][0]["id"], "case:1")
        self.assertNotIn("MERGE (n:Case", query)

    def test_relationship_query_uses_allowlisted_type_via_graph_edge(self):
        query, params = build_relationship_cypher([{"edge_id": "e1", "source_id": "a", "target_id": "b", "type": "INCLUDES", "properties": {"dataset_id": "kg"}}])
        self.assertIn(":GRAPH_EDGE", query)
        self.assertIn("r.type", query)
        self.assertEqual(params["rows"][0]["type"], "INCLUDES")

    def test_schema_statements_create_unique_node_and_edge_constraints(self):
        statements = build_schema_statements()
        self.assertTrue(any("n.id IS UNIQUE" in query for query in statements))
        self.assertTrue(any("r.edge_id IS UNIQUE" in query for query in statements))

if __name__ == "__main__":
    unittest.main()
