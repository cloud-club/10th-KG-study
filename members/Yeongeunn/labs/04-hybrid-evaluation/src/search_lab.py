"""BM25 / local E5 / RRF on one frozen Notion snapshot. Run at repo root."""
import argparse, hashlib, json, os, re, sys, time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path.cwd()
OUT=ROOT/'data/Yeongeunn/evaluation'
CORPUS=ROOT/'data/Yeongeunn/processed/notion-chunks.jsonl'
INDEX='yeongeunn-notion-eval-v1'
MODEL='intfloat/multilingual-e5-small'
REVISION='614241f622f53c4eeff9890bdc4f31cfecc418b3'
TABLE='yeongeunn_search_eval.chunks'

def dump(name,obj):
    OUT.mkdir(parents=True,exist_ok=True)
    p=OUT/name; tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)); tmp.replace(p)

def settings():
    s={}
    if (ROOT/'.env').exists():
        for line in (ROOT/'.env').read_text().splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line:continue
            k,v=line.removeprefix('export ').split('=',1)
            s[k.strip()]=v.strip().strip('\"\'')
    return dict(s,**os.environ)

def db():
    import psycopg
    s=settings()
    return psycopg.connect(host='127.0.0.1',port=int(s.get('POSTGRES_PORT',5432)),user=s.get('POSTGRES_USER','kg'),password=s.get('POSTGRES_PASSWORD','kg'),dbname=s.get('POSTGRES_DB','kg'))

def es(method,path,payload=None):
    s=settings(); req=Request('http://127.0.0.1:'+s.get('ES_PORT','9200')+path,method=method,
        data=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=90) as r:return json.load(r)

def load_snapshot():
    rows=[json.loads(l) for l in CORPUS.read_text().splitlines() if l.strip()]
    groups={}; mapping={}
    for r in sorted(rows,key=lambda x:x['id']):
        gid=hashlib.sha256(re.sub(r'\s+',' ',r['content']).strip().encode()).hexdigest()
        if gid not in groups:groups[gid]=dict(r,group_id=gid)
        mapping[r['id']]=groups[gid]['id']
    return list(groups.values()),mapping

class Encoder:
    def __init__(self,revision=None):
        from sentence_transformers import SentenceTransformer
        import torch
        torch.set_num_threads(4)
        self.model=SentenceTransformer(MODEL,revision=revision,device='cpu',trust_remote_code=False)
        self.tokenizer=self.model.tokenizer
    def encode(self,texts,kind):
        import numpy as np
        # Every token is covered; long source chunks are windowed, not silently truncated.
        windows=[]; spans=[]
        for text in texts:
            ids=self.tokenizer.encode(text,add_special_tokens=False)
            start=len(windows)
            for pos in range(0,max(1,len(ids)),384):
                segment=self.tokenizer.decode(ids[pos:pos+448],skip_special_tokens=True)
                windows.append(kind+': '+segment)
                if pos+448>=len(ids):break
            spans.append((start,len(windows)))
        emb=self.model.encode(windows,batch_size=16,normalize_embeddings=True,show_progress_bar=False)
        result=np.stack([emb[a:b].mean(axis=0) for a,b in spans])
        return result/np.linalg.norm(result,axis=1,keepdims=True)

