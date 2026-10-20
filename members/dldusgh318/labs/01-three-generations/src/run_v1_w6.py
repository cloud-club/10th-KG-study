"""W3 agent.py를 변경하지 않는 W6 실행/계측 래퍼. 그래프 접근 없음.

    .venv/bin/python src/run_v1_w6.py --prompt-key
    .venv/bin/python src/run_v1_w6.py --retrieve-only
"""
import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import time
from unittest.mock import patch

import yaml
import agent
import hybrid_search
from common import LAB, EMBED_MODEL
from gen2_pgvector import EF_SEARCH

STALE_CHUNK = '캐시~2#978'


def recall(question, retrieved):
    """gold를 포함하는 동등성 그룹만 대체 정답으로 인정한다."""
    gold = set(question.get('gold_chunks', []))
    if not gold:
        return [], None, []
    units = [{id_} for id_ in sorted(gold)]
    for group in question.get('equivalent_groups', []):
        members = set(group.get('chunk_ids', []))
        overlapping = [unit for unit in units if unit & members]
        if overlapping:
            units = [unit for unit in units if not unit & members]
            units.append(set.union(members, *overlapping))
    hits = [id_ for id_ in retrieved if any(id_ in unit for unit in units)]
    matched = [sorted(unit) for unit in units if unit & set(retrieved)]
    return hits, len(matched) / len(units), matched


def settings(path):
    return {
        'record_type': 'metadata', 'agent': 'v1-week3-unchanged',
        'model': os.getenv('OPENAI_MODEL') or agent.DEFAULT_MODEL,
        'top_k': agent.TOP_K, 'retriever_limit_each': hybrid_search.RETRIEVER_LIMIT,
        'rrf_k': hybrid_search.RRF_K, 'embedding_model': EMBED_MODEL,
        'vector_ef_search': EF_SEARCH, 'context_max_chars': agent.CONTEXT_MAX_CHARS,
        'temperature': None, 'temperature_policy': 'W3와 동일하게 API 요청에서 생략; 기본값 숫자를 가정하지 않음',
        'reasoning_effort': 'low', 'verbosity': 'low',
        'prompt': agent.SYSTEM_INSTRUCTIONS,
        'user_prompt_template': 'Question:\n{question}\n\nContext:\n{context}',
        'answer_schema': agent.ANSWER_SCHEMA, 'graph_used': False,
        'agent_sha256': hashlib.sha256(Path(agent.__file__).read_bytes()).hexdigest(),
        'eval_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'latency_policy': '검색 시작부터 답변·인용 검증 종료까지. 첫 모델 로딩 포함. 재개 시 기존 행은 재측정하지 않음.',
        'tokens_policy': 'Responses API usage 실측값. 로컬 임베딩은 제외.',
        'usage_reference': 'https://developers.openai.com/api/docs/guides/token-counting',
        'recall_policy': 'gold를 포함하는 equivalent_groups를 1단위로 계산. 그중 하나만 검색돼도 적중. gold 없으면 null.',
    }


