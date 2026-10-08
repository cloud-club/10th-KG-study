"""Generate pending triples using Ollama; never auto-approve model output."""
import json, os, urllib.request
from pipeline import BASE, RELATIONS
sample=json.loads((BASE/'sample.json').read_text())
item={'type':'object','additionalProperties':False,'required':['subject','predicate','object','document_id','evidence'], 'properties':{
 'subject':{'type':'string','enum':[n['id'] for n in sample['nodes']]},
 'object':{'type':'string','enum':[n['id'] for n in sample['nodes']]},
 'predicate':{'type':'string','enum':list(RELATIONS)},
 'document_id':{'type':'string','enum':list(sample['documents'])},'evidence':{'type':'string'}}}
schema={'type':'object','additionalProperties':False,'required':['triples'],'properties':{'triples':{'type':'array','items':item}}}
body={'model':os.getenv('OLLAMA_MODEL','qwen2.5:7b'),'stream':False,'format':schema,'options':{'temperature':0},'messages':[
 {'role':'system','content':'Extract only explicit facts from DATA. Return JSON. Evidence must be an exact substring of its document. relatedCommit is a reference, never proof of completion. Example: Task A links issue B => A hasIssue B, never B hasIssue A. Allowed schema: '+json.dumps(RELATIONS)},
 {'role':'user','content':json.dumps({'nodes':sample['nodes'],'documents':sample['documents']},ensure_ascii=False)}]}
request=urllib.request.Request(os.getenv('OLLAMA_URL','http://localhost:11434')+'/api/chat',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=180) as r: result=json.load(r)
candidates=json.loads(result['message']['content'])
from jsonschema import validate
validate(candidates,schema)
for t in candidates['triples']:
 text=sample['documents'][t['document_id']];start=text.find(t['evidence'])
 assert t['evidence'] and start>=0,'Unsupported quote'
 t.update(start=start,end=start+len(t['evidence']),approved=False)
(BASE/'outputs').mkdir(exist_ok=True)
(BASE/'outputs'/'pending-triples.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2))
print('Candidates saved for semantic review; not loaded into databases.')
