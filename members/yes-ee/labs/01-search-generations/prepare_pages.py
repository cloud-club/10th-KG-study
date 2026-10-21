"""청킹 없이 Markdown 파일 하나를 검색 문서 하나로 변환한다. 외부 통신 없음."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RAW = ROOT / 'data/yes-ee/raw'
OUT = ROOT / 'data/yes-ee/processed/notion-pages-v1'


def main():
    documents = []
    for path in sorted(RAW.rglob('*.md')):
        text = unicodedata.normalize('NFC', path.read_text(encoding='utf-8-sig'))
        heading = re.search(r'^#\s+(.+)$', text, re.M)
        source_path = path.relative_to(ROOT).as_posix()
        notion_id = re.search(r'([0-9a-fA-F]{32})$', path.stem)
        documents.append({
            'id': notion_id.group(1).lower() if notion_id else hashlib.sha256(source_path.encode()).hexdigest(),
            'title': heading.group(1).strip() if heading else unicodedata.normalize('NFC', path.stem),
            'body': text,
            'source_path': source_path,
        })
    if not documents:
        raise SystemExit('Markdown 파일이 없습니다.')
    if len({doc['id'] for doc in documents}) != len(documents):
        raise SystemExit('같은 페이지 ID의 파일이 여러 개입니다. 원본 중복을 확인하세요.')
    OUT.mkdir(parents=True, exist_ok=False)
    # 제목을 포함한 Markdown 본문을 보존한다. NFC 외에는 정제하지 않는다.
    with (OUT / 'documents.jsonl').open('w', encoding='utf-8') as file:
        for doc in documents:
            file.write(json.dumps(doc, ensure_ascii=False) + '\n')
    print(f'Markdown {len(documents)}개 → JSON 문서 {len(documents)}개 (청킹 없음)')
    print(OUT.relative_to(ROOT) / 'documents.jsonl')


if __name__ == '__main__':
    main()
