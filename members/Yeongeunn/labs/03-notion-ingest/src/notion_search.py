"""Notion Markdown -> local PostgreSQL / Elasticsearch nori BM25.

Standard library only. Run from the study repository root.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata
from urllib.request import Request, urlopen
from urllib.error import HTTPError

INDEX = 'yeongeunn-notion-v1'
TABLE = 'yeongeunn_notion.chunks'


def parse(root):
    chunks = []
    for path in sorted(root.rglob('*.md')):
        source = unicodedata.normalize('NFC', path.relative_to(root).as_posix())
        raw = unicodedata.normalize('NFC', path.read_text(encoding='utf-8-sig'))
        title = next((s[2:].strip() for s in raw.splitlines() if s.startswith('# ')), path.stem)
        text = re.sub(r'!\[[^\]]*\]\([^\n]*?\)', '', raw)
        text = re.sub(r'\[([^\]]+)\]\([^\n]*?\)', r'\1', text).strip()
        page_id = hashlib.sha256(source.encode()).hexdigest()[:20]
        for start in range(0, len(text), 1000):
            chunks.append(dict(id=f'{page_id}:{start}', page_id=page_id, title=title,
                               source=source, start=start, content=text[start:start+1200]))
            if start + 1200 >= len(text):
                break
    return chunks


def pg(sql):
    result = subprocess.run(
        ['docker', 'compose', 'exec', '-T', 'postgres', 'sh', '-c',
         'exec psql -X -q -A -t -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'],
        input=sql, text=True, capture_output=True, encoding='utf-8')
    if result.returncode:
        # Do not dump SQL or document text on error.
        raise RuntimeError('PostgreSQL command failed. Check docker compose ps and DB permissions.')
    return result.stdout.strip()


def sql_text(value):
    return "'" + value.replace("'", "''") + "'"


def es(base, method, endpoint, body=None, ndjson=False):
    payload = body.encode() if ndjson else (json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
    request = Request(base + endpoint, data=payload, method=method,
                      headers={'Content-Type': 'application/x-ndjson' if ndjson else 'application/json'})
    with urlopen(request, timeout=90) as response:
        return json.load(response)


def ingest(chunks, base):
    # JSON goes through a SQL string with standard-conforming escaping, not shell interpolation.
    payload = sql_text(json.dumps(chunks, ensure_ascii=False))
    pg("SET standard_conforming_strings=on; BEGIN; CREATE SCHEMA IF NOT EXISTS yeongeunn_notion; "
       f"CREATE TABLE IF NOT EXISTS {TABLE} (id text PRIMARY KEY, page_id text NOT NULL, "
       "title text NOT NULL, source text NOT NULL, start integer NOT NULL, content text NOT NULL); "
       f"INSERT INTO {TABLE} SELECT * FROM jsonb_to_recordset({payload}::jsonb) "
       "AS x(id text,page_id text,title text,source text,start integer,content text) "
       "ON CONFLICT(id) DO UPDATE SET title=EXCLUDED.title, source=EXCLUDED.source, "
       "start=EXCLUDED.start, content=EXCLUDED.content, page_id=EXCLUDED.page_id; COMMIT;")
    print('PostgreSQL 적재 완료', flush=True)
    try:
        es(base, 'GET', '/' + INDEX)
    except HTTPError as error:
        if error.code != 404:
            raise
        es(base, 'PUT', '/' + INDEX, {
            'settings': {'number_of_shards': 1, 'number_of_replicas': 0},
            'mappings': {'dynamic': 'strict', 'properties': {
                'id': {'type': 'keyword'}, 'page_id': {'type': 'keyword'},
                'source': {'type': 'keyword', 'index': False}, 'start': {'type': 'integer'},
                'title': {'type': 'text', 'analyzer': 'nori', 'similarity': 'BM25'},
                'content': {'type': 'text', 'analyzer': 'nori', 'similarity': 'BM25'}}}})
    for start in range(0, len(chunks), 200):
        lines = []
        for chunk in chunks[start:start+200]:
            lines.extend([json.dumps({'index': {'_id': chunk['id']}}), json.dumps(chunk, ensure_ascii=False)])
        result = es(base, 'POST', '/' + INDEX + '/_bulk', '\n'.join(lines) + '\n', ndjson=True)
        if result.get('errors'):
            failed = sum(1 for x in result['items'] if x['index'].get('error'))
            raise RuntimeError(f'Elasticsearch bulk failed for {failed} items. Partial ingest; rerun after fixing.')
    es(base, 'POST', '/' + INDEX + '/_refresh')
    counts(base)


def counts(base):
    print('PostgreSQL 청크 수:', pg(f'SELECT count(*) FROM {TABLE};'))
    print('Elasticsearch 청크 수:', es(base, 'GET', '/' + INDEX + '/_count')['count'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'ingest', 'count', 'search'])
    parser.add_argument('--input', type=Path, default=Path('data/Yeongeunn/raw/Erumpay_notion'))
    parser.add_argument('--output', type=Path, default=Path('data/Yeongeunn/processed/notion-chunks.jsonl'))
    parser.add_argument('--es-url', default='http://127.0.0.1:9200')
    parser.add_argument('--query')
    args = parser.parse_args()
    # This lab deliberately sends source documents only to a loopback endpoint.
    from urllib.parse import urlparse
    if urlparse(args.es_url).hostname not in ('localhost', '127.0.0.1', '::1'):
        parser.error('--es-url must point to local Elasticsearch')
    if args.action in ('prepare', 'ingest'):
        if not args.input.is_dir():
            parser.error(f'Input folder does not exist: {args.input}')
        chunks = parse(args.input)
        if not chunks:
            parser.error('No Markdown content found')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(''.join(json.dumps(c, ensure_ascii=False)+'\n' for c in chunks), encoding='utf-8')
        print(f'문서 {len({c["page_id"] for c in chunks})}개 / 청크 {len(chunks)}개', flush=True)
        print(f'가공 데이터: {args.output}', flush=True)
        if args.action == 'ingest':
            ingest(chunks, args.es_url)
    elif args.action == 'count':
        counts(args.es_url)
    else:
        if not args.query:
            parser.error('search requires --query')
        response = es(args.es_url, 'POST', '/' + INDEX + '/_search', {
            'size': 5, 'query': {'multi_match': {'query': args.query, 'fields': ['title', 'content']}}})
        for rank, hit in enumerate(response['hits']['hits'], 1):
            doc = hit['_source']
            print(f'[{rank}] {doc["title"]} | score={hit["_score"]:.3f} | {hit["_id"]}')
            print(doc['source'])
            print(doc['content'][:500], '\n')
        if not response['hits']['hits']:
            print('검색 결과 없음')


if __name__ == '__main__':
    main()
