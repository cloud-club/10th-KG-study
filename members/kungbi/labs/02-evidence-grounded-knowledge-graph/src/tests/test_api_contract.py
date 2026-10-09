"""All literals and source records in these public tests are synthetic."""
"""Exact endpoint evidence contracts; no runtime client or fuzzy route matching."""
import copy
import json
import unittest
from pathlib import Path

from graph import build_graph as builder
from graph import loader
from graph.validate_graph import validate_graph


class EndpointProofTests(unittest.TestCase):
    def proof(self):
        # Independently invented classroom example; no application source excerpt.
        # Minimal strings exercise parser syntax, not a real product endpoint.
        return dict(method='POST', prefix='classroom', suffix='exercises',
                    path='/classroom/exercises',
                    backend_patch="+ @Post('exercises')\n+ createExercise() { return { synthetic: true }; }",
                    backend_source="@Controller('classroom')\nclass SyntheticClassroom {\n @Post('exercises')\n createExercise() { return { synthetic: true }; }\n}",
                    openapi_patch='+ "/classroom/exercises": {\n+ "post": {',
                    caller_patches=["+ client.post('/classroom/exercises', { synthetic: true });"],
                    caller_source="const client = axios.create({ baseURL: API_URL });\nclient.post('/classroom/exercises', { synthetic: true });")

    def check(self, proof):
        self.assertTrue(hasattr(builder, 'validate_endpoint_proof'), 'endpoint proof validator missing')
        return builder.validate_endpoint_proof(**proof)

    def test_exact_literal_proof_resolves_controller_relative_route(self):
        self.assertEqual(self.check(self.proof()), '/classroom/exercises')

    def test_wrong_controller_prefix_rejected(self):
        p = self.proof(); p['backend_source'] = p['backend_source'].replace("'classroom'", "'other'")
        with self.assertRaisesRegex(ValueError, 'api_'): self.check(p)

    def test_removed_method_not_authored_implementation(self):
        p = self.proof(); p['backend_patch'] = p['backend_patch'].replace('+', '-')
        with self.assertRaisesRegex(ValueError, 'api_'): self.check(p)

    def test_removed_caller_not_authored_call(self):
        p = self.proof(); p['caller_patches'] = [p['caller_patches'][0].replace('+', '-')]
        with self.assertRaisesRegex(ValueError, 'api_'): self.check(p)

    def test_wrong_method_rejected(self):
        p = self.proof(); p['caller_patches'] = [p['caller_patches'][0].replace('.post', '.delete')]
        with self.assertRaisesRegex(ValueError, 'api_'): self.check(p)

    def test_name_similarity_not_call_evidence(self):
        p = self.proof(); p['caller_patches'] = ['+ classroomApi.createExercises();']
        with self.assertRaisesRegex(ValueError, 'api_'): self.check(p)

    def test_openapi_other_path_rejected(self):
        p = self.proof(); p['openapi_patch'] = p['openapi_patch'].replace('classroom', 'other')
        with self.assertRaisesRegex(ValueError, 'api_'): self.check(p)

    def test_parameter_normalization_not_inferred(self):
        p = self.proof(); p['suffix'] = ':id'; p['path'] = '/classroom/42'
        with self.assertRaisesRegex(ValueError, 'api_'): self.check(p)

    def test_snapshot_caller_drift_rejected(self):
        p = self.proof(); p['caller_source'] = p['caller_source'].replace('.post', '.delete')
        with self.assertRaisesRegex(ValueError, 'api_'): self.check(p)

    def test_commented_controller_is_not_static_route_evidence(self):
        p = self.proof(); p['backend_source'] = p['backend_source'].replace('@Controller', '// @Controller')
        with self.assertRaisesRegex(ValueError, 'api_'): self.check(p)

    def test_commented_call_is_not_authored_call(self):
        p = self.proof(); p['caller_patches'] = ['+ // ' + p['caller_source'].split('\n')[1]]
        with self.assertRaisesRegex(ValueError, 'api_'): self.check(p)

    def test_block_commented_call_is_not_authored_call(self):
        p = self.proof(); p['caller_patches'] = ['+ /* ' + p['caller_source'].split('\n')[1] + ' */']
        with self.assertRaisesRegex(ValueError, 'api_'): self.check(p)


class EndpointGraphTests(unittest.TestCase):

    def test_loader_accepts_endpoint_and_both_semantic_edges(self):
        n = dict(id='api:test', labels=['APIContract'], properties={'dataset_id': 'test'})
        self.assertIn('APIContract', loader.build_node_cypher([n])[0])
        for rel in ('IMPLEMENTS', 'CALLS_WITH'):
            loader.build_relationship_cypher([dict(edge_id='e', source_id='s', target_id='t', type=rel, properties={})])

    def test_endpoint_missing_scope_and_evidence_rejected(self):
        node = dict(id='api:test', labels=['APIContract'], properties={'dataset_id':'test'})
        errors = validate_graph([node], [], set(), set())['errors']
        self.assertIn('api_node_contract_invalid', errors)
        self.assertIn('api_node_evidence_missing_or_unknown', errors)

    def test_endpoint_call_requires_codefile_source_and_evidence(self):
        nodes = [dict(id='pr', labels=['PullRequest'], properties={}),
                 dict(id='api', labels=['APIContract'], properties={})]
        edge = dict(edge_id='e', source_id='pr', type='CALLS_WITH', target_id='api', properties={})
        errors = validate_graph(nodes, [edge], {'CALLS_WITH'}, set())['errors']
        self.assertIn('api_edge_endpoints_invalid', errors)
        self.assertIn('api_edge_evidence_missing', errors)


    def test_git_evidence_ids_collected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'chunks.jsonl'; p.write_text('{"retrieval_chunk_id":"git-proof"}\n')
            self.assertEqual(builder.load_evidence_ids({'git_chunks':p}), {'git-proof'})
