"""HNSW neighbor overlap vs exact search, distinct from task evidence Recall@5."""
import json
from search_lab import db,OUT,TABLE
r=json.loads((OUT/'results.json').read_text());scores=[]
with db() as c:
 c.execute(f'CREATE INDEX IF NOT EXISTS yeongeunn_eval_hnsw ON {TABLE} USING hnsw(embedding vector_cosine_ops) WITH(m=16,ef_construction=64)')
 c.execute('ANALYZE '+TABLE)
 for q in r['questions']:
  c.execute('SET enable_seqscan=off');c.execute('SET enable_indexscan=on');c.execute('SET hnsw.ef_search=100')
  v=json.dumps(q['query_vector'])
  sql=f'SELECT id FROM {TABLE} ORDER BY embedding <=> %s::vector LIMIT 5'
  plan='\n'.join(x[0] for x in c.execute('EXPLAIN '+sql,(v,)))
  assert 'yeongeunn_eval_hnsw' in plan
  approx=[x[0] for x in c.execute(sql,(v,))]
  exact=q['rankings']['vector'][:5]
  scores.append({'id':q['id'],'top5_overlap':len(set(approx)&set(exact))/5})
obj={'ef_search':100,'m':16,'ef_construction':64,'mean_exact_neighbor_overlap_at_5':sum(x['top5_overlap'] for x in scores)/len(scores),'questions':scores,'query_plan':plan}
(OUT/'ann-check.json').write_text(json.dumps(obj,indent=2));print(json.dumps(obj,indent=2))
