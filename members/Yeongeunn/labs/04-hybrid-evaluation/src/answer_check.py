"""Diagnostic answer comparison using saved search rankings (new Gemini calls)."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path.cwd(); OUT=ROOT/'data/Yeongeunn/evaluation'
sys.path.insert(0,str(ROOT/'members/Yeongeunn/labs/03-notion-ingest/src'))
from rag import config,generate,redact

def main():
    result=json.loads((OUT/'results.json').read_text()); gold=json.loads((OUT/'qrels.json').read_text())
    snap=json.loads((OUT/'snapshot.json').read_text());lookup={c['id']:c for c in snap['rows']}
    questions={q['id']:q for q in gold['questions']}; model='gemini-3.1-flash-lite'; key=config()['GEMINI_API_KEY']
    folder=OUT/'answers';folder.mkdir(exist_ok=True)
    jobs=[(r['id'],m,r['rankings'][m][:5]) for r in result['questions'] if r['id'] in ['q01','q05','q09','q10'] for m in ['bm25','vector','rrf']]
    q=questions['q02'];ids=sorted({snap['canonical_ids'][c] for g in q['evidence_groups'] for c in g['chunk_ids']})
    jobs.append(('q02','oracle',ids))
    for qid,method,ids in jobs:
        p=folder/(qid+'-'+method+'.json')
        if p.exists():print('Cached',qid,method,flush=True);continue
        ev=[{'number':i+1,'content':redact(lookup[id]['content'])} for i,id in enumerate(ids)]
        answer,reason,usage=generate(key,model,questions[qid]['question'],ev)
        obj={'id':qid,'method':method,'question':questions[qid]['question'],'model':model,'chunk_ids':ids,'answer':answer,'finish_reason':reason,'usage':usage,'retrieval_results_sha256':hashlib.sha256((OUT/'results.json').read_bytes()).hexdigest()}
        p.write_text(json.dumps(obj,ensure_ascii=False,indent=2));print('Generated',qid,method,reason,flush=True)
if __name__=='__main__':main()
