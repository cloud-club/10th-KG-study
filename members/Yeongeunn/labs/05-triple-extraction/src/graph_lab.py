"""Reviewed local triples -> PostgreSQL, RDF, Neo4j, browser graph."""
import argparse, hashlib, json, re, sys
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'data/Yeongeunn/kg-v0'
sys.path.insert(0,str(ROOT/'members/Yeongeunn/labs/04-hybrid-evaluation/src'))
from search_lab import db, settings
PAIRS={'exposesAPI':('Service','API'),'implementsOperation':('API','Operation'),'callsService':('API','Service'),'requiresPolicy':('Operation','Policy'),'checksPolicy':('API','Policy'),'blocksOperation':('Policy','Operation'),'concernsTransactionType':('Policy','TransactionType')}

def load():
    data=json.loads((OUT/'graph-reviewed.json').read_text());lookup={n['id']:n for n in data['nodes']}
    chunks={c['id']:c for c in map(json.loads,(ROOT/'data/Yeongeunn/processed/notion-chunks.jsonl').read_text().splitlines())}
    assert len(lookup)==len(data['nodes'])
    assert len({e['id'] for e in data['edges']})==len(data['edges'])
    for e in data['edges']:
        assert (lookup[e['subject']]['class'],lookup[e['object']]['class'])==PAIRS[e['predicate']]
        assert e['evidence'] and e['review_status']=='source_reviewed_by_assistant'
        if e['predicate']=='blocksOperation':assert e['condition']
        for ev in e['evidence']:
            text=chunks[ev['chunk_id']][ev['field']]
            assert hashlib.sha256(text.encode()).hexdigest()==ev['source_sha256']
            assert text[ev['start']:ev['end']]==ev['quote']
    return data,hashlib.sha256((OUT/'graph-reviewed.json').read_bytes()).hexdigest()[:16]

def rdf_export(data,run):
    from rdflib import Graph,Namespace,RDF,RDFS,Literal
    from rdflib.compare import isomorphic
    kg=Namespace('https://example.org/erumpay/ontology/'); ns=Namespace('https://example.org/erumpay/data/'+run+'/')
    g=Graph();g.bind('kg',kg);g.bind('data',ns)
    for n in data['nodes']:g.add((ns[n['id']],RDF.type,kg[n['class']]));g.add((ns[n['id']],RDFS.label,Literal(n['label'],lang='ko')))
    for e in data['edges']:
        triple=(ns[e['subject']],kg[e['predicate']],ns[e['object']]);g.add(triple)
        a=ns['assertion-'+e['id']];g.add((a,RDF.type,RDF.Statement))
        for predicate,value in [(RDF.subject,triple[0]),(RDF.predicate,triple[1]),(RDF.object,triple[2])]:g.add((a,predicate,value))
        g.add((a,kg.reviewStatus,Literal(e['review_status'])))
        g.add((a,kg.condition,Literal(e['condition'],lang='ko')))
        for i,ev in enumerate(e['evidence']):
            v=ns['evidence-'+e['id']+'-'+str(i)];g.add((a,kg.evidence,v))
            for key,value in ev.items():g.add((v,kg[key],Literal(value)))
    g.serialize(OUT/'facts.ttl',format='turtle');g.serialize(OUT/'facts.jsonld',format='json-ld')
    assert isomorphic(g,Graph().parse(OUT/'facts.ttl',format='turtle'))
    assert isomorphic(g,Graph().parse(OUT/'facts.jsonld',format='json-ld'))
    return len(g)

