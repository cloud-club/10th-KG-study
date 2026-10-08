"""Public, synthetic version of the W5 evidence-validation/load/export flow."""
import argparse, hashlib, json, os
from pathlib import Path
from urllib.parse import quote
from rdflib import Graph, Namespace, Literal, RDF, RDFS
from rdflib.compare import isomorphic

BASE = Path(__file__).resolve().parent.parent
KG = Namespace('https://example.org/kg/')
ID = Namespace('https://example.org/id/')
CLASSES = ['Task', 'Issue', 'Change', 'Verification', 'Artifact']
RELATIONS = {'hasIssue': ('Task','Issue','HAS_ISSUE'),
 'relatedCommit': ('Issue','Change','RELATED_COMMIT'),
 'hasVerification': ('Issue','Verification','HAS_VERIFICATION'),
 'hasExecution': ('Verification','Verification','HAS_EXECUTION'),
 'partOfRun': ('Verification','Verification','PART_OF_RUN'),
 'hasTestRun': ('Artifact','Verification','HAS_TEST_RUN'),
 'forRelease': ('Artifact','Artifact','FOR_RELEASE'),
 'produces': ('Change','Artifact','PRODUCES')}

def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def uri(value):
    return ID[quote(value, safe='')]

def validate(data):
    nodes = {n['id']: n for n in data['nodes']}
    assert len(nodes) == len(data['nodes']), 'Duplicate node ID'
    for n in nodes.values():
        assert n['type'] in CLASSES
    edges = {}
    for t in data['triples']:
        assert t['predicate'] in RELATIONS, 'Unknown predicate'
        source, target, _ = RELATIONS[t['predicate']]
        assert nodes[t['subject']]['type'] == source
        assert nodes[t['object']]['type'] == target
        doc = data['documents'][t['document_id']]
        assert 0 <= t['start'] < t['end'] <= len(doc)
        assert doc[t['start']:t['end']] == t['evidence'], 'Evidence mismatch'
        assert t['approved'] is True, 'Pending semantic review'
        key = stable([t['subject'],t['predicate'],t['object']])
        edges[key] = t | {'id': key}
    return nodes, list(edges.values())

def export(data, out):
    nodes, edges = validate(data)
    out.mkdir(parents=True, exist_ok=True)
    g = Graph(); g.bind('kg',KG); g.bind('id',ID)
    for cls in CLASSES: g.add((KG[cls], RDF.type, RDFS.Class))
    for pred,(src,dst,_) in RELATIONS.items():
        g.add((KG[pred], RDF.type, RDF.Property))
        g.add((KG[pred], RDFS.domain, KG[src])); g.add((KG[pred], RDFS.range, KG[dst]))
    for n in nodes.values():
        g.add((uri(n['id']), RDF.type, KG[n['type']]))
        for k,v in n.items():
            if k not in ['id','type']: g.add((uri(n['id']), KG[k], Literal(v)))
    for t in edges:
        g.add((uri(t['subject']), KG[t['predicate']], uri(t['object'])))
        claim = uri('claim:'+t['id']); g.add((claim,RDF.type,RDF.Statement))
        for p,v in [(RDF.subject,uri(t['subject'])),(RDF.predicate,KG[t['predicate']]),(RDF.object,uri(t['object']))]: g.add((claim,p,v))
        g.add((claim,KG.evidence,Literal(t['evidence'])))
        g.add((claim,KG.documentId,Literal(t['document_id'])))
    g.serialize(out/'graph.ttl',format='turtle'); g.serialize(out/'graph.jsonld',format='json-ld')
    assert isomorphic(Graph().parse(out/'graph.ttl'),Graph().parse(out/'graph.jsonld',format='json-ld'))
    (out/'graph.json').write_text(json.dumps({'nodes':list(nodes.values()),'edges':edges},ensure_ascii=False,indent=2))
    return nodes,edges

def load_postgres(nodes,edges):
    import psycopg
    from psycopg.types.json import Jsonb
    with psycopg.connect(os.environ['POSTGRES_DSN']) as c:
        c.execute('CREATE SCHEMA IF NOT EXISTS kg_study_w5')
        c.execute('CREATE TABLE IF NOT EXISTS kg_study_w5.entities(id text PRIMARY KEY, properties jsonb NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS kg_study_w5.edges(id text PRIMARY KEY, subject text REFERENCES kg_study_w5.entities(id), predicate text, object text REFERENCES kg_study_w5.entities(id))')
        c.execute('CREATE TABLE IF NOT EXISTS kg_study_w5.evidence(edge_id text REFERENCES kg_study_w5.edges(id), document_id text, quote text, start_offset integer, end_offset integer, PRIMARY KEY(edge_id,document_id,start_offset))')
        for n in nodes.values(): c.execute('INSERT INTO kg_study_w5.entities VALUES (%s,%s) ON CONFLICT(id) DO UPDATE SET properties=excluded.properties',(n['id'],Jsonb(n)))
        for t in edges:
            c.execute('INSERT INTO kg_study_w5.edges VALUES (%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING',(t['id'],t['subject'],t['predicate'],t['object']))
            c.execute('INSERT INTO kg_study_w5.evidence VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(t['id'],t['document_id'],t['evidence'],t['start'],t['end']))

def load_neo4j(nodes,edges):
    from neo4j import GraphDatabase
    with GraphDatabase.driver(os.environ['NEO4J_URI'], auth=(os.environ['NEO4J_USER'],os.environ['NEO4J_PASSWORD'])) as driver:
        with driver.session(database=os.getenv('NEO4J_DATABASE','neo4j')) as s:
            s.run('CREATE CONSTRAINT study_w5_id IF NOT EXISTS FOR (n:StudyW5) REQUIRE n.id IS UNIQUE').consume()
            for n in nodes.values():
                # Label/relationship names come only from the closed schema.
                s.run(f"MERGE (n:StudyW5:{n['type']} {{id:$id}}) SET n += $props",id=n['id'],props=n).consume()
            for t in edges:
                rel=RELATIONS[t['predicate']][2]
                s.run(f'MATCH (a:StudyW5 {{id:$a}}),(b:StudyW5 {{id:$b}}) MERGE (a)-[r:{rel} {{id:$id}}]->(b) SET r.evidence=$quote',a=t['subject'],b=t['object'],id=t['id'],quote=t['evidence']).consume()

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--postgres',action='store_true'); p.add_argument('--neo4j',action='store_true'); args=p.parse_args()
    data=json.loads((BASE/'sample.json').read_text()); nodes,edges=export(data,BASE/'outputs')
    if args.postgres: load_postgres(nodes,edges)
    if args.neo4j: load_neo4j(nodes,edges)
    print(json.dumps({'nodes':len(nodes),'edges':len(edges),'rdf_roundtrip':'pass'}))
