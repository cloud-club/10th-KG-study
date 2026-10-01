"""기존 BM25·pgvector 검색을 재사용하는 RRF 실습. DB 데이터는 변경하지 않는다."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fuse(lists, constant):
    merged = {}
    for name, hits in lists.items():
        seen = set()
        for rank, hit in enumerate(hits, 1):
            cid = hit['chunk_id']
            if cid in seen:
                raise ValueError('검색 결과에 중복 chunk_id')
            seen.add(cid)
            item = merged.setdefault(cid, dict(chunk_id=cid, record=hit['record'],
                                               rrf=0.0, ranks={}))
            item['rrf'] += 1 / (constant + rank)
            item['ranks'][name] = rank
    return sorted(merged.values(), key=lambda h: (-h['rrf'], h['chunk_id']))


def retrieve(query, operator='or', candidates=20, rrf_k=60, mode='exact',
             ef_search=40, track_total_hits=True, cache=None):
    bm = module('bm25', ROOT / 'bm25_lab/search_lab.py')
    pg = module('pg', ROOT / 'pgvector_lab/04_pgvector_search.py')
    cache_path = Path(cache).expanduser() if cache is not None else pg.CACHE
    saved = json.loads(cache_path.read_text())
    settings = json.loads(pg.sql('SELECT settings FROM cache_settings WHERE id=1;'))
    if settings != saved['settings'] or pg.previous.model_digest() != settings['model_digest']:
        raise ValueError('캐시/DB/모델 설정 불일치')
    db_ids = set(pg.sql('SELECT chunk_id FROM chunks;').splitlines())
    es_ids = set()
    after = None
    while True:
        body = {'size': 1000, '_source': False, 'sort': [{'chunk_id': 'asc'}]}
        if after is not None:
            body['search_after'] = after
        page = bm.request('POST', f'/{bm.INDEX}/_search', body)['hits']['hits']
        if not page:
            break
        es_ids.update(h['_id'] for h in page)
        after = page[-1]['sort']
    if db_ids != es_ids or db_ids != {r['chunk_id'] for r in saved['records']}:
        raise ValueError('BM25/DB/캐시 검색 범위 불일치')
    result = bm.request('POST', f'/{bm.INDEX}/_search', {
        'size': candidates, 'track_total_hits': track_total_hits,
        'query': {'match': {'embedding_text': {'query': query, 'operator': operator}}}})
    bm_hits = [dict(chunk_id=h['_source']['chunk_id'], record=h['_source'], score=h['_score'])
               for h in result['hits']['hits']]
    q = pg.previous.embed_texts([f'Instruct: {pg.previous.TASK}\nQuery: {query}'])[0]
    if pg.previous.model_digest() != settings['model_digest']:
        raise ValueError('질문 임베딩 중 모델 변경')
    value = pg.literal(json.dumps(q)) + '::vector'
    statement = f'''SELECT row_to_json(t) FROM (SELECT chunk_id, record,
        1-(embedding <=> {value}) AS score FROM chunks
        ORDER BY embedding <=> {value} LIMIT {candidates}) t;'''
    controls = (f'SET LOCAL enable_seqscan=off; SET LOCAL hnsw.ef_search={ef_search};'
                if mode == 'hnsw' else
                'SET LOCAL enable_indexscan=off; SET LOCAL enable_bitmapscan=off;')
    plan = json.loads(pg.sql('BEGIN; ' + controls +
        ' EXPLAIN (ANALYZE, FORMAT JSON) ' + statement + ' COMMIT;'))[0]
    def nodes(node):
        yield node
        for child in node.get('Plans', []):
            yield from nodes(child)
    indexes = [n['Index Name'] for n in nodes(plan['Plan']) if 'Index Name' in n]
    hnsw_indexes = set(pg.sql("SELECT indexrelid::regclass::text FROM pg_index "
        "JOIN pg_class ON pg_class.oid=indexrelid JOIN pg_am ON pg_am.oid=pg_class.relam "
        "WHERE indrelid='chunks'::regclass AND pg_am.amname='hnsw';").splitlines())
    used_hnsw = bool(hnsw_indexes.intersection(indexes))
    if mode == 'hnsw' and not used_hnsw:
        raise ValueError('HNSW 인덱스 사용이 확인되지 않습니다.')
    vec_hits = [json.loads(line) for line in
                pg.sql('BEGIN; ' + controls + statement + ' COMMIT;').splitlines()]
    lists = {'bm25': bm_hits, 'vector': vec_hits}
    combined = fuse(lists, rrf_k)
    return {'results': combined, 'lists': lists, 'count': len(db_ids),
            'total': result['hits'].get('total', {}).get('value'),
            'used_hnsw': used_hnsw, 'indexes': indexes,
            'db_execution_ms': plan['Execution Time']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', required=True)
    parser.add_argument('--cache', type=Path, help='04에서 적재한 벡터 캐시 파일')
    parser.add_argument('--operator', choices=['or', 'and'], default='or')
    parser.add_argument('--candidates', type=int, default=20)
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--rrf-k', type=int, default=60)
    parser.add_argument('--mode', choices=['exact', 'hnsw'], default='exact')
    parser.add_argument('--ef-search', type=int, default=40)
    args = parser.parse_args()
    if args.ef_search < args.candidates and args.mode == 'hnsw':
        parser.error('ef-search는 candidates 이상으로 지정하세요.')
    if not args.query.strip() or min(args.candidates, args.top_k) < 1 or args.rrf_k < 0:
        parser.error('질문과 양수 후보/출력 수, 0 이상의 rrf-k가 필요합니다.')
    report = retrieve(args.query, args.operator, args.candidates, args.rrf_k,
                      args.mode, args.ef_search, cache=args.cache)
    combined, lists = report['results'], report['lists']
    bm_hits, vec_hits = lists['bm25'], lists['vector']
    print(f"검색 범위: {report['count']} / BM25={args.operator.upper()} / vector={args.mode}")
    print(f"BM25 총 일치={report['total']}, 후보={len(bm_hits)} / 벡터 후보={len(vec_hits)}")
    print('HNSW 사용:', report['used_hnsw'], '/ 인덱스:', report['indexes'])
    for name, hits in lists.items():
        print(f'\n{name} Top-{args.top_k}')
        for rank, hit in enumerate(hits[:args.top_k], 1):
            print(rank, hit['chunk_id'], f"{hit['score']:.4f}", hit['record'].get('title'))
    print('\nRRF 결과 (—는 해당 후보 목록에 없음)')
    for rank, hit in enumerate(combined[:args.top_k], 1):
        r = hit['record']
        print(f"\n{rank}. RRF={hit['rrf']:.6f} BM25순위={hit['ranks'].get('bm25', '—')} 벡터순위={hit['ranks'].get('vector', '—')}")
        print('chunk_id:', hit['chunk_id'])
        print('출처:', r.get('title'), '/', ' / '.join(r.get('section_path') or []))
        print('본문:', r['raw_text'][:500].replace('\n', ' '))


if __name__ == '__main__':
    main()
