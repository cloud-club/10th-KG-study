import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import agent
import graph_retriever as g
from run_w6_compare import majority


class GraphTests(unittest.TestCase):
    def fixture(self):
        nodes=[{'entity_id':i,'type':t,'label':i,'props':{'status':'implemented','purpose':'캐시'}}
               for i,t in [('u1','TechnologyUse'),('u2','TechnologyUse'),('t','Technology'),('p1','Project'),('p2','Project')]]
        edges=[{'id':n,'subject':s,'predicate':p,'object':o,'chunk_id':c,'evidence':'원문'}
               for n,(s,p,o,c) in enumerate([('u1','usesTechnology','t','c1'),('u1','partOf','p1','c1'),('u2','usesTechnology','t','c2'),('u2','partOf','p2','c2')])]
        return {'entities':nodes,'edges':edges}

    def test_no_seed_exact_context(self):
        chunks=[{'id':'other','text':'원문','title':'title'}]
        a,m,_=agent.assemble_context(chunks)
        b,n,trace=g.assemble_v2(chunks,self.fixture(),{})
        self.assertEqual((a,m),(b,n))
        self.assertTrue(trace['fallback_v1'])

    def test_two_hop_and_recover_no_duplicates(self):
        chunks=[{'id':'c1','text':'원문'}]
        context,mapping,trace=g.assemble_v2(chunks,self.fixture(),{'c2':{'id':'c2','text':'두번째 원문'}})
        self.assertIn('u2',trace['expanded_nodes'])
        self.assertEqual(trace['included_recovered_chunks'],['c2'])
        self.assertEqual(len(mapping),2)
        self.assertLessEqual(len(context),8000)
        # 생성한 그래프 문장은 원문 citation으로 허용하지 않는다.
        self.assertFalse(agent.verify_citations({'citations':[{'source':2,'snippet':'p2은 t를'}]},mapping)[0]['valid'])

    def test_whole_recovery_chunk_dropped(self):
        _,_,trace=g.assemble_v2([{'id':'c1','text':'원문'}],self.fixture(),{'c2':{'id':'c2','text':'x'*2300}})
        self.assertEqual(trace['included_recovered_chunks'],[])
        self.assertEqual(trace['budget_dropped_chunks'],['c2'])

    def test_hub_not_expanded(self):
        state=self.fixture()
        for i in range(21):
            state['entities'].append({'entity_id':f'new{i}','type':'TechnologyUse','label':'n','props':{}})
            state['edges'].append({'id':i+20,'subject':f'new{i}','predicate':'usesTechnology','object':'t','chunk_id':'other','evidence':'원문'})
        result=g.expand(state,{'c1'})
        self.assertIn('t',result['skipped_high_degree'])
        self.assertNotIn('u2',result['expanded_nodes'])

    def test_majority(self):
        self.assertEqual(majority(['wrong','correct','wrong']),'wrong')
        self.assertEqual(majority(['wrong','correct','partial']),'partial')

    def test_default_and_explicit_id_order_identical(self):
        chunks=[{'id':'c1','text':'원문'}]
        corpus={'c2':{'id':'c2','text':'추가 원문'}}
        self.assertEqual(g.assemble_v2(chunks,self.fixture(),corpus),
                         g.assemble_v2(chunks,self.fixture(),corpus,recovery_order=['c2']))

    def test_rerank_cannot_change_candidate_set(self):
        with self.assertRaises(ValueError):
            g.assemble_v2([{'id':'c1','text':'원문'}],self.fixture(),{},recovery_order=['gold-injected'])

    def test_order_is_only_budget_selection_change(self):
        state=self.fixture()
        state['edges'].append(dict(state['edges'][2],id=20,chunk_id='c3'))
        chunks=[{'id':'c1','text':'원문'}]
        corpus={id_:{'id':id_,'text':'x'*1500} for id_ in ('c2','c3')}
        _,_,old=g.assemble_v2(chunks,state,corpus)
        _,_,new=g.assemble_v2(chunks,state,corpus,recovery_order=['c3','c2'])
        self.assertEqual(old['included_recovered_chunks'],['c2'])
        self.assertEqual(new['included_recovered_chunks'],['c3'])
        self.assertEqual(old['seed_nodes'],new['seed_nodes'])
        self.assertEqual(old['expanded_nodes'],new['expanded_nodes'])


if __name__ == '__main__': unittest.main()
