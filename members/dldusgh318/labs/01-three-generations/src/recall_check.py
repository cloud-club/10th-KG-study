"""HNSW recall 검증 — 못 찾은 게 임베딩 탓인가 인덱스 탓인가.

벡터 검색이 뭔가를 놓쳤을 때 원인은 둘 중 하나다.
  ① 임베딩이 그 의미를 못 잡았다        → 모델 문제
  ② HNSW가 근사 탐색 중에 놓쳤다        → 인덱스 문제

구분하지 않으면 "벡터 검색은 이런 걸 못 잡네요"라는 결론이 통째로 틀릴 수 있다.
구분법은 간단하다. 인덱스를 끄면 완전 탐색(정답)이 되므로 둘을 비교하면 된다.

    python src/recall_check.py            # ef_search 40 / 100 비교
"""
import psycopg
from pgvector.psycopg import register_vector

from common import PG_DSN, PG_TABLE
from gen2_pgvector import embedder
from query import QUESTIONS

K = 10


def topk(cur, vec, exact: bool, ef: int = 40):
    if exact:
        # 인덱스 스캔을 끄면 pgvector는 완전 탐색으로 떨어진다 = 정답(recall 100%)
        cur.execute("SET enable_indexscan = off")
        cur.execute("SET enable_seqscan = on")
    else:
        cur.execute("SET enable_indexscan = on")
        cur.execute(f"SET hnsw.ef_search = {ef}")
    cur.execute(
        f"SELECT id FROM {PG_TABLE} ORDER BY embedding <=> %s LIMIT %s", (vec, K)
    )
    return [r[0] for r in cur.fetchall()]


def main() -> None:
    model = embedder()
    conn = psycopg.connect(PG_DSN, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)

    print(f"HNSW recall@{K}  (완전 탐색 대비 근사 탐색의 일치율)\n")
    print(f"| {'#':<4} | {'쿼리':<22} | ef=40 | ef=100 |")
    print(f"|------|{'-'*24}|-------|--------|")

    tot40 = tot100 = 0
    with conn.cursor() as cur:
        for qid, query, _kind, _note in QUESTIONS:
            vec = model.encode([query], normalize_embeddings=True)[0]
            exact = topk(cur, vec, exact=True)
            r40 = len(set(exact) & set(topk(cur, vec, False, 40))) / len(exact)
            r100 = len(set(exact) & set(topk(cur, vec, False, 100))) / len(exact)
            tot40 += r40
            tot100 += r100
            pad = 22 - sum(2 if ord(c) > 0x1100 else 1 for c in query)
            print(f"| {qid:<4} | {query}{' '*max(pad,0)} | {r40:.2f}  | {r100:.2f}   |")

    n = len(QUESTIONS)
    print(f"\n평균 recall@{K}:  ef=40 → {tot40/n:.3f}   ef=100 → {tot100/n:.3f}")
    print("\n판정 기준: 0.9 이상이면 인덱스는 정상이고, 못 찾은 건 임베딩 탓이다.")
    conn.close()


if __name__ == "__main__":
    main()
