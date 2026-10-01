"""Neo4j 적재기의 DB 비의존 단위 테스트."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import load_neo4j


class LoadNeo4jTests(unittest.TestCase):
    def test_edge_key_is_stable_and_chunk_sensitive(self):
        first = load_neo4j.make_edge_key("s", "partOf", "o", "chunk-1")
        again = load_neo4j.make_edge_key("s", "partOf", "o", "chunk-1")
        other_chunk = load_neo4j.make_edge_key("s", "partOf", "o", "chunk-2")

        self.assertEqual(first, again)
        self.assertNotEqual(first, other_chunk)

    def test_batches_cover_rows_without_overlap(self):
        rows = [{"id": number} for number in range(5)]
        result = list(load_neo4j.batches(rows, 2))

        self.assertEqual([len(batch) for batch in result], [2, 2, 1])
        self.assertEqual([row for batch in result for row in batch], rows)

    def test_merge_uses_only_node_identifier(self):
        for query in load_neo4j.NODE_QUERIES.values():
            merge_line = next(line.strip() for line in query.splitlines() if "MERGE" in line)
            self.assertIn("{id: row.id}", merge_line)
            self.assertNotIn("label:", merge_line)
            self.assertNotIn("purpose:", merge_line)

    def test_literal_predicates_are_not_relationships(self):
        self.assertEqual(
            set(load_neo4j.RELATION_TYPES),
            {"partOf", "usesTechnology", "replaces"},
        )

    def test_invalid_batch_size_fails(self):
        with self.assertRaises(ValueError):
            list(load_neo4j.batches([], 0))


if __name__ == "__main__":
    unittest.main()
