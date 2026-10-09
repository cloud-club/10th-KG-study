"""All literals and source records in these public tests are synthetic."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from graph import build_graph as builder
from graph import loader
from graph.validate_graph import validate_graph


class AWSSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = {k: self.root / (k + '.jsonl') for k in ('aws_resources', 'aws_relations', 'aws_chunks', 'github_chunks')}
        self.paths['aws_bindings'] = self.root / 'bindings.json'
        self.paths['github_payload_root'] = self.root / 'payloads'
        self.paths['github_payload_root'].mkdir()
        repo = self.paths['github_payload_root'] / 'repo'
        repo.mkdir()
        self.patch_text = "+const SOURCE = 'exact-source';\n+const DETAIL_TYPE = 'ExactEvent';\n+EventBusName: process.env.EVENT_BUS_NAME\n+Source: SOURCE,\n+DetailType: DETAIL_TYPE,"
        self.write_rows(repo / 'pull-files.jsonl', [{'pull_number': 1, 'repository': 'repo', 'raw': {'filename': 'publisher.ts', 'patch': self.patch_text}}])
        self.resources = [
            {'resource_id': 'synthetic-rule-id', 'resource_name': 'synthetic-rule', 'resource_arn': 'arn:aws:events:region:000000000000:rule/synthetic-rule', 'account_id': '000000000000', 'region': 'region', 'service_name': 'events', 'resource_type': 'rule', 'configuration': {'EventPattern': json.dumps({'source': ['exact-source'], 'detail-type': ['ExactEvent']}), 'EventBusName': 'synthetic-bus'}},
            {'resource_id': 'synthetic-bus-id', 'resource_name': 'synthetic-bus', 'resource_arn': 'arn:aws:events:region:000000000000:event-bus/synthetic-bus', 'account_id': '000000000000', 'region': 'region', 'service_name': 'events', 'resource_type': 'event_bus', 'configuration': {}},
        ]
        self.write_rows(self.paths['aws_resources'], self.resources)
        self.write_rows(self.paths['aws_relations'], [{'source_resource_id': 'synthetic-rule-id', 'target_resource_id': None, 'relation_type': 'invokes', 'unresolved_target': 'arn:aws:sqs:region:000000000000:missing'}])
        self.write_rows(self.paths['aws_chunks'], [{'source_record_id': a['resource_id'], 'retrieval_chunk_id': 'aws-chunk-' + str(i)} for i, a in enumerate(self.resources)])
        self.write_rows(self.paths['github_chunks'], [{'citation': {'repository': 'repo', 'item_type': 'pull_request', 'item_number': 1}, 'retrieval_chunk_id': 'github-chunk'}])
        self.bindings = {'bindings': [{'case_id': 'case:test', 'pull_request': 'repo#1', 'file_path': 'publisher.ts', 'source': 'exact-source', 'detail_type': 'ExactEvent', 'rule_resource_id': 'synthetic-rule-id', 'bus_resource_id': 'synthetic-bus-id'}]}
        self.save_bindings()
        self.nodes = {'case:test': {'id': 'case:test', 'labels': ['Case'], 'properties': {'dataset_id': builder.DATASET_ID}}, 'github:repo#1': {'id': 'github:repo#1', 'labels': ['PullRequest'], 'properties': {'dataset_id': builder.DATASET_ID}}, 'file:repo:publisher.ts': {'id': 'file:repo:publisher.ts', 'labels': ['CodeFile'], 'properties': {'dataset_id': builder.DATASET_ID}}}

    def write_rows(self, path, rows):
        path.write_text(''.join(json.dumps(x) + '\n' for x in rows))

    def save_bindings(self):
        self.paths['aws_bindings'].write_text(json.dumps(self.bindings))

    def augment(self):
        from graph.aws_snapshot import add_aws_snapshot
        edges = {}
        report = add_aws_snapshot(self.paths, self.nodes, edges, {'repo#1': {'case:test'}})
        return list(self.nodes.values()), list(edges.values()), report

    def test_exact_contract_links_are_anonymous_and_do_not_claim_delivery(self):
        nodes, edges, report = self.augment()
        aws = [n for n in nodes if n['labels'] == ['AWSResource']]
        self.assertEqual(len(aws), 2)
        serialized = json.dumps([aws, edges])
        for secret in ('000000000000', 'synthetic-bus', 'synthetic-rule', 'synthetic-rule-id', 'synthetic-bus-id', 'arn:aws:', 'exact-source', 'ExactEvent'):
            self.assertNotIn(secret, serialized)
        self.assertEqual(sum(e['properties']['basis'] == 'exact_event_contract_match' for e in edges), 1)
        self.assertEqual(sum(e['properties']['basis'] == 'snapshot_event_bus_membership' for e in edges), 1)
        self.assertFalse(any(e['type'] in ('DECLARES_TARGET', 'INVOKES') for e in edges))
        self.assertEqual(report['unresolved_target_count'], 1)
        for n in aws:
            self.assertTrue(n['properties']['evidence_chunk_ids'])
        valid = validate_graph(nodes, edges, {'RELATED_TO', 'INCLUDES'}, {'aws-chunk-0', 'aws-chunk-1', 'github-chunk'})
        self.assertTrue(valid['valid'], valid['errors'])

    def test_near_event_name_is_not_a_binding(self):
        self.resources[0]['configuration']['EventPattern'] = json.dumps({'source': ['exact-source'], 'detail-type': ['ExactEventV2']})
        self.write_rows(self.paths['aws_resources'], self.resources)
        with self.assertRaisesRegex(ValueError, 'aws_event_contract_mismatch'):
            self.augment()

    def test_bus_name_match_in_other_account_is_rejected(self):
        self.resources[1]['account_id'] = '111111111111'
        self.write_rows(self.paths['aws_resources'], self.resources)
        with self.assertRaisesRegex(ValueError, 'aws_bus_scope_mismatch'):
            self.augment()

    def test_missing_snapshot_chunk_is_rejected(self):
        self.write_rows(self.paths['aws_chunks'], [])
        with self.assertRaisesRegex(ValueError, 'aws_snapshot_chunk_missing'):
            self.augment()

    def test_missing_code_literal_is_rejected(self):
        self.write_rows(self.paths['github_payload_root'] / 'repo/pull-files.jsonl', [{'pull_number': 1, 'repository': 'repo', 'raw': {'filename': 'publisher.ts', 'patch': self.patch_text.replace('ExactEvent', 'OtherEvent')}}])
        with self.assertRaisesRegex(ValueError, 'aws_code_contract_mismatch'):
            self.augment()

    def test_unselected_pr_is_rejected(self):
        self.bindings['bindings'][0]['pull_request'] = 'repo#2'
        self.save_bindings()
        with self.assertRaisesRegex(ValueError, 'aws_binding_outside_case'):
            self.augment()

    def test_validator_rejects_arn_in_aws_properties(self):
        n = {'id': 'aws:opaque', 'labels': ['AWSResource'], 'properties': {'dataset_id': 'kg', 'resource_type': 'events.rule', 'anonymous_label': 'Resource 1', 'evidence_chunk_ids': ['aws-chunk-0'], 'note': 'arn:aws:events:region:000000000000:rule/secret'}}
        self.assertFalse(validate_graph([n], [], set(), {'aws-chunk-0'})['valid'])

    def test_validator_rejects_aws_node_without_evidence(self):
        n = {'id': 'aws:opaque', 'labels': ['AWSResource'], 'properties': {'dataset_id': 'kg', 'resource_type': 'events.rule'}}
        self.assertFalse(validate_graph([n], [], set(), set())['valid'])

    def test_evidence_ids_include_aws_chunks(self):
        self.assertIn('aws-chunk-0', builder.load_evidence_ids(self.paths))


    def test_loader_accepts_aws_nodes_and_related_to(self):
        q, _ = loader.build_node_cypher([{'id': 'aws:opaque', 'labels': ['AWSResource'], 'properties': {'dataset_id': 'kg'}}])
        self.assertIn('SET n:AWSResource', q)
        loader.build_relationship_cypher([{'edge_id': 'e', 'source_id': 'a', 'target_id': 'b', 'type': 'RELATED_TO', 'properties': {'dataset_id': 'kg'}}])
        session = MagicMock()
        loader.apply_node_labels(session, [{'id': 'aws:opaque', 'labels': ['AWSResource']}])
        self.assertIn('AWSResource', session.run.call_args[0][0])

    def test_loader_rejects_mixed_scope_before_connecting(self):
        with self.assertRaisesRegex(ValueError, 'graph_dataset_scope_invalid'):
            loader.load_graph('unused', 'unused', 'unused', 'unused', [{'id': 'a', 'labels': ['Case'], 'properties': {'dataset_id': 'one'}}, {'id': 'b', 'labels': ['Case'], 'properties': {'dataset_id': 'two'}}], [])

    def test_loader_uses_explicit_validated_scope_for_readback(self):
        driver = MagicMock()
        session = driver.__enter__.return_value.session.return_value.__enter__.return_value
        session.run.return_value.single.return_value = {'n': 1}
        import neo4j
        with patch.object(neo4j.GraphDatabase, 'driver', return_value=driver):
            result = loader.load_graph('unused', 'unused', 'unused', 'unused', [{'id': 'a', 'labels': ['Case'], 'properties': {'dataset_id': 'kg'}}], [])
        self.assertEqual(result['node_count'], 1)
        readbacks = [c for c in session.run.call_args_list if 'RETURN count' in c.args[0] and 'dataset_id: $id' in c.args[0]]
        self.assertEqual([c.kwargs['id'] for c in readbacks], ['kg', 'kg'])
