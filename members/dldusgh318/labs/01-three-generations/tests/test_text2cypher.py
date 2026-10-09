import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from text2cypher import guard, user_message, FEW_SHOTS


class SafetyTests(unittest.TestCase):
    def test_read_examples(self):
        for shot in FEW_SHOTS: self.assertTrue(guard(shot['cypher']))

    def test_write_and_external_calls_rejected(self):
        for q in ['MATCH(n) DELETE n','CALL db.labels()','LOAD CSV FROM "url" AS r RETURN r',
                  'MATCH(n) RETURN n; MATCH(m) SET m.x=1','MATCH(n) /* trick */ RETURN n']:
            with self.assertRaises(ValueError): guard(q)

    def test_literals_not_mistaken_for_write(self):
        self.assertTrue(guard("MATCH(n) WHERE n.label='set' RETURN n.label;"))

    def test_zero_result_includes_query_and_scope(self):
        q='MATCH(n:TechnologyUse) WHERE n.status="not_implemented" RETURN n.id'
        message=user_message(q,[])
        self.assertIn('20개 청크 표본',message)
        self.assertIn('이 조건으로 찾았는데 없다',message)
        self.assertIn(q,message)


if __name__=='__main__': unittest.main()
