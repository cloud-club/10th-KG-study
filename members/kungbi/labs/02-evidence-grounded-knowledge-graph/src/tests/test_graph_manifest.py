"""All literals and source records in these public tests are synthetic."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GraphManifestTests(unittest.TestCase):

    def test_schema_requires_provenance_and_excludes_private_fields(self):
        schema = json.loads((ROOT / "graph/schema.json").read_text())
        required = set(schema["relationship_provenance_required"])
        self.assertTrue({"evidence_chunk_ids", "evidence_quote", "review_status", "basis"} <= required)
        self.assertIn("github_login", schema["private_fields_never_written_to_neo4j"])
        self.assertIn("canonical_arn", schema["private_fields_never_written_to_neo4j"])




if __name__ == "__main__":
    unittest.main()