def store_pg(data,run):
    from psycopg.types.json import Jsonb
    with db() as c:
        c.execute('CREATE SCHEMA IF NOT EXISTS yeongeunn_kg')
        c.execute('CREATE TABLE IF NOT EXISTS yeongeunn_kg.entities (run text, id text, class text NOT NULL, label text NOT NULL, PRIMARY KEY(run,id))')
        c.execute('CREATE TABLE IF NOT EXISTS yeongeunn_kg.edges (run text,id text,subject text NOT NULL,predicate text NOT NULL,object text NOT NULL,condition text NOT NULL,review_status text NOT NULL,PRIMARY KEY(run,id),FOREIGN KEY(run,subject) REFERENCES yeongeunn_kg.entities(run,id),FOREIGN KEY(run,object) REFERENCES yeongeunn_kg.entities(run,id))')
        c.execute('CREATE TABLE IF NOT EXISTS yeongeunn_kg.evidence (run text,edge_id text,ordinal int,payload jsonb NOT NULL,PRIMARY KEY(run,edge_id,ordinal),FOREIGN KEY(run,edge_id) REFERENCES yeongeunn_kg.edges(run,id))')
        for n in data['nodes']:c.execute('INSERT INTO yeongeunn_kg.entities VALUES(%s,%s,%s,%s) ON CONFLICT(run,id) DO UPDATE SET label=excluded.label,class=excluded.class',(run,n['id'],n['class'],n['label']))
        for e in data['edges']:
            c.execute('INSERT INTO yeongeunn_kg.edges VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(run,id) DO UPDATE SET condition=excluded.condition,review_status=excluded.review_status',(run,e['id'],e['subject'],e['predicate'],e['object'],e['condition'],e['review_status']))
            for i,ev in enumerate(e['evidence']):c.execute('INSERT INTO yeongeunn_kg.evidence VALUES(%s,%s,%s,%s) ON CONFLICT(run,edge_id,ordinal) DO UPDATE SET payload=excluded.payload',(run,e['id'],i,Jsonb(ev)))
        return {t:c.execute('SELECT count(*) FROM yeongeunn_kg.'+t+' WHERE run=%s',(run,)).fetchone()[0] for t in ['entities','edges','evidence']}

def driver():
    from neo4j import GraphDatabase
    s=settings();return GraphDatabase.driver('bolt://127.0.0.1:'+s.get('NEO4J_BOLT_PORT','7687'),auth=('neo4j',s.get('NEO4J_PASSWORD','kgstudy2026')))

def relname(s):return re.sub(r'(?<!^)(?=[A-Z])','_',s).upper() # Explicit overrides below for acronyms.
RELS={k: {'exposesAPI':'EXPOSES_API','implementsOperation':'IMPLEMENTS_OPERATION','callsService':'CALLS_SERVICE','requiresPolicy':'REQUIRES_POLICY','checksPolicy':'CHECKS_POLICY','blocksOperation':'BLOCKS_OPERATION','concernsTransactionType':'CONCERNS_TRANSACTION_TYPE'}[k] for k in PAIRS}

def store_neo(data,run):
    with driver() as d, d.session() as session:
        session.run('CREATE CONSTRAINT yeongeunn_kg_identity IF NOT EXISTS FOR (n:KGStudyYeongeunn) REQUIRE n.uid IS UNIQUE').consume()
        def txwrite(tx):
            for n in data['nodes']:
                assert n['class'] in {v for p in PAIRS.values() for v in p}
                tx.run('MERGE (n:KGStudyYeongeunn:'+n['class']+' {uid:$uid}) SET n.id=$id,n.run=$run,n.label=$label,n.kind=$kind',uid=run+':'+n['id'],id=n['id'],run=run,label=n['label'],kind=n['class']).consume()
            for e in data['edges']:
                tx.run('MATCH (a:KGStudyYeongeunn {uid:$a}), (b:KGStudyYeongeunn {uid:$b}) MERGE (a)-[r:'+RELS[e['predicate']]+' {id:$id}]->(b) SET r.run=$run,r.predicate=$predicate,r.condition=$condition,r.evidence_json=$evidence,r.review_status=$review',a=run+':'+e['subject'],b=run+':'+e['object'],id=e['id'],run=run,predicate=e['predicate'],condition=e['condition'],evidence=json.dumps(e['evidence'],ensure_ascii=False),review=e['review_status']).consume()
        session.execute_write(txwrite)
        n=session.run('MATCH (n:KGStudyYeongeunn {run:$run}) RETURN count(n) AS n',run=run).single()['n']
        e=session.run('MATCH (:KGStudyYeongeunn {run:$run})-[r]->(:KGStudyYeongeunn {run:$run}) RETURN count(r) AS n',run=run).single()['n']
        return {'nodes':n,'edges':e}