def build():
    import numpy as np
    
    rows,mapping=load_snapshot()
    qrels=json.loads((OUT/'qrels.json').read_text())
    corpus_hash=hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    if corpus_hash!=qrels['corpus_sha256']:raise ValueError('Corpus changed after labeling')
    meta_path=OUT/'embedding-meta.json'
    if meta_path.exists():
        meta=json.loads(meta_path.read_text());revision=meta['revision']
        if meta['corpus_sha256']!=corpus_hash:raise ValueError('Use another output snapshot for changed corpus')
    else:
        revision=REVISION
        meta={'model':MODEL,'revision':revision,'corpus_sha256':corpus_hash,'original_chunks':sum(1 for l in CORPUS.read_text().splitlines() if l.strip()),'unique_chunks':len(rows),'dim':384,'windows':{'tokens':448,'stride':384,'pool':'mean of normalized windows, renormalized'},'prefixes':['query: ','passage: ']}
        dump('embedding-meta.json',meta)
    encoder=Encoder(revision)
    cache=OUT/'vectors.npy'
    if cache.exists():vectors=np.load(cache)
    else:
        batches=[];start=time.perf_counter()
        for i in range(0,len(rows),64):
            batches.append(encoder.encode([r['title']+'\n'+r['content'] for r in rows[i:i+64]],'passage'))
            print('Embedded',min(i+64,len(rows)),'/',len(rows),flush=True)
        vectors=np.vstack(batches);np.save(cache,vectors)
        meta['embedding_seconds']=time.perf_counter()-start;dump('embedding-meta.json',meta)
    assert vectors.shape==(len(rows),384)
    dump('snapshot.json',{'rows':rows,'canonical_ids':mapping})
    with db() as conn:
        conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
        conn.execute('CREATE SCHEMA IF NOT EXISTS yeongeunn_search_eval')
        conn.execute(f'CREATE TABLE IF NOT EXISTS {TABLE}(id text PRIMARY KEY, title text NOT NULL, content text NOT NULL, embedding vector(384) NOT NULL)')
        # Dedicated experimental table only; one atomic frozen snapshot.
        conn.execute(f'DELETE FROM {TABLE}')
        with conn.cursor().copy(f'COPY {TABLE}(id,title,content,embedding) FROM STDIN') as cp:
            for r,v in zip(rows,vectors):cp.write_row((r['id'],r['title'],r['content'],json.dumps(v.tolist())))
    try:es('GET','/'+INDEX)
    except Exception as e:
        if getattr(e,'code',None)!=404:raise
        es('PUT','/'+INDEX,{'settings':{'number_of_shards':1,'number_of_replicas':0},'mappings':{'properties':{'record_id':{'type':'keyword'},'title':{'type':'text','analyzer':'nori'},'content':{'type':'text','analyzer':'nori'}}}})
    # Dedicated index cleared so removed source chunks cannot leak into this evaluation.
    es('POST','/'+INDEX+'/_delete_by_query?refresh=true',{'query':{'match_all':{}}})
    for i in range(0,len(rows),200):
        bulk=''.join(json.dumps({'index':{'_id':r['id']}})+'\n'+json.dumps({'record_id':r['id'],'title':r['title'],'content':r['content']},ensure_ascii=False)+'\n' for r in rows[i:i+200])
        req=Request('http://127.0.0.1:'+settings().get('ES_PORT','9200')+'/'+INDEX+'/_bulk',data=bulk.encode(),headers={'Content-Type':'application/x-ndjson'})
        with urlopen(req,timeout=90) as f:result=json.load(f)
        if result.get('errors'):raise RuntimeError('Bulk indexing failed')
    es('POST','/'+INDEX+'/_refresh')
    assert es('GET','/'+INDEX+'/_count')['count']==len(rows)
    with db() as conn:assert conn.execute(f'SELECT count(*) FROM {TABLE}').fetchone()[0]==len(rows)
    print('Snapshot ready:',len(rows),'unique chunks; model',MODEL,flush=True)

def rrf(a,b,c=60):
    scores={}
    for ranking in (a,b):
        for rank,item in enumerate(ranking,1):scores[item]=scores.get(item,0)+1/(c+rank)
    return sorted(scores,key=lambda x:(-scores[x],x))

def recall(ranking,groups,mapping,k=5):
    top=set(ranking[:k]);hit=sum(bool(top & {mapping[x] for x in g['chunk_ids']}) for g in groups)
    return hit/len(groups),hit==len(groups)

