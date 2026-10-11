import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import merge_uses as m


class MergeTests(unittest.TestCase):
    def test_non_clique_is_all_review(self):
        j=[{'pair':['a','b'],'decision':'same'},
           {'pair':['b','c'],'decision':'same'},
           {'pair':['a','c'],'decision':'unsure'}]
        merges,reviews=m.components(['a','b','c'],j)
        self.assertEqual(merges,[])
        self.assertEqual(reviews[0]['use_ids'],['a','b','c'])

    def test_clique_and_isolated_node(self):
        merges,reviews=m.components(['a','b','c'],[
            {'pair':['a','b'],'decision':'same'},
            {'pair':['a','c'],'decision':'different'},
            {'pair':['b','c'],'decision':'different'}])
        self.assertEqual(merges[0][0],['a','b'])
        self.assertEqual(reviews,[])

    def test_null_rule_needs_same_chunk_and_same_text(self):
        a={'evidence':[{'chunk_id':'c','evidence':'a\n b'}]}
        self.assertEqual(m.null_rule(a,{'evidence':[{'chunk_id':'c','evidence':'a b'}]})['decision'],'same')
        self.assertEqual(m.null_rule(a,{'evidence':[{'chunk_id':'other','evidence':'a b'}]})['decision'],'different')
        self.assertEqual(m.null_rule(a,{'evidence':[{'chunk_id':'c','evidence':'a c'}]})['decision'],'different')

    def fixture(self):
        entities=[{'entity_id':id_,'type':'TechnologyUse','label':id_,
                   'props':{'purpose':purpose,'status':'implemented'}}
                  for id_,purpose in [('a','count cache'),('b','applicant cache')]]
        edges=[]
        for id_ in ('a','b'):
            for pred,obj in [('partOf','p'),('usesTechnology','t'),('hasPurpose',entities[0 if id_=='a' else 1]['props']['purpose'])]:
                edges.append({'id':len(edges)+1,'subject':id_,'predicate':pred,'object':obj,'chunk_id':'c','evidence':'evidence '+id_})
        edges.append({'id':7,'subject':'external','predicate':'replaces','object':'b','chunk_id':'d','evidence':'replacement'})
        state={'entities':entities,'edges':edges}
        plan={'merges':[{'canonical_use_id':'a','merged_use_ids':['b'],'purpose':'count cache',
                        'pair_judgments':[{'pair':['a','b'],'decision':'same'}]}]}
        return state,plan

    def test_remap_inbound_outbound_and_keep_purpose_edges_and_collisions(self):
        state,plan=self.fixture()
        before=copy.deepcopy(state)
        result,collisions=m.transformed(state,plan,'merge-v1-test')
        self.assertEqual(state,before)
        self.assertEqual(len(result['entities']),1)
        self.assertEqual(len(collisions),2)
        self.assertEqual([e['object'] for e in result['edges'] if e['predicate']=='replaces'],['a'])
        self.assertEqual(len([e for e in result['edges'] if e['predicate']=='hasPurpose']),2)
        self.assertEqual(result['entities'][0]['props']['original_purposes'],['count cache','applicant cache'])

    def test_different_status_rejected(self):
        state,plan=self.fixture()
        state['entities'][1]['props']['status']='proposed'
        with self.assertRaises(ValueError): m.transformed(state,plan,'run')

    def test_new_purpose_rejected(self):
        state,plan=self.fixture()
        plan['merges'][0]['purpose']='invented'
        with self.assertRaises(ValueError): m.transformed(state,plan,'run')

    def test_x03_guard(self):
        with self.assertRaises(ValueError): m.verify({'entities':[],'edges':[]})

    def test_human_override_null_and_drop_exact_edge(self):
        state,plan=self.fixture()
        state['entities'][1]['props']['purpose']=None
        merge=plan['merges'][0]
        merge.update(decided_by='human',reason='동일 기능의 읽기/쓰기 경로',pair_judgments=[])
        edge=state['edges'][0]
        plan['dropped_edges']=[dict(edge,edge_id=edge['id'],reason='제목 근거 제거')]
        result,_=m.transformed(state,plan,'run')
        self.assertNotIn(edge['id'],[e['id'] for e in result['edges']])
        state['entities'][1]['props']['status']='proposed'
        with self.assertRaises(ValueError): m.transformed(state,plan,'run')

    def test_alias_retargets_technology_only(self):
        state,plan=self.fixture()
        state['entities'] += [{'entity_id':id_,'type':'Technology','label':id_,'props':{}} for id_ in ('t','alias')]
        state['edges'][1]['object']='alias'
        plan['merges']=[]
        plan['technology_aliases']=[{'from':'alias','to':'t'}]
        result,_=m.transformed(state,plan,'run')
        self.assertNotIn('alias',[e['entity_id'] for e in result['entities']])
        self.assertEqual(result['edges'][1]['object'],'t')


if __name__=='__main__': unittest.main()
