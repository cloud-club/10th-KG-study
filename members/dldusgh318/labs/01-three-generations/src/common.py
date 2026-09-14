"""세 세대가 공유하는 경로·설정과 청크 로더."""
import json
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
    with CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            rows[row["id"]] = row
    return rows
