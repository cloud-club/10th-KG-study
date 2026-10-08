"""W6: exact vector cosine + BM25 + RRF, then bounded graph expansion."""
import collections, hashlib, json, math, os, re, urllib.request
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent

def request(url,body,headers=None):
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json',**(headers or {})})
    with urllib.request.urlopen(req,timeout=180) as r: return json.load(r)

def embed(text):
    return request(os.getenv('OLLAMA_URL','http://localhost:11434')+'/api/embed',{'model':os.getenv('EMBED_MODEL','qwen3-embedding:0.6b'),'input':text})['embeddings'][0]

def tokens(text): return re.findall(r'\w+',text.lower())
def cosine(a,b): return sum(x*y for x,y in zip(a,b))/(math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b)) or 1)

def search(question,k=6):
    docs=json.loads((BASE/'chunks.json').read_text()); model=os.getenv('EMBED_MODEL','qwen3-embedding:0.6b')
    fingerprint=hashlib.sha256(json.dumps([model,docs],sort_keys=True).encode()).hexdigest()
    path=BASE/'outputs'/'vector-index.json'; path.parent.mkdir(exist_ok=True)
    cache=json.loads(path.read_text()) if path.exists() else {}
    if cache.get('fingerprint')!=fingerprint:
        cache={'fingerprint':fingerprint,'vectors':[embed(d['text']) for d in docs]};path.write_text(json.dumps(cache))
    q=embed(question); vector=sorted(range(len(docs)),key=lambda i:cosine(q,cache['vectors'][i]),reverse=True)
    bags=[collections.Counter(tokens(d['text'])) for d in docs];N=len(docs);avg=sum(sum(b.values()) for b in bags)/max(N,1)
    def bm25(i):
        score=0;length=sum(bags[i].values())
        for term in set(tokens(question)):
            tf=bags[i][term];df=sum(term in b for b in bags)
            score+=math.log(1+(N-df+.5)/(df+.5))*tf*2.2/(tf+1.2*(.25+.75*length/(avg or 1)))
        return score
    keyword=sorted(range(N),key=bm25,reverse=True);scores=collections.defaultdict(float)
    for ranking in [vector,keyword]:
        for rank,i in enumerate(ranking,1): scores[i]+=1/(60+rank)
    return [docs[i] for i in sorted(scores,key=scores.get,reverse=True)[:k]]

def expand(hits):
    graph=json.loads((BASE/'graph.json').read_text());ids={d['entity_id'] for d in hits};front=set(ids)
    for _ in range(3):
        more={e['object'] for e in graph['edges'] if e['subject'] in front}|{e['subject'] for e in graph['edges'] if e['object'] in front}
        front=more-ids;ids|=front
    return {'nodes':[n for n in graph['nodes'] if n['id'] in ids], 'edges':[e for e in graph['edges'] if e['subject'] in ids and e['object'] in ids]}

def chat(messages):
    if os.getenv('LLM_API_KEY'):
        x=request(os.getenv('LLM_BASE_URL','https://api.mangoboost.io/v1').rstrip('/')+'/chat/completions',{'model':os.getenv('LLM_MODEL','zai-org/GLM-5.2'),'messages':messages,'temperature':0,'max_tokens':3000}, {'Authorization':'Bearer '+os.environ['LLM_API_KEY']})
        return x['choices'][0]['message']['content'],x.get('usage',{})
    x=request(os.getenv('OLLAMA_URL','http://localhost:11434')+'/api/chat',{'model':os.getenv('OLLAMA_MODEL','qwen2.5:7b'),'messages':messages,'stream':False,'options':{'temperature':0}})
    return x['message']['content'],{'prompt_tokens':x.get('prompt_eval_count',0),'completion_tokens':x.get('eval_count',0)}
