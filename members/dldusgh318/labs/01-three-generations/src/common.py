"""세 세대가 공유하는 경로·설정과 청크 로더."""
import json
import os
import re
from functools import lru_cache
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
DATA = LAB / "data"
RAW = DATA / "raw"              # 0세대의 저장소 그 자체: 그냥 파일 더미
PROCESSED = DATA / "processed"
CHUNKS = PROCESSED / "chunks.jsonl"   # 1·2세대의 공통 입력

ES_URL = "http://localhost:9200"
ES_INDEX = "notion-gen1"

PG_DSN = "postgresql://study:study@localhost:5433/study"  # 5432는 로컬 Postgres가 점유
PG_TABLE = "notion_gen2"

# bge-m3: 한국어 성능 좋고 1024차원. 로컬 실행이라 노션 원문이 밖으로 나가지 않는다.
EMBED_MODEL = "BAAI/bge-m3"
EMBED_DIM = 1024

WEEK3_DATA = DATA / "week3"

for d in (RAW, PROCESSED):
    d.mkdir(parents=True, exist_ok=True)


def load_chunks_by_id() -> dict[str, dict]:
    """Oracle context에서 사용할 청크를 ID로 읽는다.

    개인 원문을 로그로 출력하거나 외부로 보내지 않고 로컬 JSONL만 읽는다.
    """
    rows: dict[str, dict] = {}
    path = Path(active_runtime().get('chunks_path', CHUNKS))
    with path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            rows[row["id"]] = row
    return rows


def active_runtime():
    if os.getenv('KG_USE_LEGACY') == '1':
        return {}
    path = PROCESSED / 'active_corpus.json'
    return json.loads(path.read_text()) if path.exists() else {}


def active_vector_table():
    value = active_runtime().get('vector_table', PG_TABLE)
    if not re.fullmatch(r'[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?', value):
        raise ValueError('잘못된 검색 테이블 이름')
    return value


@lru_cache(maxsize=2)
def _runtime_data(config_hash):
    config = json.loads(config_hash)
    corpus = {r['id']:r for r in (json.loads(l) for l in Path(config['chunks_path']).read_text().splitlines() if l.strip())}
    return json.loads(Path(config['aliases_path']).read_text()), corpus


def canonical_search_result(row):
    config = active_runtime()
    if not config:
        return row
    aliases, corpus = _runtime_data(json.dumps(config, sort_keys=True))
    id_ = aliases.get(row['id'], row['id'])
    if id_ not in corpus:
        raise ValueError('검색 결과 ID가 활성 코퍼스에 없음')
    chunk = corpus[id_]
    return {**row, **{k:chunk.get(k,'') for k in ('source','title','heading','text')}, 'id':id_}
