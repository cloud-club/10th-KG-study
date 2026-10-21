"""개인 매핑 파일로 페이지의 고객사 이름을 치환하고 Elasticsearch에 반영한다.

원본 Markdown은 변경하지 않는다. 매핑 파일은 git에서 제외된 data/ 아래에 보관한다.
"""
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'data/yes-ee/processed/notion-pages-v1'
INDEX = 'yes-ee-notion-pages-v1'


def request(path, data, content_type='application/json'):
    req = Request('http://localhost:9200/' + path, data=data,
                  headers={'Content-Type': content_type}, method='POST')
    with urlopen(req, timeout=60) as response:
        return json.load(response)


def main():
    mapping = json.loads((ROOT / 'data/yes-ee/customer-pseudonyms.json').read_text())
    variants = {}
    for name, replacement in mapping.items():
        for form in ('NFC', 'NFD'):
            normalized = unicodedata.normalize(form, name)
            variants[normalized] = replacement
            variants[quote(normalized, safe='')] = replacement
    pattern = re.compile('|'.join(re.escape(s) for s in sorted(variants, key=len, reverse=True)))

    def clean(text):
        return pattern.sub(lambda match: variants[match.group()], unicodedata.normalize('NFC', text))

    result = request(INDEX + '/_search', b'{"size":100,"query":{"match_all":{}}}')
    hits = result['hits']['hits']
    if result['hits']['total']['relation'] != 'eq' or result['hits']['total']['value'] != len(hits):
        raise SystemExit('문서를 모두 읽지 못해 중단합니다.')
    if not hits:
        raise SystemExit('등록된 문서가 없습니다.')
    documents, lines = [], []
    for hit in hits:
        doc = {key: clean(value) if isinstance(value, str) else value
               for key, value in hit['_source'].items()}
        doc['source_path'] = f"notion/{hit['_id']}.md"
        documents.append(doc)
        lines.extend([json.dumps({'index': {'_index': INDEX, '_id': hit['_id']}}),
                      json.dumps(doc, ensure_ascii=False)])
    payload = ('\n'.join(lines) + '\n').encode()
    # 로컬 적재 파일에도 반영하여 재등록 시 기존 이름이 돌아오지 않도록 한다.
    (OUT / 'documents.jsonl').write_text(''.join(json.dumps(doc, ensure_ascii=False) + '\n'
                                               for doc in documents), encoding='utf-8')
    (OUT / 'bulk.ndjson').write_bytes(payload)
    response = request('_bulk?refresh=wait_for', payload, 'application/x-ndjson')
    if response.get('errors'):
        raise SystemExit('일부 문서 갱신 실패. 응답의 항목별 오류를 확인해야 합니다.')
    check = request(INDEX + '/_search', b'{"size":100,"query":{"match_all":{}}}')
    for hit in check['hits']['hits']:
        for value in hit['_source'].values():
            if isinstance(value, str) and pattern.search(value):
                raise SystemExit('원래 이름이 남아 있습니다.')
    print(f"고객사 이름 치환 완료: {len(documents)}개 문서, 원래 이름 잔존 없음")


if __name__ == '__main__':
    main()
