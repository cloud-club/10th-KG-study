#!/usr/bin/env python3
"""기존 JSON 벡터를 PostgreSQL에 적재하고 Python/DB 검색을 비교한다."""
import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / 'outputs/vectors_qwen3_2685.json'
spec = importlib.util.spec_from_file_location('previous', HERE.parent / '03_vector_search.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def sql(statement):
    result = subprocess.run(['docker', 'compose', '-f', str(HERE / 'compose.yaml'),
                             'exec', '-T', 'db', 'psql', '-X', '-qAt',
                             '-v', 'ON_ERROR_STOP=1', '-U', 'rag', '-d', 'rag'],
                            input=statement, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError('DB 작업 실패. 컨테이너 상태와 SQL 구성을 확인하세요.')
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--load', action='store_true', help='캐시의 벡터를 재생성 없이 적재')
    parser.add_argument('--query')
    parser.add_argument('--cache', type=Path, default=CACHE)
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--mode', choices=['exact', 'hnsw'], default='exact')
    parser.add_argument('--ef-search', type=int, default=40)
    args = parser.parse_args()
    if not args.load and not args.query:
        parser.error('--load 또는 --query를 지정하세요.')
    if args.ef_search < 1:
        parser.error('--ef-search는 1 이상이어야 합니다.')
    if args.top_k < 1:
        parser.error('--top-k는 1 이상이어야 합니다.')
    saved = json.loads(args.cache.read_text())
    settings, rows = saved['settings'], saved['records']
    vectors = previous.validate_vectors([r['embedding'] for r in rows], len(rows))
    if settings['count'] != len(rows) or len({r['chunk_id'] for r in rows}) != len(rows):
        raise ValueError('캐시 개수 또는 ID 오류')
    if args.load:
        statements = ["BEGIN; SET standard_conforming_strings=on; CREATE EXTENSION IF NOT EXISTS vector;",
            "CREATE TABLE IF NOT EXISTS chunks (chunk_id text PRIMARY KEY, record jsonb NOT NULL, embedding vector(1024) NOT NULL);",
            "CREATE TABLE IF NOT EXISTS cache_settings (id integer PRIMARY KEY CHECK(id=1), settings jsonb NOT NULL);",
            "INSERT INTO cache_settings VALUES (1, " + literal(json.dumps(settings)) + "::jsonb) ON CONFLICT(id) DO UPDATE SET settings=EXCLUDED.settings;"]
        for row in rows:
            record = {k:v for k,v in row.items() if k != 'embedding'}
            statements.append('INSERT INTO chunks VALUES (' + literal(row['chunk_id']) + ', ' +
                literal(json.dumps(record, ensure_ascii=False)) + '::jsonb, ' +
                literal(json.dumps(row['embedding'])) + '::vector) ON CONFLICT(chunk_id) DO UPDATE SET record=EXCLUDED.record, embedding=EXCLUDED.embedding;')
        statements.append('COMMIT;')
        sql('\n'.join(statements))
        print('DB 저장 청크 수:', sql('SELECT count(*) FROM chunks;'))
        print('문서 임베딩 호출: 0회 (JSON에 저장된 벡터 재사용)')
    if not args.query:
        return
    db_settings = json.loads(sql('SELECT settings FROM cache_settings WHERE id=1;'))
    if db_settings != settings or previous.model_digest() != settings['model_digest']:
        raise ValueError('캐시/DB/현재 모델 설정 불일치')
    db_ids = set(sql('SELECT chunk_id FROM chunks;').splitlines())
    if db_ids != {r['chunk_id'] for r in rows}:
        raise ValueError('DB와 JSON의 검색 대상이 다릅니다.')
    q = previous.embed_texts([f'Instruct: {previous.TASK}\nQuery: {args.query}'])[0]
    if previous.model_digest() != settings['model_digest']:
        raise ValueError('질문 임베딩 중 모델 변경')
    value = literal(json.dumps(q)) + '::vector'
    query = f'''SELECT row_to_json(result) FROM (
      SELECT chunk_id, record, 1 - (embedding <=> {value}) AS similarity
      FROM chunks ORDER BY embedding <=> {value} LIMIT {args.top_k}
    ) result;'''
    controls = ('SET LOCAL enable_seqscan=off; SET LOCAL hnsw.ef_search=' + str(args.ef_search) + ';'
                if args.mode == 'hnsw' else
                'SET LOCAL enable_indexscan=off; SET LOCAL enable_bitmapscan=off;')
    plan = json.loads(sql('BEGIN; ' + controls + ' EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + query + ' COMMIT;'))[0]
    def nodes(node):
        yield node
        for child in node.get('Plans', []):
            yield from nodes(child)
    index_names = [n['Index Name'] for n in nodes(plan['Plan']) if 'Index Name' in n]
    used_hnsw = any('hnsw' in name for name in index_names)
    if args.mode == 'hnsw' and not used_hnsw:
        raise ValueError('HNSW 사용이 확인되지 않습니다. 인덱스를 확인하세요.')
    hits = [json.loads(line) for line in sql('BEGIN; ' + controls + query + ' COMMIT;').splitlines()]
    expected = sorted([(previous.cosine_similarity(q,v),r['chunk_id']) for r,v in zip(rows,vectors)],key=lambda x:(-x[0],x[1]))[:args.top_k]
    same = [r['chunk_id'] for r in hits] == [r[1] for r in expected]
    scores = dict((cid,score) for score,cid in expected)
    max_error = max((abs(r['similarity']-scores.get(r['chunk_id'],float('inf'))) for r in hits),default=0)
    overlap = len({h['chunk_id'] for h in hits} & {cid for _, cid in expected})
    print(f'검색 범위: {len(rows)}개 / 모드: {args.mode}')
    print(f'HNSW 실제 사용: {used_hnsw} / 사용 인덱스: {index_names}')
    print(f"실행 계획 측정 DB 시간: {plan['Execution Time']:.3f} ms (임베딩 시간 제외)")
    if args.mode == 'hnsw':
        print(f'HNSW 탐색 설정 ef_search: {args.ef_search}')
    print(f'정확 검색 Top-k와 겹치는 결과: {overlap}/{len(expected)}')
    for rank,hit in enumerate(hits,1):
        r=hit['record']
        print(f"\n[{rank}위] 코사인 유사도: {hit['similarity']:.4f}")
        print('문서:', r.get('title'))
        print('섹션:', ' / '.join(r.get('section_path') or []) or '(본문)')
        print('chunk_id:',hit['chunk_id'])
        print('본문:',previous.single_line(r['raw_text'])[:350])
    print(f'\n동일 질문 벡터로 비교: Python/DB Top-k 순서 일치={same}')
    report={'query':args.query,'count':len(rows),'same_order':same,'max_score_difference':max_error if same else None, 'mode':args.mode, 'used_hnsw':used_hnsw, 'overlap':overlap, 'execution_ms':plan['Execution Time'],
            'results':[{'chunk_id':h['chunk_id'],'title':h['record'].get('title'),'similarity':h['similarity']} for h in hits]}
    (HERE/'last_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if args.mode == 'exact' and (not same or max_error > 1e-5):
        raise ValueError('Python/DB 비교 결과를 확인하세요.')

if __name__ == '__main__':
    main()