def retrieve(query,encoder,conn):
    start=time.perf_counter()
    a=[h['_id'] for h in es('POST','/'+INDEX+'/_search',{'size':30,'query':{'multi_match':{'query':query,'fields':['title','content']}},'sort':[{'_score':'desc'},{'record_id':'asc'}]})['hits']['hits']]
    bm_ms=(time.perf_counter()-start)*1000
    start=time.perf_counter();v=encoder.encode([query],'query')[0].tolist();embed_ms=(time.perf_counter()-start)*1000
    start=time.perf_counter()
    conn.execute('SET enable_indexscan=off');conn.execute('SET enable_bitmapscan=off')
    b=[r[0] for r in conn.execute(f'SELECT id FROM {TABLE} ORDER BY embedding <=> %s::vector, id LIMIT 30',(json.dumps(v),)).fetchall()]
    vec_ms=(time.perf_counter()-start)*1000
    start=time.perf_counter();h=rrf(a,b);fuse_ms=(time.perf_counter()-start)*1000
    return {'bm25':a,'vector':b,'rrf':h},{'bm25':bm_ms,'vector':embed_ms+vec_ms,'rrf':bm_ms+embed_ms+vec_ms+fuse_ms},v

def evaluate():
    meta=json.loads((OUT/'embedding-meta.json').read_text());encoder=Encoder(meta['revision'])
    snapshot=json.loads((OUT/'snapshot.json').read_text());mapping=snapshot['canonical_ids']
    gold=json.loads((OUT/'qrels.json').read_text());results=[]
    with db() as conn:
        for q in gold['questions']:
            rankings,latency,v=retrieve(q['question'],encoder,conn)
            rankings['grep']=[r['id'] for r in snapshot['rows'] if q['question'] in r['title']+'\n'+r['content']]
            metrics={m:dict(zip(['recall_at_5','all_evidence'],recall(ids,q['evidence_groups'],mapping))) for m,ids in rankings.items()}
            results.append(dict(id=q['id'],type=q['type'],rankings=rankings,metrics=metrics,latency_ms=latency,query_vector=v))
            print(q['id'],{k:round(v['recall_at_5'],3) for k,v in metrics.items()},flush=True)
    summary={m:{'mean_recall_at_5':sum(r['metrics'][m]['recall_at_5'] for r in results)/len(results),'all_evidence_questions':sum(r['metrics'][m]['all_evidence'] for r in results)} for m in ['grep','bm25','vector','rrf']}
    dump('results.json',{'qrels_sha256':hashlib.sha256((OUT/'qrels.json').read_bytes()).hexdigest(),'k':5,'c':60,'candidate_limit':30,'labeling':gold['labeling'],'summary':summary,'questions':results})
    print(json.dumps(summary,indent=2))

def ask(method,question,model):
    sys.path.insert(0,str(ROOT/'members/Yeongeunn/labs/03-notion-ingest/src'))
    from rag import config,generate,redact
    meta=json.loads((OUT/'embedding-meta.json').read_text());encoder=Encoder(meta['revision'])
    snapshot=json.loads((OUT/'snapshot.json').read_text());lookup={x['id']:x for x in snapshot['rows']}
    with db() as conn:ranks,_,_=retrieve(question,encoder,conn)
    ids=ranks[method][:5]
    evidence=[{'number':i+1,'content':redact(lookup[id]['content'])} for i,id in enumerate(ids)]
    answer,reason,usage=generate(config()['GEMINI_API_KEY'],model,redact(question),evidence)
    target='answer-'+hashlib.sha256((method+question).encode()).hexdigest()[:12]+'.json'
    dump(target,{'question':question,'method':method,'model':model,'chunk_ids':ids,'answer':answer,'finish_reason':reason,'usage':usage})
    print(answer);print('Saved local answer:',target)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','evaluate','ask']);p.add_argument('--method',choices=['bm25','vector','rrf'],default='rrf');p.add_argument('--query');p.add_argument('--model',default='gemini-3.1-flash-lite');a=p.parse_args()
    if a.action=='build':build()
    elif a.action=='evaluate':evaluate()
    else:
        if not a.query:p.error('--query required')
        ask(a.method,a.query,a.model)