def query(run):
    queries={
      'one_hop': 'MATCH (a:KGStudyYeongeunn {run:$run,id:"withdraw-api"})-[r:CALLS_SERVICE]->(s:KGStudyYeongeunn {run:$run}) RETURN a.label AS api,type(r) AS relation,s.label AS service',
      'paths_1_3': 'MATCH p=(a:KGStudyYeongeunn {run:$run,id:"withdraw-api"})-[*1..3]->(b:KGStudyYeongeunn {run:$run}) WHERE all(n IN nodes(p) WHERE n.run=$run) RETURN [n IN nodes(p)|n.label] AS nodes,[r IN relationships(p)|type(r)] AS relations LIMIT 50',
      'payment_multihop': 'MATCH (a:KGStudyYeongeunn {run:$run,id:"withdraw-api"})-[:CALLS_SERVICE]->(s:KGStudyYeongeunn {run:$run,id:"payment"})-[:EXPOSES_API]->(api:KGStudyYeongeunn {run:$run})-[:CHECKS_POLICY]->(p:KGStudyYeongeunn {run:$run})<-[:REQUIRES_POLICY]-(o:KGStudyYeongeunn {run:$run,id:"withdraw"}) RETURN s.label AS service,api.label AS candidate_api,p.label AS policy',
      'card_multihop': 'MATCH (a:KGStudyYeongeunn {run:$run,id:"withdraw-api"})-[:CALLS_SERVICE]->(s:KGStudyYeongeunn {run:$run,id:"card"})-[:EXPOSES_API]->(api:KGStudyYeongeunn {run:$run})-[:IMPLEMENTS_OPERATION]->(op:KGStudyYeongeunn {run:$run}) RETURN s.label AS service,api.label AS candidate_api,op.label AS operation',
      'withdrawal_conditions':'MATCH (p:KGStudyYeongeunn {run:$run})-[r:BLOCKS_OPERATION]->(o:KGStudyYeongeunn {run:$run,id:"withdraw"}) RETURN p.label AS policy,r.condition AS condition,r.evidence_json AS evidence'
    }
    with driver() as d,d.session() as s:result={name:s.run(q,run=run).data() for name,q in queries.items()}
    (OUT/'queries.json').write_text(json.dumps({'run':run,'cypher':queries,'results':result},ensure_ascii=False,indent=2))
    # Cross-check the same three-hop pattern with SQL joins.
    with db() as c:
        sql=c.execute('''SELECT s.label, a.label, o.label FROM yeongeunn_kg.edges e1 JOIN yeongeunn_kg.entities s ON (s.run,s.id)=(e1.run,e1.object) JOIN yeongeunn_kg.edges e2 ON (e2.run,e2.subject)=(e1.run,e1.object) JOIN yeongeunn_kg.entities a ON (a.run,a.id)=(e2.run,e2.object) JOIN yeongeunn_kg.edges e3 ON (e3.run,e3.subject)=(e2.run,e2.object) JOIN yeongeunn_kg.entities o ON (o.run,o.id)=(e3.run,e3.object) WHERE e1.run=%s AND e1.subject='withdraw-api' AND e1.object='card' AND e1.predicate='callsService' AND e2.predicate='exposesAPI' AND e3.predicate='implementsOperation' ''',(run,)).fetchall()
    assert sorted(map(tuple,sql))==sorted((r['service'],r['candidate_api'],r['operation']) for r in result['card_multihop'])
    return {k:len(v) for k,v in result.items()}

def browser(run):
    with driver() as d,d.session() as s:
        nodes=[r['n'] for r in s.run('MATCH (n:KGStudyYeongeunn {run:$run}) RETURN properties(n) AS n',run=run)]
        edges=[r['r'] for r in s.run('MATCH (a:KGStudyYeongeunn {run:$run})-[r]->(b:KGStudyYeongeunn {run:$run}) RETURN {subject:a.id,object:b.id,predicate:r.predicate,condition:r.condition,evidence:r.evidence_json} AS r',run=run)]
    template=(Path(__file__).parent/'graph-template.html').read_text()
    payload=json.dumps({'nodes':nodes,'edges':edges},ensure_ascii=False).replace('<','\\u003c')
    (OUT/'graph.html').write_text(template.replace('__DATA__',payload))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['load','query','browser']);a=p.parse_args()
    data,run=load()
    if a.action=='load':
        rdf=rdf_export(data,run);pg=store_pg(data,run);neo=store_neo(data,run)
        # Running the exact same writes twice must not add duplicates.
        assert store_pg(data,run)==pg and store_neo(data,run)==neo
        assert pg['entities']==neo['nodes']==len(data['nodes']) and pg['edges']==neo['edges']==len(data['edges'])
        report={'run':run,'reviewer':data['reviewer'],'postgres':pg,'neo4j':neo,'rdf_triples_including_metadata':rdf,'roundtrip_isomorphic':True,'idempotency_passed':True,'queries':query(run)}
        (OUT/'graph-run.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));browser(run);print(json.dumps(report,indent=2))
    elif a.action=='query':print(query(run))
    else:browser(run)
