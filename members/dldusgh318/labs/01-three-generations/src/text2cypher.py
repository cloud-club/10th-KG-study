"""표본 Neo4j의 실제 스키마로 Text2Cypher 7문항 × 3회 실험."""
import hashlib
import json
import os
import re
import time
from urllib.request import Request, urlopen

from neo4j import GraphDatabase, READ_ACCESS, unit_of_work
import yaml

from common import LAB
from agent import DEFAULT_MODEL, API_URL
from load_neo4j import DEFAULT_NEO4J_URI, DEFAULT_NEO4J_PASSWORD

FEW_SHOTS = [
    {'question':'SeCause가 쓴 기술은?', 'cypher':"MATCH (u:TechnologyUse)-[:PART_OF]->(p:Project {id:'kg:secause'}), (u)-[:USES_TECHNOLOGY]->(t:Technology) RETURN DISTINCT t.id AS technology_id, t.label AS technology ORDER BY technology_id"},
    {'question':'Docker를 쓴 프로젝트는?', 'cypher':"MATCH (t:Technology {id:'kg:tech-docker'})<-[:USES_TECHNOLOGY]-(u:TechnologyUse)-[:PART_OF]->(p:Project) RETURN DISTINCT p.id AS project_id, p.label AS project ORDER BY project_id"},
    {'question':'SeCause에서 구현한 기술 수는?', 'cypher':"MATCH (u:TechnologyUse)-[:PART_OF]->(p:Project {id:'kg:secause'}), (u)-[:USES_TECHNOLOGY]->(t:Technology) WHERE u.status='implemented' RETURN count(DISTINCT t.id) AS technology_count"},
]
OUTPUT_SCHEMA = {'type':'object','properties':{'cypher':{'type':'string'}},
                 'required':['cypher'],'additionalProperties':False}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def inspect(session):
    nodes=session.run('MATCH(n) RETURN labels(n) AS labels, properties(n) AS props ORDER BY n.id').data()
    rels=session.run('MATCH(a)-[r]->(b) RETURN a.id AS subject,type(r) AS type,b.id AS object, properties(r) AS props ORDER BY subject,type,object,r.edge_key').data()
    schema={}
    for row in nodes:
        for label in row['labels']:
            group=schema.setdefault(label,{'count':0,'properties':set()})
            group['count']+=1; group['properties'].update(row['props'])
    for group in schema.values(): group['properties']=sorted(group['properties'])
    directions=sorted({(tuple(n['labels']),r['type'],tuple(m['labels'])) for r in rels
        for n in nodes if n['props']['id']==r['subject']
        for m in nodes if m['props']['id']==r['object']})
    projects=[n['props'] for n in nodes if 'Project' in n['labels']]
    statuses={}
    for n in nodes:
        if 'TechnologyUse' in n['labels']:
            status=n['props'].get('status'); key=status or 'NULL'
            statuses[key]=statuses.get(key,0)+1
    return {'schema':schema,'relationships':directions,'projects':projects,'status_counts':statuses,
            'snapshot_hash':digest({'nodes':nodes,'relationships':rels}),
            'nodes':nodes,'edges':rels}


