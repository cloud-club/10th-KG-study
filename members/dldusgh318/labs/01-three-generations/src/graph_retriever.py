"""v1 top-5 chunk_id만으로 진입하는 읽기 전용 2-hop 기술 공유 확장."""
import hashlib
import json
import os

import psycopg
from psycopg.rows import dict_row

import agent
from common import PG_DSN, load_chunks_by_id

RELATIONS = {'partOf', 'usesTechnology', 'replaces'}
STATUS = {'implemented': '구현됨', 'proposed': '제안만', 'not_implemented': '미구현'}


def load_graph():
    with psycopg.connect(os.getenv('POSTGRES_DSN', PG_DSN), row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        entities = conn.execute('SELECT entity_id,type,label,props FROM entities ORDER BY entity_id').fetchall()
        edges = conn.execute('SELECT id,subject,predicate,object,chunk_id,evidence FROM edges ORDER BY id').fetchall()
    return {'entities': entities, 'edges': edges}


def fingerprint(graph):
    return hashlib.sha256(json.dumps(graph, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def expand(graph, seed_chunk_ids):
    nodes = {n['entity_id']: n for n in graph['entities']}
    edges = graph['edges']
    seeds = set()
    neighbors = {id_: set() for id_ in nodes}
    for e in edges:
        if e['predicate'] in RELATIONS and e['object'] in nodes:
            neighbors[e['subject']].add(e['object'])
            neighbors[e['object']].add(e['subject'])
        if e['chunk_id'] in seed_chunk_ids:
            for id_ in (e['subject'], e['object'] if e['predicate'] in RELATIONS else None):
                if id_ in nodes and nodes[id_]['type'] in ('TechnologyUse', 'Technology'):
                    seeds.add(id_)
    skipped = set()

    def allowed(id_):
        if len(neighbors[id_]) > 20:
            skipped.add(id_)
            return False
        return True

    techs = {id_ for id_ in seeds if nodes[id_]['type'] == 'Technology'}
    uses = {id_ for id_ in seeds if nodes[id_]['type'] == 'TechnologyUse'}
    for e in edges:
        if e['subject'] in uses and e['predicate'] == 'usesTechnology' and allowed(e['subject']):
            techs.add(e['object'])
    for e in edges:
        if e['object'] in techs and e['predicate'] == 'usesTechnology' and allowed(e['object']):
            uses.add(e['subject'])
    support = [e for e in edges if e['subject'] in uses]
    expanded = set(uses) | techs
    expanded.update(e['object'] for e in support if e['predicate'] == 'partOf')
    return {'seed_nodes': sorted(seeds), 'expanded_nodes': sorted(expanded-seeds),
            'skipped_high_degree': sorted(skipped), 'support_edges': support,
            'uses': sorted(uses)}


def assemble_v2(retrieved, graph, corpus, *, recovery_order=None):
    trace = expand(graph, {r['id'] for r in retrieved})
    if not trace['seed_nodes']:
        context, mapping, assembly = agent.assemble_context(retrieved)
        return context, mapping, {**trace, 'fallback_v1': True, 'recovered_chunks': [],
                                 'included_recovered_chunks': [], 'assembly': assembly}
    context, mapping, assembly = agent.assemble_context(retrieved, max_chars=5000)
    existing = {r['id'] for r in retrieved}
    edge_chunks = sorted({e['chunk_id'] for e in trace['support_edges']} - existing)
    if recovery_order is not None:
        if len(recovery_order) != len(edge_chunks) or set(recovery_order) != set(edge_chunks):
            raise ValueError('회수 순서는 기존 후보 집합의 순열이어야 함')
        edge_chunks = list(recovery_order)
    # 순서는 질문/정답과 무관한 chunk_id 정렬. 예산 초과 시 원문을 통째로 제외한다.
    recovered = []; omitted = []; blocks = []; used = 0
    for id_ in edge_chunks:
        if id_ not in corpus:
            raise ValueError(f'그래프 근거 원문 없음: {id_}')
        row = corpus[id_]
        number = len(mapping)+1
        block = f'\n\n[{number}]\ntitle: {row.get("title", "")}\nsource: {row.get("source", "")}\ntext: {row["text"]}'
        if used+len(block) > 2200:
            omitted.append(id_)
            continue
        mapping[number] = row
        blocks.append(block); used += len(block); recovered.append(id_)
    numbers = {row['id']: i for i,row in mapping.items()}
    nodes = {n['entity_id']: n for n in graph['entities']}
    groups = {}
    for id_ in trace['uses']:
        use = nodes[id_]
        rel = [e for e in trace['support_edges'] if e['subject'] == id_]
        projects = {e['object'] for e in rel if e['predicate'] == 'partOf'}
        techs = {e['object'] for e in rel if e['predicate'] == 'usesTechnology'}
        refs = {numbers[e['chunk_id']] for e in rel if e['chunk_id'] in numbers}
        if not refs:
            continue
        for p in sorted(projects):
            for t in sorted(techs):
                key = (p,t,use['props'].get('status'))
                group = groups.setdefault(key, {'purposes': set(), 'refs': set()})
                if use['props'].get('purpose'):
                    group['purposes'].add(use['props']['purpose'])
                group['refs'].update(refs)
    facts = '\n\n그래프 파생 사실 (인용 snippet은 번호가 가리키는 원문에서 복사):\n'
    fact_count = 0
    for (p,t,status), group in sorted(groups.items(), key=lambda pair: str(pair[0])):
        purpose = ' / '.join(sorted(group['purposes'])) or '목적 미기재'
        refs = ', '.join(str(n) for n in sorted(group['refs']))
        line = f'{nodes[p]["label"]}은 {nodes[t]["label"]}를 {purpose} 용도로 사용한 기록이 있다 ({STATUS.get(status,"상태 미기재")}) [근거 {refs}]\n'
        if len(facts)+len(line) <= 800:
            facts += line; fact_count += 1
    if not fact_count:
        facts = ''
    combined = context+facts+''.join(blocks)
    assert len(combined) <= 8000
    return combined, mapping, {**trace, 'fallback_v1': False,
        'recovered_chunks': edge_chunks, 'included_recovered_chunks': recovered,
        'budget_dropped_chunks': omitted, 'assembly': assembly, 'fact_count': fact_count,
        'graph_facts_text': facts,
        'context_chars': len(combined),
        'budget_used': {'v1': len(context), 'facts': len(facts), 'recovered': used}}


def answer(question, retrieved, graph, corpus=None, model=None, generator=None):
    context, mapping, trace = assemble_v2(retrieved, graph, corpus if corpus is not None else load_chunks_by_id())
    payload = generator(question, context) if generator else agent.call_openai(question, context, model=model)
    citations = agent.verify_citations(payload, mapping)
    valid = all(c['valid'] for c in citations) and (bool(citations) or payload.get('answer') == agent.NOT_FOUND)
    return {'answer': payload['answer'], 'citations': citations, 'citation_verified': valid,
            'context_chunk_ids': [r['id'] for r in mapping.values()], 'context_trace': trace,
            'seed_nodes': trace['seed_nodes'], 'expanded_nodes': trace['expanded_nodes'],
            'recovered_chunks': trace['recovered_chunks'],
            'included_recovered_chunks': trace['included_recovered_chunks']}
