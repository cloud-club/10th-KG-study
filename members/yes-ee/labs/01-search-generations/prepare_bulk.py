"""페이지 JSONL에 Elasticsearch Bulk 등록 지시를 붙인다. 전송은 하지 않는다."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'data/yes-ee/processed/notion-pages-v1'
INDEX = 'yes-ee-notion-pages-v1'


def main():
    documents = [json.loads(line) for line in (OUT / 'documents.jsonl').read_text().splitlines() if line.strip()]
    if not documents or len({doc['id'] for doc in documents}) != len(documents):
        raise SystemExit('문서가 없거나 ID가 중복되었습니다.')
    with (OUT / 'bulk.ndjson').open('w', encoding='utf-8') as file:
        for doc in documents:
            file.write(json.dumps({'index': {'_index': INDEX, '_id': doc['id']}}) + '\n')
            file.write(json.dumps(doc, ensure_ascii=False) + '\n')
    print(f'등록 파일 준비: {len(documents)}개 문서 (서버 전송은 하지 않음)')


if __name__ == '__main__':
    main()