def prompt(actual):
    return '''질문을 Neo4j 5 Cypher 읽기 쿼리 1개로 변환하라. JSON의 cypher만 반환한다.
그래프는 전체 문서가 아니라 20개 청크 표본이다. 정답을 추측하거나 데이터를 변경하지 않는다.
주요 스키마:
Project {id,label}; Technology {id,label}; TechnologyUse {id,purpose,status}
(TechnologyUse)-[:PART_OF]->(Project)
(TechnologyUse)-[:USES_TECHNOLOGY]->(Technology)
purpose/status는 TechnologyUse 속성이지 관계나 Technology 속성이 아니다. NULL/미기재일 수 있다.
status 허용값: implemented / proposed / not_implemented. 상태는 해당 사용례의 상태다.
기술 id 예시: kg:tech-redis, kg:tech-docker. label/id는 소문자이며 프로젝트 id는 kg:secause, kg:teamficial, kg:jikhaeng이다.
Neo4j는 대소문자를 구분한다. 없던 라벨·속성·관계·값을 만들지 않는다.
한 사실에 여러 청크 근거가 있어 관계가 중복될 수 있다. 기술/프로젝트/사용례 개수를 셀 때 적절한 DISTINCT 식별자를 사용한다.
질문에 명시된 상태 조건만 사용하며 NULL을 implemented나 proposed로 추정하지 않는다.
용도와 상태를 묻는 질문이면 식별 기술, 프로젝트, 해당 사용례 purpose/status를 반환하라.
CALL, APOC, LOAD CSV, USE, 쓰기 명령은 금지한다. 코드 펜스와 설명 없이 쿼리만 JSON에 넣는다.
실제 DB 스키마 및 값 예시(정답 목록이 아님):
'''+json.dumps({k:actual[k] for k in ('schema','relationships','projects','status_counts')},ensure_ascii=False)+'''
few-shot (논리적 1-hop은 TechnologyUse 중간 노드 때문에 실제로는 관계 2개):
'''+json.dumps(FEW_SHOTS,ensure_ascii=False)


def guard(cypher):
    query=cypher.strip()
    if query.endswith(';'): query=query[:-1].rstrip()
    # 문자열 리터럴은 검사에서 제외. 백틱 식별자 안의 위험 키워드는 보수적으로 차단.
    lexical=re.sub(r"'(?:\\.|''|[^'\\])*'|\"(?:\\.|\"\"|[^\"\\])*\"", "''", query)
    if ';' in lexical or '//' in lexical or '/*' in lexical:
        raise ValueError('단일 읽기 쿼리만 허용; 주석/다중 문장 차단')
    if not re.match(r'(?is)^(MATCH|OPTIONAL\s+MATCH|WITH)\b',lexical):
        raise ValueError('MATCH/OPTIONAL MATCH/WITH 읽기 쿼리만 허용')
    if re.search(r'\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|CALL|LOAD|FOREACH|USE|INSERT|ALTER|GRANT|DENY|REVOKE)\b',lexical,re.I):
        raise ValueError('쓰기/프로시저/외부 I/O 키워드 차단')
    return query


def execute(session, cypher):
    query=guard(cypher)
    @unit_of_work(timeout=10)
    def read(tx):
        summary=tx.run('EXPLAIN '+query).consume()
        if summary.query_type!='r':
            raise ValueError(f'읽기 실행계획 아님: {summary.query_type}')
        result=tx.run(query)
        rows=[r.data() for r in result.fetch(201)]
        result.consume()
        if len(rows)>200: raise ValueError('결과 200행 초과: 의미 채점 전에 쿼리 검토 필요')
        return rows,summary.notifications or []
    return session.execute_read(read)


