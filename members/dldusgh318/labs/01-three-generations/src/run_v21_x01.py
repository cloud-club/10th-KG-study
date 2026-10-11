"""v2.1: 회수 후보의 코사인 유사도 정렬만 변경. X01 3회, baseline 재실행 없음."""
from contextlib import contextmanager
import hashlib
import io
import json
import os
import time
from unittest.mock import patch

import psycopg
from psycopg import sql
from pgvector.psycopg import register_vector
import yaml

import agent
import graph_retriever as graph
from common import LAB, PG_DSN, PG_TABLE, load_chunks_by_id
from gen2_pgvector import embedder
from hybrid_search import hybrid_search
from run_v1_w6 import recall, settings


def rank_candidates(question, ids, corpus):
    if not ids:
        return []
    vector = embedder().encode([question], normalize_embeddings=True)[0]
    with psycopg.connect(os.getenv('POSTGRES_DSN',PG_DSN)) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        register_vector(conn)
        rows = conn.execute(sql.SQL('''SELECT id, 1-(embedding <=> %s) AS similarity, text
            FROM {} WHERE id=ANY(%s) AND embedding IS NOT NULL
            ORDER BY embedding <=> %s, id''').format(sql.Identifier(PG_TABLE)),
            (vector, ids, vector)).fetchall()
    if {r[0] for r in rows} != set(ids):
        raise ValueError('회수 후보의 기존 임베딩 누락. 후보를 임의로 추가/제거하지 않음')
    for id_,_,text in rows:
        if text != corpus[id_]['text']:
            raise ValueError(f'임베딩 색인 원문 불일치: {id_}')
    return [{'chunk_id':id_, 'similarity':float(score), 'rank':rank}
            for rank,(id_,score,_) in enumerate(rows,1)]


