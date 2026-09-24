from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from knowledge_graph import graphviz_dot, load_graph, relevant_subgraph, validate_graph  # noqa: E402


class KnowledgeGraphTest(unittest.TestCase):
    def test_curated_graph_is_valid(self) -> None:
        graph = load_graph()
        self.assertGreaterEqual(len(graph["nodes"]), 10)
        self.assertGreaterEqual(len(graph["edges"]), 10)

    def test_unknown_edge_endpoint_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_graph(
                {
                    "nodes": [{"id": "known"}],
                    "edges": [{"source": "known", "target": "missing", "type": "AFFECTS"}],
                }
            )

    def test_certificate_query_expands_one_hop(self) -> None:
        graph = relevant_subgraph(load_graph(), "인증서 만료 조치")
        node_ids = {node["id"] for node in graph["nodes"]}
        self.assertIn("incident:inc-003", node_ids)
        self.assertIn("action:renew-certificate", node_ids)
        self.assertIn("action:restart-static-pod", node_ids)

    def test_graphviz_contains_relation_labels(self) -> None:
        dot = graphviz_dot(relevant_subgraph(load_graph(), "인증서"))
        self.assertIn("RESOLVED_BY", dot)
        self.assertIn("kubeadm 인증서 갱신", dot)


if __name__ == "__main__":
    unittest.main()
