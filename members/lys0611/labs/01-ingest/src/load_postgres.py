#!/usr/bin/env python3
"""가명화된 JSONL을 Postgres에 적재하고 청크를 만든다.

  python src/load_postgres.py data/interim/여행모임.masked.jsonl --room 여행모임
  python src/load_postgres.py ... --rebuild-chunks   # 청킹 파라미터를 바꿨을 때 (임베딩도 함께 삭제됨)

테이블
  rooms     방
  members   방별 발신자(가명)
  messages  원문 메시지 1건 1행  ← "정본". grep 세대 검색(ILIKE)은 여기서
  chunks    검색 단위 대화 조각   ← 임베딩(pgvector)과 ES 인덱스는 이 테이블을 본다
멱등성: (room_id, seq) / content_hash 유니크 → 같은 파일을 다시 넣어도 중복되지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from chunking import build_chunks
from common import (CHUNK_MAX_CHARS, CHUNK_MAX_MSGS, CHUNK_OVERLAP_MSGS, SESSION_GAP_MIN, get_pg)

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS rooms (
  id            SERIAL PRIMARY KEY,
  name          TEXT UNIQUE NOT NULL,
  source_format TEXT,
  source_files  TEXT[],
  exported_at   TEXT,
  loaded_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS members (
  id      SERIAL PRIMARY KEY,
  room_id INT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  name    TEXT NOT NULL,
  UNIQUE (room_id, name)
);

CREATE TABLE IF NOT EXISTS messages (
  id          BIGSERIAL PRIMARY KEY,
  room_id     INT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  seq         INT NOT NULL,
  sent_at     TIMESTAMP NOT NULL,
  sender_id   INT REFERENCES members(id),
  msg_type    TEXT NOT NULL,
  text        TEXT NOT NULL,
  source_line INT,
  UNIQUE (room_id, seq)
);
CREATE INDEX IF NOT EXISTS messages_room_time ON messages (room_id, sent_at);
-- ILIKE '%단어%' 를 빠르게: pg_trgm GIN 인덱스 (grep 세대 실습용)
CREATE INDEX IF NOT EXISTS messages_text_trgm ON messages USING gin (text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS chunks (
  id           BIGSERIAL PRIMARY KEY,
  room_id      INT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  chunk_index  INT NOT NULL,
  start_seq    INT NOT NULL,
  end_seq      INT NOT NULL,
  start_at     TIMESTAMP NOT NULL,
  end_at       TIMESTAMP NOT NULL,
  n_messages   INT NOT NULL,
  participants TEXT[] NOT NULL,
  text         TEXT NOT NULL,
  content_hash TEXT NOT NULL UNIQUE,
  UNIQUE (room_id, chunk_index)
);
"""


def load_jsonl(path: str) -> list[dict]:
    msgs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    for m in msgs:
        m["sent_at"] = datetime.fromisoformat(m["sent_at"])
    return msgs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inp", help="pseudonymize.py 가 만든 *.masked.jsonl")
    ap.add_argument("--room", required=True)
    ap.add_argument("--rebuild-chunks", action="store_true", help="기존 청크(+임베딩) 삭제 후 다시 청킹")
    args = ap.parse_args()

    msgs = load_jsonl(args.inp)
    meta_path = Path(args.inp + ".meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    with get_pg() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)

        # 1) room
        cur.execute(
            """INSERT INTO rooms (name, source_format, source_files, exported_at)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (name) DO UPDATE SET source_format = EXCLUDED.source_format,
                   source_files = EXCLUDED.source_files, exported_at = EXCLUDED.exported_at,
                   loaded_at = now()
               RETURNING id""",
            (args.room, ",".join(meta.get("formats", [])) or None, meta.get("files") or None, meta.get("saved_at")),
        )
        room_id = cur.fetchone()[0]

        # 2) members
        names = sorted({m["sender"] for m in msgs if m.get("sender")})
        cur.executemany("INSERT INTO members (room_id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        [(room_id, n) for n in names])
        cur.execute("SELECT name, id FROM members WHERE room_id = %s", (room_id,))
        member_id = dict(cur.fetchall())

        # 3) messages
        rows = [(room_id, m["seq"], m["sent_at"], member_id.get(m.get("sender")), m["msg_type"],
                 m.get("text", ""), m.get("line_no")) for m in msgs]
        cur.executemany(
            """INSERT INTO messages (room_id, seq, sent_at, sender_id, msg_type, text, source_line)
               VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (room_id, seq) DO NOTHING""",
            rows,
        )
        cur.execute("SELECT count(*) FROM messages WHERE room_id = %s", (room_id,))
        n_msgs = cur.fetchone()[0]
        conn.commit()
        print(f"[pg] room={args.room!r} (id={room_id}) members={len(names)} messages={n_msgs:,}", file=sys.stderr)

        # 4) chunks
        cur.execute("SELECT count(*) FROM chunks WHERE room_id = %s", (room_id,))
        existing = cur.fetchone()[0]
        if existing and not args.rebuild_chunks:
            print(f"[pg] chunks 이미 {existing:,}개 존재 → 건너뜀 (다시 만들려면 --rebuild-chunks)", file=sys.stderr)
            return
        if existing:
            cur.execute("DELETE FROM chunks WHERE room_id = %s", (room_id,))  # chunk_embeddings 는 CASCADE 삭제

        cur.execute(
            """SELECT m.seq, m.sent_at, mem.name, m.msg_type, m.text
               FROM messages m LEFT JOIN members mem ON mem.id = m.sender_id
               WHERE m.room_id = %s ORDER BY m.seq""",
            (room_id,),
        )
        db_msgs = [dict(seq=r[0], sent_at=r[1], sender=r[2], msg_type=r[3], text=r[4]) for r in cur.fetchall()]
        chunks = build_chunks(db_msgs, args.room, SESSION_GAP_MIN, CHUNK_MAX_MSGS, CHUNK_MAX_CHARS, CHUNK_OVERLAP_MSGS)
        cur.executemany(
            """INSERT INTO chunks (room_id, chunk_index, start_seq, end_seq, start_at, end_at, n_messages,
                                   participants, text, content_hash)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (content_hash) DO NOTHING""",
            [(room_id, c["chunk_index"], c["start_seq"], c["end_seq"], c["start_at"], c["end_at"],
              c["n_messages"], c["participants"], c["text"], c["content_hash"]) for c in chunks],
        )
        conn.commit()
        avg = sum(len(c["text"]) for c in chunks) / max(len(chunks), 1)
        print(f"[pg] chunks={len(chunks):,} (평균 {avg:.0f}자, gap={SESSION_GAP_MIN}분, "
              f"max_msgs={CHUNK_MAX_MSGS}, max_chars={CHUNK_MAX_CHARS}, overlap={CHUNK_OVERLAP_MSGS})", file=sys.stderr)
        if chunks:
            print("  샘플 청크:\n    " + chunks[len(chunks) // 2]["text"][:300].replace("\n", "\n    "), file=sys.stderr)


if __name__ == "__main__":
    main()