def generate(question, instructions, model):
    body={'model':model,'store':False,'reasoning':{'effort':'low'},'instructions':instructions,
          'input':question,'text':{'verbosity':'low','format':{'type':'json_schema','name':'cypher_query',
                  'strict':True,'schema':OUTPUT_SCHEMA}}}
    request=Request(API_URL,data=json.dumps(body).encode(),method='POST',
                    headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY'],'Content-Type':'application/json'})
    with urlopen(request,timeout=120) as response: raw=json.load(response)
    if raw.get('status')!='completed': raise ValueError('LLM 응답 미완료')
    text=raw.get('output_text') or ''.join(p.get('text','') for item in raw.get('output',[])
                                         for p in item.get('content',[]) if p.get('type')=='output_text')
    return json.loads(text)['cypher'],raw.get('usage'),raw.get('model'),raw.get('temperature')


def user_message(query, rows, error=None):
    scope='이 결과는 전체 문서가 아니라 20개 청크 표본 그래프 기준입니다.'
    if error: return scope+' 쿼리 실행에 실패했습니다.\n'+query+'\n'+str(error)
    if not rows: return scope+' 이 조건으로 찾았는데 없다. 전체 데이터에 없다는 뜻은 아닙니다.\n'+query
    return scope+'\n'+json.dumps(rows,ensure_ascii=False)


def main():
    env=LAB/'.env'
    if env.exists():
        for line in env.read_text().splitlines():
            name,sep,value=line.strip().partition('=')
            if sep and name in ('OPENAI_API_KEY','OPENAI_MODEL'): os.environ.setdefault(name,value.strip().strip('\"\''))
    if not os.getenv('OPENAI_API_KEY'): raise ValueError('OPENAI_API_KEY 없음')
    model=os.getenv('OPENAI_MODEL') or DEFAULT_MODEL
    evaluation=yaml.safe_load((LAB/'queries/eval_w6.yaml').read_text())['questions']
    questions=[{'id':id_,'question':next(q['question'] for q in evaluation if q['id']==id_)} for id_ in ('A1','A2','X01','X03')]
    questions += [{'id':'T01','question':'TEAMFICIAL과 SeCause가 둘 다 쓴 기술은?'},
                  {'id':'T02','question':'Redis를 제안만 한 프로젝트는?'},
                  {'id':'T03','question':'목적이 기록되지 않은 기술 사용례는 몇 개인가?'}]
    with GraphDatabase.driver(os.getenv('NEO4J_URI',DEFAULT_NEO4J_URI),auth=(os.getenv('NEO4J_USER','neo4j'),os.getenv('NEO4J_PASSWORD',DEFAULT_NEO4J_PASSWORD))) as driver:
        with driver.session(database='neo4j',default_access_mode=READ_ACCESS) as session:
            actual=inspect(session); instructions=prompt(actual)
            # few-shot은 EXPLAIN 및 읽기 실행으로 문법을 검증한다. 결과는 모델에 제공하지 않는다.
            for example in FEW_SHOTS: execute(session,example['cypher'])
            meta={'record_type':'metadata','model':model,'reasoning_effort':'low','verbosity':'low','temperature':None,
                  'temperature_policy':'기존 실험처럼 요청에서 생략','scope':'20개 청크 표본 그래프',
                  'schema':{k:v for k,v in actual.items() if k not in ('nodes','edges')},'prompt':instructions,
                  'answer_schema':OUTPUT_SCHEMA,'repeats':3,'questions':questions,
                  'safety':'정적 단일 읽기 검사 + EXPLAIN query_type=r + execute_read + 10초 제한; 생성 쿼리 자동 수정 없음'}
            output=LAB/'results/text2cypher.jsonl'
            previous=[]
            if output.exists():
                previous=[json.loads(l) for l in output.read_text().splitlines()]
                if previous[0]!=meta: raise ValueError('실행 설정/DB 스냅샷 변경됨')
            else: output.write_text(json.dumps(meta,ensure_ascii=False)+'\n')
            (LAB/'results/text2cypher_schema.json').write_text(json.dumps(actual,ensure_ascii=False,indent=2))
            done={(r['id'],r['round']) for r in previous[1:]}
            for round_ in range(1,4):
                for question in questions:
                    if (question['id'],round_) in done: continue
                    start=time.perf_counter()
                    cypher,usage,response_model,temp=generate(question['question'],instructions,model)
                    rows=[]; error=None; notifications=[]
                    try: rows,notifications=execute(session,cypher)
                    except Exception as exc: error={'type':type(exc).__name__,'code':getattr(exc,'code',None),'message':str(exc)}
                    record={**question,'round':round_,'cypher':cypher,'rows':rows,'row_count':len(rows),
                            'error':error,'notifications':notifications,'judgment':None,'failure_type':None,
                            'response':user_message(cypher,rows,error),
                            'tokens':usage.get('total_tokens') if usage else None,'usage':usage,
                            'latency_ms':round((time.perf_counter()-start)*1000,2),
                            'response_model':response_model,'response_temperature':temp}
                    with output.open('a') as file: file.write(json.dumps(record,ensure_ascii=False)+'\n')
                    print(f"{round_} {question['id']}: rows={len(rows)}, error={error}",flush=True)
            if inspect(session)['snapshot_hash']!=actual['snapshot_hash']: raise ValueError('실행 중 그래프 변경됨')


if __name__=='__main__': main()
