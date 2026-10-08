"""Run the same question with retrieved chunks alone and with graph context."""
import argparse,json,time
from retriever import BASE,chat,search,expand
p=argparse.ArgumentParser();p.add_argument('question');args=p.parse_args()
hits=search(args.question);results={}
for mode in ['v1','v2']:
    context={'chunks':hits}
    if mode=='v2':context['graph']=expand(hits)
    start=time.perf_counter()
    answer,usage=chat([{'role':'system','content':'Answer in Korean using DATA only. Cite chunk IDs or graph entity IDs. TestCase is definition, CaseRun is one case execution, TestRun groups case executions. Reference commits do not prove resolution. Do not treat top-k or a bounded subgraph as all records. If counts need complete scope, state insufficient evidence.'},{'role':'user','content':json.dumps({'question':args.question,'data':context},ensure_ascii=False)}])
    results[mode]={'answer':answer,'usage':usage,'answer_seconds':round(time.perf_counter()-start,3),'context':context}
(BASE/'outputs').mkdir(exist_ok=True);(BASE/'outputs'/'comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print(json.dumps(results,ensure_ascii=False,indent=2))
