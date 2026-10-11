import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from run_v1_w6 import recall


class RecallTests(unittest.TestCase):
    def test_no_gold_is_null_even_with_candidate_groups(self):
        self.assertEqual(recall({'gold_chunks': [], 'equivalent_groups': [{'chunk_ids':['a','b']}]}, ['a']), ([], None, []))

    def test_equivalent_counts_once(self):
        q = {'gold_chunks':['a','b','c'], 'equivalent_groups':[{'chunk_ids':['a','b','alt']}]}
        hits, value, groups = recall(q, ['alt','b'])
        self.assertEqual(hits,['alt','b'])
        self.assertEqual(value,0.5)
        self.assertEqual(len(groups),1)

    def test_non_gold_candidate_group_does_not_expand_denominator(self):
        q = {'gold_chunks':['a'], 'equivalent_groups':[{'chunk_ids':['b','c']}]}
        self.assertEqual(recall(q,['b'])[1],0.0)

    def test_exact_gold(self):
        self.assertEqual(recall({'gold_chunks':['a','b']},['b','x'])[1],0.5)


if __name__ == '__main__':
    unittest.main()