def score_template(rows, config, path):
    lines = ['# W6 v1 채점', '', '실제 답변을 expected와 비교한다. 인용 형식 검증은 정답 판정이 아니다.',
             '', '## 고정 설정', '', '```json', json.dumps(config, ensure_ascii=False, indent=2), '```', '']
    for row in rows:
        lines += [f"## {row['id']}", '', f"expected: {row['expected']}", '',
                  f"answer: {row['answer']}", '',
                  '판정: 미채점 (correct / partial / wrong 의미 비교 필요)',
                  '이유: 미기입', '',
                  f"recall@5: {row['recall_at_5']}; citation_valid: {row['citation_valid']}; 옛 캐시 메모: {row['stale_cache_retrieved']}", '']
    path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eval', type=Path, default=LAB/'queries/eval_w6.yaml')
    parser.add_argument('--retrieve-only', action='store_true')
    parser.add_argument('--prompt-key', action='store_true')
    args = parser.parse_args()
    if args.prompt_key:
        import getpass
        os.environ['OPENAI_API_KEY'] = getpass.getpass('OpenAI API 키 (저장하지 않음): ')
    # dotenv는 선택 사항이다. 키와 모델만 읽으며 화면/결과 파일에 키를 남기지 않는다.
    env_path = LAB/'.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            name, sep, value = line.strip().partition('=')
            if sep and name in ('OPENAI_API_KEY','OPENAI_MODEL'):
                os.environ.setdefault(name, value.strip().strip('\"\''))
    if not args.retrieve_only and not os.getenv('OPENAI_API_KEY'):
        parser.error('OPENAI_API_KEY 없음. --prompt-key 또는 무시되는 .env 사용. LLM 실행 결과는 생성하지 않음.')
    questions = yaml.safe_load(args.eval.read_text())['questions']
    config = settings(args.eval)
    destination = LAB/'results'
    destination.mkdir(exist_ok=True)
    output = destination/('v1_w6_retrieval.jsonl' if args.retrieve_only else 'v1_w6.jsonl')
    existing = []
    if output.exists():
        records = [json.loads(line) for line in output.read_text().splitlines()]
        if not records or records[0] != config:
            raise ValueError('기존 실행과 설정/평가셋 불일치. 기존 결과를 별도 보관한 후 재실행할 것.')
        existing = records[1:]
    else:
        output.write_text(json.dumps(config, ensure_ascii=False)+'\n', encoding='utf-8')
    done = {row['id'] for row in existing}
    rows = existing[:]
    for question in questions:
        if question['id'] in done:
            continue
        start = time.perf_counter()
        retrieved = hybrid_search.hybrid_search(question['question'], agent.TOP_K)
        ids = [r['id'] for r in retrieved]
        hits, recall_value, groups = recall(question, ids)
        row = {'id': question['id'], 'question': question['question'],
               'expected': question.get('expected'), 'retrieved_top5': ids,
               'gold_hit': hits, 'recall_at_5': recall_value, 'gold_groups_hit': groups,
               'stale_cache_retrieved': STALE_CHUNK in ids}
        if args.retrieve_only:
            row['retrieval_latency_ms'] = round((time.perf_counter()-start)*1000, 2)
        else:
            observed = {}
            original_urlopen = agent.urlopen

            @contextmanager
            def metered_urlopen(request, **kwargs):
                # 요청 body/프롬프트를 변경하지 않고 기존 응답만 계측한다.
                with original_urlopen(request, **kwargs) as response:
                    raw = json.load(response)
                observed.update(usage=raw.get('usage'), response_model=raw.get('model'),
                                response_temperature=raw.get('temperature'))
                yield io.BytesIO(json.dumps(raw).encode())

            with patch.object(agent, 'urlopen', metered_urlopen):
                result = agent.answer_from_chunks(question['question'], retrieved, model=config['model'])
            usage = observed.get('usage')
            row.update(answer=result['answer'], citations=result['citations'],
                       citation_valid=result['citation_verified'], context_trace=result['context_trace'],
                       latency_ms=round((time.perf_counter()-start)*1000, 2),
                       tokens=usage.get('total_tokens') if usage else None, token_usage=usage,
                       response_model=observed.get('response_model'),
                       response_temperature=observed.get('response_temperature'),
                       stale_cache_cited=any(c['chunk_id']==STALE_CHUNK for c in result['citations']))
        with output.open('a', encoding='utf-8') as file:
            file.write(json.dumps(row, ensure_ascii=False)+'\n')
        rows.append(row)
        print(f"{row['id']}: recall={recall_value}, stale_cache={row['stale_cache_retrieved']}", flush=True)
    if not args.retrieve_only:
        score_path = destination/'v1_w6_score.md'
        if not score_path.exists():
            score_template(rows, config, score_path)
    print(f'저장: {output}')


if __name__ == '__main__':
    main()
