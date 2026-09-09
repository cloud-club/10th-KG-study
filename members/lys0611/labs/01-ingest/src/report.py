#!/usr/bin/env python3
"""labs README 의 '결과' 절에 붙일 마크다운 통계를 출력한다.

  python src/report.py            # 표준 출력으로 마크다운
  python src/report.py > results.md

원문 텍스트는 한 글자도 출력하지 않는다(건수·길이·토큰 샘플만). 그대로 README 에 붙여도 안전하다.
"""
from __future__ import annotations

from datetime import date

from common import (CHUNK_MAX_CHARS, CHUNK_MAX_MSGS, CHUNK_OVERLAP_MSGS, EMBED_DIM, EMBED_MODEL,
                    EMBED_PROVIDER, ES_INDEX, SESSION_GAP_MIN, get_es, get_pg)

SAMPLE = "부산 여행 숙소 예약했어요"
TYPE_ORDER = ["text", "link", "media", "system", "deleted", "empty"]


def main():
    with get_pg() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT r.name, count(*), min(m.sent_at)::date, max(m.sent_at)::date, count(DISTINCT m.sender_id)
               FROM messages m JOIN rooms r ON r.id = m.room_id GROUP BY r.name ORDER BY r.name""")
        rooms = cur.fetchall()
        cur.execute(
            """SELECT r.name, m.msg_type, count(*) FROM messages m JOIN rooms r ON r.id = m.room_id
               GROUP BY 1, 2""")
        types: dict[str, dict[str, int]] = {}
        for name, t, n in cur.fetchall():
            types.setdefault(name, {})[t] = n
        cur.execute(
            """SELECT r.name, count(*), round(avg(length(c.text))), round(avg(c.n_messages), 1)
               FROM chunks c JOIN rooms r ON r.id = c.room_id GROUP BY 1 ORDER BY 1""")
        chunks = {row[0]: row[1:] for row in cur.fetchall()}
        cur.execute("SELECT model, count(*) FROM chunk_embeddings GROUP BY 1 ORDER BY 1")
        embs = cur.fetchall()
        cur.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'chunk_embeddings' ORDER BY 1")
        idx = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        pgv = (cur.fetchone() or ["?"])[0]
        cur.execute("SHOW server_version")
        pgver = cur.fetchone()[0]

    es = get_es()
    es_ver = es.info()["version"]["number"]
    es_docs = es.count(index=ES_INDEX)["count"]
    plugins = [f"{p.get('component')} {p.get('version')}" for p in es.cat.plugins(format="json")]
    tokens = [t["token"] for t in es.indices.analyze(index=ES_INDEX, analyzer="korean", text=SAMPLE)["tokens"]]

    print(f"### 적재 결과 ({date.today().isoformat()}, `src/report.py` 출력)\n")
    print("| 방 | 메시지 | 기간 | 발신자 | 청크 | 청크 평균 글자 | 청크당 메시지 |")
    print("|---|---|---|---|---|---|---|")
    for name, n, d0, d1, senders in rooms:
        c = chunks.get(name, ("-", "-", "-"))
        print(f"| {name} | {n:,} | {d0} ~ {d1} | {senders} | {c[0]:,} | {c[1]} | {c[2]} |"
              if c[0] != "-" else f"| {name} | {n:,} | {d0} ~ {d1} | {senders} | - | - | - |")
    print()
    print("| 방 | " + " | ".join(TYPE_ORDER) + " |")
    print("|---|" + "---|" * len(TYPE_ORDER))
    for name, *_ in rooms:
        row = types.get(name, {})
        print(f"| {name} | " + " | ".join(f"{row.get(t, 0):,}" for t in TYPE_ORDER) + " |")
    print()
    print(f"- Postgres {pgver} · pgvector {pgv} · 임베딩 `{EMBED_MODEL}` ({EMBED_PROVIDER}, {EMBED_DIM}차원)")
    for model, n in embs:
        print(f"  - `chunk_embeddings` {model}: {n:,}행 · 인덱스 {', '.join(idx) or '없음'}")
    print(f"- Elasticsearch {es_ver} · 플러그인 {', '.join(plugins) or '없음'} · `{ES_INDEX}` {es_docs:,}건")
    print(f"  - `korean` analyzer 토큰 예: `{SAMPLE}` → {tokens}")
    print(f"- 청킹: 세션 간격 {SESSION_GAP_MIN}분 · 최대 {CHUNK_MAX_MSGS}건/{CHUNK_MAX_CHARS}자 · 겹침 {CHUNK_OVERLAP_MSGS}건")


if __name__ == "__main__":
    main()
