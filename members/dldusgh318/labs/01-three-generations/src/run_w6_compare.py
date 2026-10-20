"""동일 생성 설정으로 v1/v2 7문항 × 3회 실행. 채점은 별도 의미 검토."""
import argparse
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import time
from unittest.mock import patch

import yaml
import agent
from common import LAB, load_chunks_by_id
from gen2_pgvector import embedder
from hybrid_search import hybrid_search
import graph_retriever as graph
from run_v1_w6 import settings, recall, STALE_CHUNK


def majority(grades):
    if len(grades) != 3 or any(g not in ('correct','partial','wrong') for g in grades):
        raise ValueError('3개 의미 채점 필요')
    for grade in ('correct','partial','wrong'):
        if grades.count(grade) >= 2:
            return grade
    return 'partial'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    env = LAB/'.env'
    if env.exists():
        for line in env.read_text().splitlines():
            name,sep,value = line.strip().partition('=')
            if sep and name in ('OPENAI_API_KEY','OPENAI_MODEL'):
                os.environ.setdefault(name,value.strip().strip('\"\''))
    if not args.dry_run and not os.getenv('OPENAI_API_KEY'):
        parser.error('OPENAI_API_KEY 없음')
    evaluation = LAB/'queries/eval_w6.yaml'
    questions = yaml.safe_load(evaluation.read_text())['questions']
    config = settings(evaluation)
    prior = json.loads((LAB/'results/v1_w6.jsonl').read_text().splitlines()[0])
    for key in ('model','top_k','retriever_limit_each','rrf_k','context_max_chars','temperature',
                'reasoning_effort','verbosity','prompt','answer_schema','agent_sha256'):
        if prior[key] != config[key]:
            raise ValueError(f'기존 v1과 설정 변경: {key}')
    state = graph.load_graph()
    corpus = load_chunks_by_id()
    config.update(agent='w6-v1-v2-3runs', graph_used='v2 only', repeats=3,
                  graph_sha256=graph.fingerprint(state), graph_budgets=[5000,800,2200],
                  max_degree=20, graph_hops='use→tech→use 2홉; 소속 Project는 속성 연결 조회',
                  latency_policy='모델 사전 로딩 후 매 실행 검색+조립+LLM+검증. 공통 DB 스냅샷 로드는 제외.',
                  grading_policy='각 실행을 expected와 의미 비교 후 다수결. 3회 모두 다르면 partial.')
    embedder()  # 양쪽의 cold-start 비용을 제거한다.
    path = LAB/'results'/('w6_context_preview.jsonl' if args.dry_run else 'w6_runs.jsonl')
    previous = []
    if path.exists():
        previous = [json.loads(l) for l in path.read_text().splitlines()]
        if previous[0] != config:
            raise ValueError('기존 실행과 설정/DB 스냅샷 불일치. 결과 보관 후 새 실행 필요')
    else:
        path.write_text(json.dumps(config,ensure_ascii=False)+'\n')
    done = {(r['id'],r['variant'],r['round']) for r in previous[1:]}
    for round_ in range(1, 2 if args.dry_run else 4):
        for q in questions:
            for variant in (('v1','v2') if round_%2 else ('v2','v1')):
                if (q['id'],variant,round_) in done:
                    continue
                start = time.perf_counter()
                retrieved = hybrid_search(q['question'], agent.TOP_K)
                ids = [r['id'] for r in retrieved]
                observed = {}
                original_urlopen = agent.urlopen

                @contextmanager
                def measured(request, **kwargs):
                    with original_urlopen(request, **kwargs) as response:
                        raw = json.load(response)
                    observed.update(usage=raw.get('usage'),model=raw.get('model'),temperature=raw.get('temperature'))
                    yield io.BytesIO(json.dumps(raw).encode())

                if args.dry_run:
                    if variant == 'v1':
                        context,mapping,trace = agent.assemble_context(retrieved)
                    else:
                        context,mapping,trace = graph.assemble_v2(retrieved,state,corpus)
                    result = {'context_trace':trace, 'context_chunk_ids':[r['id'] for r in mapping.values()],
                              'context':context}
                else:
                    with patch.object(agent,'urlopen',measured):
                        if variant == 'v1':
                            result = agent.answer_from_chunks(q['question'],retrieved,model=config['model'])
                        else:
                            result = graph.answer(q['question'],retrieved,state,corpus,model=config['model'])
                trace = result['context_trace']
                included = result['context_chunk_ids']
                hits,value,groups = recall(q,included)
                graph_gold = [id_ for id_ in hits if id_ not in ids]
                usage = observed.get('usage')
                row = {'id':q['id'],'variant':variant,'round':round_,'question':q['question'],
                       'expected':q['expected'],'retrieved_top5':ids,**result,
                       'gold_hit':hits,'recall_at_5':value,'gold_groups_hit':groups,
                       'seed_nodes':trace.get('seed_nodes',[]),'expanded_nodes':trace.get('expanded_nodes',[]),
                       'recovered_chunks':trace.get('recovered_chunks',[]),
                       'included_recovered_chunks':trace.get('included_recovered_chunks',[]),
                       'gold_reached_via_graph':bool(graph_gold),'graph_gold_chunks':graph_gold,
                       'citation_valid':result.get('citation_verified'),
                       'latency_ms':round((time.perf_counter()-start)*1000,2),
                       'tokens':usage.get('total_tokens') if usage else None,'token_usage':usage,
                       'response_model':observed.get('model'),'response_temperature':observed.get('temperature'),
                       'stale_cache_retrieved':STALE_CHUNK in ids,
                       'stale_cache_in_context':STALE_CHUNK in included}
                with path.open('a') as f:
                    f.write(json.dumps(row,ensure_ascii=False)+'\n')
                print(f"{round_} {q['id']} {variant}: recall={value}, graph_gold={graph_gold}, seeds={len(row['seed_nodes'])}",flush=True)


if __name__ == '__main__':
    main()
