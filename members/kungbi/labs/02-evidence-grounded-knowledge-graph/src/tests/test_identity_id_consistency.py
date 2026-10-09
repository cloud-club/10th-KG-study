"""All literals and source records in these public tests are synthetic."""
import unittest

from graph.build_graph import make_identity_id as builder_id
from graph.validate_graph import make_identity_id as approval_id, materialize_identity_graph


class IdentityIdConsistencyTests(unittest.TestCase):
    def test_builder_and_approval_share_identifier_function(self):
        self.assertIs(builder_id, approval_id)
        for source in ('slack', 'github'):
            self.assertEqual(builder_id(source, 'test-account'), approval_id(source, 'test-account'))

    def test_approved_links_use_builder_identifiers(self):
        nodes, edges = materialize_identity_graph([{
            'person_id': 'person:test', 'slack_user_id': 'test-slack',
            'github_account_id': 'test-github'
        }], 'test-dataset')
        expected = {builder_id('slack', 'test-slack'), builder_id('github', 'test-github')}
        self.assertEqual({e['source_id'] for e in edges}, expected)
        self.assertTrue(all(e['target_id'] == 'person:test' for e in edges))


if __name__ == '__main__':
    unittest.main()
