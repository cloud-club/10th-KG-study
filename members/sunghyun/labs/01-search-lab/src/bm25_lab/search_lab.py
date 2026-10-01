#!/usr/bin/env python3
"""청크 JSONL로 문자열 검색과 Elasticsearch BM25를 비교한다."""
import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = 'http://127.0.0.1:19200'
INDEX = 'rag-chunks-v1'
INPUT = Path(__file__).resolve().parents[1] / 'outputs/chunked_documents_v1.jsonl'


def request(method, path, body=None, ndjson=False):
    data = body.encode() if ndjson else (json.dumps(body).encode() if body is not None else None)
    req = Request(BASE + path, data=data, method=method,
                  headers={'Content-Type': 'application/x-ndjson' if ndjson else 'application/json'})
    with urlopen(req, timeout=90) as response:
        return json.load(response)


def chunks():
    return [json.loads(line) for line in INPUT.read_text().splitlines() if line.strip()]


def load():
    rows = chunks()
    # 기존 인덱스는 수정하지 않는다. 같은 chunk_id로 재적재해 중복을 피한다.
    try:
        request('GET', '/' + INDEX)
    except HTTPError as exc:
        if exc.code != 404:
            raise
        request('PUT', '/' + INDEX, {
            'settings': {'number_of_shards': 1, 'number_of_replicas': 0,
                         'analysis': {'analyzer': {'ko': {'type': 'nori', 'decompound_mode': 'mixed'}}}},
            'mappings': {'dynamic': False, 'properties': {
                'chunk_id': {'type': 'keyword'}, 'document_id': {'type': 'keyword'},
                'embedding_text': {'type': 'text', 'analyzer': 'ko', 'similarity': 'BM25'},
                'raw_text': {'type': 'text', 'index': False},
                'title': {'type': 'keyword'}, 'document_path': {'type': 'keyword'},
                'section_path': {'type': 'keyword'}, 'url_id': {'type': 'keyword'}
            }}
        })
    for offset in range(0, len(rows), 200):
        payload = []
        for row in rows[offset:offset + 200]:
            payload.extend([json.dumps({'index': {'_index': INDEX, '_id': row['chunk_id']}}),
                            json.dumps(row, ensure_ascii=False)])
        result = request('POST', '/_bulk', '\n'.join(payload) + '\n', ndjson=True)
        if result['errors']:
            errors = [item for item in result['items'] if item['index'].get('error')]
            raise ValueError(f'적재 오류: {errors[:1]}')
    request('POST', f'/{INDEX}/_refresh')
    count = request('GET', f'/{INDEX}/_count')['count']
    print(f'입력 {len(rows)}개 / Elasticsearch 저장 {count}개')
    if count != len(rows):
        raise ValueError('입력과 저장 개수가 다릅니다. 기존 인덱스에 다른 데이터가 있는지 확인하세요.')


def show(rows):
    for n, (score, row) in enumerate(rows, 1):
        print(f"\n{n}. {row.get('title')} | 점수: {score}")
        print('경로:', ' / '.join(row.get('document_path') or []))
        print('섹션:', ' / '.join(row.get('section_path') or []))
        print('chunk_id:', row['chunk_id'])
        print(row['raw_text'][:350].replace('\n', ' '))


def main():
    global INPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['load', 'grep', 'bm25', 'analyze', 'explain'])
    parser.add_argument('query', nargs='?', default='')
    parser.add_argument('--top', type=int, default=5)
    parser.add_argument('--input', type=Path, default=INPUT)
    parser.add_argument('--operator', choices=['or', 'and'], default='and')
    parser.add_argument('--id', help='explain으로 점수를 설명할 chunk_id')
    args = parser.parse_args()
    INPUT = args.input
    if args.mode == 'load':
        load()
        return
    if not args.query.strip():
        parser.error('검색 문장을 입력하세요.')
    if args.top < 1:
        parser.error('--top은 1 이상이어야 합니다.')
    if args.mode == 'grep':
        found = [row for row in chunks() if args.query in row['embedding_text']]
        print(f'문자열 그대로 포함: {len(found)}개 (관련도 순위 없이 파일 순서)')
        show([('없음', row) for row in found[:args.top]])
    elif args.mode == 'analyze':
        result = request('POST', f'/{INDEX}/_analyze', {'analyzer': 'ko', 'text': args.query})
        print('Nori 토큰:', ' | '.join(t['token'] for t in result['tokens']))
    elif args.mode == 'explain':
        if not args.id:
            parser.error('explain에는 --id가 필요합니다.')
        result = request('POST', f'/{INDEX}/_explain/{args.id}',
                         {'query': {'match': {'embedding_text': {'query': args.query, 'operator': args.operator}}}})
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = request('POST', f'/{INDEX}/_search', {
            'size': args.top, 'track_total_hits': True,
            'query': {'match': {'embedding_text': {'query': args.query, 'operator': args.operator}}}})
        print(f"BM25 일치: {result['hits']['total']['value']}개 (점수 내림차순, 단어 {args.operator.upper()} 검색)")
        show([(hit['_score'], hit['_source']) for hit in result['hits']['hits']])


if __name__ == '__main__':
    try:
        main()
    except (HTTPError, URLError, OSError, ValueError, KeyError) as exc:
        print(f'오류: {exc}', file=sys.stderr)
        sys.exit(1)