def main():
    env=LAB/'.env'
    if env.exists():
        for line in env.read_text().splitlines():
            name,sep,value=line.strip().partition('=')
            if sep and name in ('OPENAI_API_KEY','OPENAI_MODEL'):
                os.environ.setdefault(name,value.strip().strip('\"\''))
    if not os.getenv('OPENAI_API_KEY'):
        raise ValueError('OPENAI_API_KEY 없음')
    base_path=LAB/'results/w6_runs.jsonl'
    baseline=[json.loads(l) for l in base_path.read_text().splitlines()]
    config=settings(LAB/'queries/eval_w6.yaml')
    for key in ('model','top_k','retriever_limit_each','rrf_k','context_max_chars','temperature',
                'reasoning_effort','verbosity','prompt','answer_schema','agent_sha256','eval_sha256'):
        if config[key]!=baseline[0][key]:
            raise ValueError(f'v2와 설정 불일치: {key}')
    state=graph.load_graph()
    if graph.fingerprint(state)!=baseline[0]['graph_sha256']:
        raise ValueError('v2 이후 그래프 변경됨')
    corpus=load_chunks_by_id()
    question=next(q for q in yaml.safe_load((LAB/'queries/eval_w6.yaml').read_text())['questions'] if q['id']=='X01')
    config.update(agent='v2.1-X01', graph_used=True, repeats=3,
        graph_sha256=graph.fingerprint(state), graph_budgets=[5000,800,2200],max_degree=20,
        sole_change='회수 후보 chunk_id 정렬 → 질문/기존 bge-m3 청크 임베딩 코사인 유사도 내림차순; 동률 chunk_id',
        baseline_reused='results/w6_runs.jsonl',baseline_sha256=hashlib.sha256(base_path.read_bytes()).hexdigest(),
        latency_policy='모델 사전 로딩 후 검색+유사도 정렬+조립+LLM+인용 검증; 공통 그래프 로드는 제외')
    embedder()
    output=LAB/'results/v21_x01.jsonl'
    old=[]
    if output.exists():
        old=[json.loads(l) for l in output.read_text().splitlines()]
        if old[0]!=config:
            raise ValueError('기존 v2.1 설정 불일치')
    else:
        output.write_text(json.dumps(config,ensure_ascii=False)+'\n')
    for round_ in range(1,4):
        if any(r.get('round')==round_ for r in old[1:]):
            continue
        start=time.perf_counter()
        retrieved=hybrid_search(question['question'],agent.TOP_K)
        ids=[r['id'] for r in retrieved]
        prior=next(r for r in baseline[1:] if r['id']=='X01' and r['variant']=='v2' and r['round']==round_)
        if ids!=prior['retrieved_top5']:
            raise ValueError('v2와 v1 top-5 변경됨. 정렬만 바꾼 비교를 유지하기 위해 중단')
        expanded=graph.expand(state,set(ids))
        candidates=sorted({e['chunk_id'] for e in expanded['support_edges']} - set(ids))
        ranking=rank_candidates(question['question'],candidates,corpus)
        context,mapping,trace=graph.assemble_v2(retrieved,state,corpus,
                                              recovery_order=[r['chunk_id'] for r in ranking])
        # 기본 정렬일 때는 저장된 v2 원본 컨텍스트와 비트 단위 동일해야 한다.
        old_context,_,_=graph.assemble_v2(retrieved,state,corpus)
        preview=[json.loads(l) for l in (LAB/'results/w6_context_preview.jsonl').read_text().splitlines()][1:]
        expected_context=next(r['context'] for r in preview if r['id']=='X01' and r['variant']=='v2')
        if old_context!=expected_context:
            raise ValueError('기본 v2 컨텍스트가 기존 기록과 달라짐')
        included=trace['included_recovered_chunks']
        for candidate in ranking:
            candidate.update(included=candidate['chunk_id'] in included,
                             exclusion_reason=None if candidate['chunk_id'] in included else 'recovery_budget')
        target=next((r for r in ranking if r['chunk_id']=='경력기술서#325'),None)
        observed={}; original=agent.urlopen

        @contextmanager
        def measured(request,**kwargs):
            with original(request,**kwargs) as response:
                raw=json.load(response)
            observed.update(usage=raw.get('usage'),model=raw.get('model'),temperature=raw.get('temperature'))
            yield io.BytesIO(json.dumps(raw).encode())

        with patch.object(agent,'urlopen',measured):
            payload=agent.call_openai(question['question'],context,model=config['model'])
        citations=agent.verify_citations(payload,mapping)
        valid=all(c['valid'] for c in citations) and (bool(citations) or payload.get('answer')==agent.NOT_FOUND)
        hits,rec,groups=recall(question,[r['id'] for r in mapping.values()])
        usage=observed['usage']
        row={'id':'X01','variant':'v2.1','round':round_,'answer':payload['answer'],
             'expected':question['expected'],'retrieved_top5':ids,'recovery_ranking':ranking,
             'target_chunk':{'chunk_id':'경력기술서#325','candidate':target is not None,
                             'rank':target['rank'] if target else None,
                             'similarity':target['similarity'] if target else None,
                             'included':bool(target and target['included'])},
             'graph_facts_text':trace.get('graph_facts_text',''),
             'redis_caching_infra_in_facts':'Redis 캐싱 인프라' in trace.get('graph_facts_text',''),
             'context':context,'context_trace':trace,'context_chunk_ids':[r['id'] for r in mapping.values()],
             'seed_nodes':trace['seed_nodes'],'expanded_nodes':trace['expanded_nodes'],
             'recovered_chunks':trace['recovered_chunks'],'included_recovered_chunks':included,
             'gold_hit':hits,'recall_at_5':rec,'gold_groups_hit':groups,
             'gold_reached_via_graph':any(id_ not in ids for id_ in hits),
             'citations':citations,'citation_valid':valid,
             'tokens':usage.get('total_tokens') if usage else None,'token_usage':usage,
             'response_model':observed['model'],'response_temperature':observed['temperature'],
             'latency_ms':round((time.perf_counter()-start)*1000,2)}
        with output.open('a') as file:
            file.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(f"{round_}회: {row['answer']}\ntarget={row['target_chunk']}\n그래프 사실 원문:{row['graph_facts_text']}",flush=True)


if __name__=='__main__':
    main()
