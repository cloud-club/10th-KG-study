"""2세대: pgvector 벡터 검색 + HNSW

저장 구조가 1세대와 근본적으로 다르다. 여기엔 '단어'가 저장되지 않는다.
텍스트는 임베딩 시점에 1024개의 실수로 압축되고, 검색은 그 실수 벡터 사이의
코사인 거리 계산이 된다. 그래서 "학교에서"와 "학교"가 같은 걸로 잡히지만,
반대로 "SKU-2847-B" 같은 무의미 식별자는 오히려 놓친다.

인덱스는 HNSW — 정확한 최근접이 아니라 근사(ANN)다. 즉 2세대는 정확도를
속도와 맞바꾼 구조이고, 그 트레이드오프가 m / ef_construction 파라미터다.

사용:
    python src/gen2_pgvector.py index     # 임베딩 + 적재 (첫 실행은 모델 다운로드)
    python src/gen2_pgvector.py schema    # 저장 구조 출력
    python src/gen2_pgvector.py 학교       # 벡터 검색
"""
import json
import sys

import psycopg
from pgvector.psycopg import register_vector

from common import CHUNKS, EMBED_DIM, EMBED_MODEL, PG_DSN, PG_TABLE

DDL = f"""
DROP TABLE IF EXISTS {PG_TABLE};
CREATE TABLE {PG_TABLE} (
    id        text PRIMARY KEY,
    source    text NOT NULL,
    title     text NOT NULL,
    heading   text,
    text      text NOT NULL,
    embedding vector({EMBED_DIM})   -- 본문이 이 1024개 실수로 대체된다
);
"""

# HNSW: 그래프 기반 근사 최근접. m=이웃 수, ef_construction=색인 시 탐색 폭.
# 둘 다 올리면 정확도가 오르고 색인이 느려진다 — 이게 2세대의 핵심 손잡이.
INDEX_DDL = f"""
CREATE INDEX ON {PG_TABLE}
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
"""

_model = None


def embedder():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print(f"임베딩 모델 로딩: {EMBED_MODEL} (첫 실행은 다운로드 때문에 오래 걸린다)")
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def connect():
    conn = psycopg.connect(PG_DSN, autocommit=True)
    # register_vector는 DB에 vector 타입이 이미 있어야 동작한다.
    # 그래서 확장 설치가 먼저다 (순서를 바꾸면 "vector type not found"로 죽는다).
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def index(batch: int = 32) -> None:
    from tqdm import tqdm

    rows = [json.loads(l) for l in CHUNKS.open(encoding="utf-8")]
    model = embedder()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(DDL)
        for i in tqdm(range(0, len(rows), batch), desc="임베딩+적재"):
            part = rows[i:i + batch]
            vecs = model.encode(
                [r["text"] for r in part],
                normalize_embeddings=True,   # 정규화하면 코사인 = 내적
                show_progress_bar=False,
            )
            cur.executemany(
                f"INSERT INTO {PG_TABLE} (id, source, title, heading, text, embedding)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                [(r["id"], r["source"], r["title"], r["heading"], r["text"], v)
                 for r, v in zip(part, vecs)],
            )
        print("HNSW 인덱스 생성 중...")
        cur.execute(INDEX_DDL)
        cur.execute(f"SELECT count(*) FROM {PG_TABLE}")
        print(f"[2세대] 적재 완료: {cur.fetchone()[0]:,}행")


def schema() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {PG_TABLE}")
        n = cur.fetchone()[0]
        cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{PG_TABLE}'))")
        size = cur.fetchone()[0]
        cur.execute(f"SELECT indexdef FROM pg_indexes WHERE tablename = '{PG_TABLE}'")
        idx = [r[0] for r in cur.fetchall()]

    print("[2세대 pgvector] 저장 구조")
    print(f"  테이블      : {PG_TABLE}")
    print(f"  행(청크)    : {n:,}")
    print(f"  크기        : {size}  <- 대부분이 벡터. 1024 x 4B = 청크당 4KB")
    print(f"  저장 단위   : 테이블 한 행 (본문 + vector({EMBED_DIM}))")
    print(f"  임베딩 모델 : {EMBED_MODEL}")
    print("  랭킹        : 코사인 거리 (연산자 <=>)")
    print("  인덱스      :")
    for d in idx:
        print(f"    {d}")


def search(query: str, limit: int = 5):
    vec = embedder().encode([query], normalize_embeddings=True)[0]
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT text, 1 - (embedding <=> %s) AS score FROM {PG_TABLE}"
            " ORDER BY embedding <=> %s LIMIT %s",
            (vec, vec, limit),
        )
        return cur.fetchall()


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "schema"
    if arg == "index":
        index()
    elif arg == "schema":
        schema()
    else:
        print(f'[2세대] "{arg}" — 코사인 유사도 상위 {5}건')
        for text, score in search(arg):
            print(f'  {score:6.3f}  {text.replace(chr(10), " ")[:110]}')


if __name__ == "__main__":
    main()
