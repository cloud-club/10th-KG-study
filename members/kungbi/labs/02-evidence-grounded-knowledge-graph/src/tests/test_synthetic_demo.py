"""End-to-end public integration tests using only clearly invented fixtures."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from graph.build_graph import ROOT, MANIFEST_PATH, build_graph
from graph.ids import make_identity_id
from graph.validate_graph import load_identity_approvals
from synthetic_demo import run_demo


class SyntheticDemoTests(unittest.TestCase):
    def test_synthetic_build_validates_and_compiles_loader_queries(self):
        report = run_demo()
        self.assertIn('SYNTHETIC', report['label'])
        self.assertTrue(report['validation']['valid'])
        self.assertEqual(report['build']['case_count'], 1)
        self.assertEqual(report['build']['selected_pr_count'], 1)
        self.assertEqual(report['parameterized_query_rows']['nodes'], report['build']['node_count'])
        self.assertEqual(report['parameterized_query_rows']['edges'], report['build']['edge_count'])
        self.assertFalse(report['network_or_database_used'])

    def test_authorship_and_slack_contribution_are_distinct(self):
        nodes, edges, _ = build_graph()
        by_type = {e['type']: e for e in edges}
        self.assertEqual(by_type['AUTHORED']['source_id'], make_identity_id('github', 'synthetic-github'))
        self.assertEqual(by_type['CONTRIBUTED_TO']['source_id'], make_identity_id('slack', 'synthetic-slack'))
        self.assertEqual(by_type['LINKS_TO']['properties']['basis'], 'explicit_permalink')
        self.assertEqual(sum(n['labels'] == ['Person'] for n in nodes), 1)

    def test_shared_case_without_permalink_does_not_create_link(self):
        import graph.build_graph as builder
        original = builder._jsonl
        def without_permalink(path):
            for row in original(path):
                if path.name == 'synthetic.jsonl':
                    row = {**row, 'text': 'Synthetic discussion without an explicit link.'}
                yield row
        with patch.object(builder, '_jsonl', side_effect=without_permalink):
            _, edges, _ = builder.build_graph()
        self.assertFalse(any(e['type'] in {'LINKS_TO', 'CONTRIBUTED_TO'} for e in edges))

    def test_approval_requires_status_and_unique_complete_mapping(self):
        approved = json.loads((ROOT / 'fixtures/synthetic-approvals.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'synthetic-approvals.json'
            for data, error in [
                ({**approved, 'approval': {'status': 'candidate'}}, 'identity_approval_missing'),
                ({**approved, 'mappings': approved['mappings'] * 2}, 'identity_approval_count_invalid'),
                ({**approved, 'mappings': [{'person_id': 'person:synthetic'}]}, 'identity_mapping_incomplete'),
            ]:
                p.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, error):
                    load_identity_approvals(p)
