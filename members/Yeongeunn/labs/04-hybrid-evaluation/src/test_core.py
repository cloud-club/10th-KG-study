"""Regression checks; no model download, DB write or Gemini call."""
import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from search_lab import rrf,recall
spec=importlib.util.spec_from_file_location('triples',Path.cwd()/'members/Yeongeunn/labs/05-triple-extraction/src/triples.py')
triples=importlib.util.module_from_spec(spec);spec.loader.exec_module(triples)

class CoreTests(unittest.TestCase):
 def test_rrf_complements_and_single_list(self):
  self.assertEqual(rrf(['A','B','C'],['B','D','A']),['B','A','D','C'])
  self.assertEqual(rrf([],['A']),['A'])
 def test_one_strong_hit_can_drop_after_fusion(self):
  # c=60 can promote documents present in both lists above a sole rank-1 hit.
  out=rrf(['gold','a','b','c','d','e'],['a','b','c','d','e'])
  self.assertEqual(out.index('gold'),5)
 def test_duplicate_evidence_not_double_counted(self):
  self.assertEqual(recall(['a','a'],[{'chunk_ids':['a','copy']},{'chunk_ids':['b']}],{'a':'a','copy':'a','b':'b'}),(0.5,False))
 def test_one_chunk_can_support_two_required_facts(self):
  self.assertEqual(recall(['a'],[{'chunk_ids':['a']},{'chunk_ids':['a']}],{'a':'a'}),(1.0,True))
 def test_unsupported_quote_and_reversed_type_rejected(self):
  row={'subject':'S','subject_class':'Service','predicate':'exposesAPI','object':'A','object_class':'API','chunk_id':'c','quote':'S provides A.','condition':''}
  chunks=[{'id':'c','content':'S provides A.'}]
  self.assertEqual(len(triples.validate([row],chunks)[0]),1)
  for field,val in [('quote','invented'),('subject_class','API'),('predicate','invented'),('chunk_id','missing')]:
   with self.subTest(field=field):self.assertEqual(len(triples.validate([dict(row,**{field:val})],chunks)[1]),1)
 def test_conditional_block_requires_condition(self):
  row={'subject':'P','subject_class':'Policy','predicate':'blocksOperation','object':'O','object_class':'Operation','chunk_id':'c','quote':'blocked if pending','condition':''}
  self.assertEqual(len(triples.validate([row],[{'id':'c','content':row['quote']}])[1]),1)
if __name__=='__main__':unittest.main()
