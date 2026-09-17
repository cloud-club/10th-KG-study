#!/usr/bin/env python3
"""같은 질문을 0세대 grep / 1세대 BM25(Elasticsearch, nori) / 2세대 벡터(pgvector) 로 던져 나란히 비교한다.

  python src/search.py "부산 여행 숙소"                   # 세 방식 top-5 출력
  python src/search.py "부산 여행 숙소" -k 10 --room 여행모임
  python src/search.py --batch questions.txt --md          # 질문 목록 → 마크다운 비교표 (W2 실습 산출물)

  0세대 grep : messages.text ILIKE '%질문%'  — 문자열이 그대로 들어있는 메시지만, 순위 없음(시간순)
  1세대 BM25 : ES match(text) — 형태소 단위 키워드 일치 + BM25 순위
  2세대 벡터 : 질문 임베딩과 청크 임베딩의 코사인 유사도 순 (HNSW)
"""
from __future__ import annotations

import argparse
import sys

from common import ES_INDEX, EMBED_MODEL, get_es, get_pg, room_filter_sql, vec_literal


def grep_search(cur, q: str, k: int, room: str | None):
    where, params = room_filter_sql(room, "r")
    cur.execute(
        f"""SELECT count(*) FROM messages m JOIN rooms r ON r.id = m.room_id
            WHERE m.text ILIKE %s{where}""", [f"%{q}%"] + params)
    total = cur.fetchone()[0]
    cur.execute(
        f"""SELECT m.id, m.sent_at, mem.name, m.text
            FROM messages m JOIN rooms r ON r.id = m.room_id LEFT JOIN members mem ON mem.id = m.sender_id
            WHERE m.text ILIKE %s{where} ORDER BY m.sent_at LIMIT %s""", [f"%{q}%"] + params + [k])
    return total, cur.fetchall()


def bm25_search(es, q: str, k: int, room: str | None, field: str = "text"):
    body = {"bool": {"must": [{"match": {field: q}}]}}
    if room:
        body["bool"]["filter"] = [{"term": {"room": room}}]
    res = es.search(index=ES_INDEX, query=body, size=k,
                    highlight={"fields": {"text": {"fragment_size": 120, "number_of_fragments": 1}},
                               "pre_tags": ["«"], "post_tags": ["»"]})
    hits = []
    for h in res["hits"]["hits"]:
        src = h["_source"]
        snippet = (h.get("highlight", {}).get("text") or [src["text"].split("\n", 1)[-1][:120]])[0]
        hits.append((src["chunk_id"], h["_score"], src["start_at"][:16], snippet.replace("\n", " ")))
    return hits


def vector_search(cur, qvec: list[float], k: int, room: str | None):
    where, params = room_filter_sql(room, "r")
    lit = vec_literal(qvec)
    cur.execute(
        f"""SELECT c.id, 1 - (e.embedding <=> %s::vector) AS cos, c.start_at, c.text
            FROM chunk_embeddings e JOIN chunks c ON c.id = e.chunk_id JOIN rooms r ON r.id = c.room_id
            WHERE e.model = %s{where}
            ORDER BY e.embedding <=> %s::vector LIMIT %s""",
        [lit, EMBED_MODEL] + params + [lit, k])
    return [(cid, cos, s.strftime("%Y-%m-%d %H:%M"), text.split("\n", 1)[-1][:120].replace("\n", " "))
            for cid, cos, s, text in cur.fetchall()]


def run_one(q: str, k: int, room: str | None, cur, es, embedder):
    total, grep_rows = grep_search(cur, q, k, room)
    bm25 = bm25_search(es, q, k, room)
    vec = vector_search(cur, embedder.embed([q], is_query=True)[0], k, room)
    return total, grep_rows, bm25, vec


def print_one(q, total, grep_rows, bm25, vec):
    print(f"\n{'=' * 78}\nQ: {q}\n{'=' * 78}")
    print(f"\n[0세대 grep] ILIKE '%{q}%' → {total}건 (시간순, 순위 없음)")
    for mid, ts, name, text in grep_rows:
        print(f"  #{mid:<7} {ts:%Y-%m-%d %H:%M} {name or '(system)'}: {' '.join(text.split())[:100]}")
    print(f"\n[1세대 BM25/nori] top-{len(bm25)} 청크")
    for cid, score, ts, snip in bm25:
        print(f"  chunk {cid:<6} score={score:6.2f} {ts}  {snip}")
    print(f"\n[2세대 벡터/pgvector] top-{len(vec)} 청크")
    for cid, cos, ts, snip in vec:
        print(f"  chunk {cid:<6} cos={cos:6.3f}  {ts}  {snip}")
    both = {c for c, *_ in bm25} & {c for c, *_ in vec}
    print(f"\n  BM25 ∩ 벡터 = {len(both)}개 청크 {sorted(both) if both else ''}  ← W3 RRF 융합의 출발점")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--room")
    ap.add_argument("--batch", help="질문이 한 줄씩 들어있는 파일")
    ap.add_argument("--md", action="store_true", help="--batch 결과를 마크다운 표로")
    args = ap.parse_args()
    if not args.query and not args.batch:
        ap.error("질문 또는 --batch 파일이 필요합니다")

    from embed import Embedder  # 질문도 같은 모델로 임베딩
    embedder = Embedder()
    es = get_es()
    with get_pg() as conn, conn.cursor() as cur:
        if args.query:
            print_one(args.query, *run_one(args.query, args.k, args.room, cur, es, embedder))
            return
        questions = [l.strip() for l in open(args.batch, encoding="utf-8") if l.strip() and not l.startswith("#")]
        if args.md:
            print("| 질문 | grep 건수 | BM25 top-1 (score) | 벡터 top-1 (cos) | BM25∩벡터 | 누가 이겼나 |")
            print("|---|---|---|---|---|---|")
        for q in questions:
            total, grep_rows, bm25, vec = run_one(q, args.k, args.room, cur, es, embedder)
            if args.md:
                b = f"#{bm25[0][0]} ({bm25[0][1]:.1f}) {bm25[0][3][:40]}" if bm25 else "-"
                v = f"#{vec[0][0]} ({vec[0][1]:.2f}) {vec[0][3][:40]}" if vec else "-"
                both = len({c for c, *_ in bm25} & {c for c, *_ in vec})
                print(f"| {q} | {total} | {b} | {v} | {both}/{args.k} |  |")
            else:
                print_one(q, total, grep_rows, bm25, vec)


if __name__ == "__main__":
    main()
