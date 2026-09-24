from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from graph_retrieval import graph_evidence, merge_evidence  # noqa: E402
from knowledge_graph import load_graph  # noqa: E402


class GraphRetrievalTest(unittest.TestCase):
    def test_graph_nodes_resolve_to_source_chunks(self) -> None:
        chunks = [
            {
                "chunk_id": "inc#원인",
                "source_path": "troubleshooting/INC-003-apiserver-etcd-tls-expiry.md",
                "heading": "원인",
            },
            {
                "chunk_id": "other",
                "source_path": "unrelated.md",
                "heading": None,
            },
        ]
        rows = graph_evidence("인증서 만료 원인", load_graph(), chunks)
        self.assertEqual(["inc#원인"], [row["chunk_id"] for row in rows])

    def test_merge_preserves_primary_and_removes_duplicates(self) -> None:
        a = {"chunk_id": "a"}
        b = {"chunk_id": "b"}
        c = {"chunk_id": "c"}
        rows = merge_evidence([a, b], [b, c], limit=3)
        self.assertEqual(["a", "b", "c"], [row["chunk_id"] for row in rows])


if __name__ == "__main__":
    unittest.main()
