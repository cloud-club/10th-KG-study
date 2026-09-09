#!/usr/bin/env python3
"""카카오톡 내보내기 txt → 로컬 PostgreSQL (kakao.rooms / kakao.messages) 적재.

레포 루트에서:
    uv run --with 'psycopg[binary]' members/sese2204/labs/01-kakao-ingest/src/ingest.py data/우리동네.txt
    python3 .../ingest.py --dry-run data/*.txt          # 파싱 결과만 확인, DB 접속 안 함

접속 정보: DATABASE_URL 이 있으면 그것, 없으면 POSTGRES_* (.env 와 같은 이름, 기본 kg/kg@localhost:5432/kg).
같은 파일을 다시 넣으면 그 방의 기존 메시지를 지우고 통째로 다시 씁니다 (source_file 기준).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

from kakao_parser import Chat, parse_file

SCHEMA_SQL = Path(__file__).with_name("schema.sql")


def default_db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    user = os.environ.get("POSTGRES_USER", "kg")
    password = os.environ.get("POSTGRES_PASSWORD", "kg")
    db = os.environ.get("POSTGRES_DB", "kg")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@localhost:{port}/{db}"


def summarize(path: Path, chat: Chat) -> str:
    msgs = chat.messages
    if not msgs:
        return f"{path.name}: 메시지 없음 (형식이 카카오톡 모바일 내보내기가 맞는지 확인)"
    kinds = Counter(m.kind for m in msgs)
    kinds_text = ", ".join(f"{k} {n:,}" for k, n in kinds.most_common())
    return (
        f"{path.name}: 방 '{chat.room_name}', 메시지 {len(msgs):,}건, 참여자 {len(chat.senders)}명 "
        f"({', '.join(chat.senders)}), {msgs[0].sent_at:%Y-%m-%d} ~ {msgs[-1].sent_at:%Y-%m-%d}\n"
        f"  종류: {kinds_text}"
    )


def load_chat(conn, source_file: str, chat: Chat) -> int:
    """방 upsert → 기존 메시지 삭제 → COPY. 한 트랜잭션이라 중간에 실패하면 이전 상태 유지."""
    with conn.transaction():
        (room_id,) = conn.execute(
            """
            INSERT INTO kakao.rooms (name, source_file, exported_at, message_count)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (source_file) DO UPDATE
              SET name = EXCLUDED.name, exported_at = EXCLUDED.exported_at,
                  message_count = EXCLUDED.message_count, imported_at = now()
            RETURNING id
            """,
            (chat.room_name, source_file, chat.exported_at, len(chat.messages)),
        ).fetchone()
        conn.execute("DELETE FROM kakao.messages WHERE room_id = %s", (room_id,))
        with conn.cursor().copy(
            "COPY kakao.messages (room_id, seq, line_no, sent_at, sender, kind, content) FROM STDIN"
        ) as copy:
            for m in chat.messages:
                copy.write_row((room_id, m.seq, m.line_no, m.sent_at, m.sender, m.kind, m.content))
    # COPY 직후엔 통계가 없어 플래너가 trgm 인덱스를 안 탈 수 있음. 바로 갱신.
    conn.execute("ANALYZE kakao.messages")
    return len(chat.messages)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path, help="카카오톡 내보내기 txt")
    ap.add_argument("--db", default=default_db_url(), help="postgresql://user:pw@host:port/db")
    ap.add_argument("--dry-run", action="store_true", help="파싱 요약만 출력하고 DB 에는 넣지 않음")
    args = ap.parse_args(argv)

    missing = [f for f in args.files if not f.is_file()]
    if missing:
        ap.error("파일 없음: " + ", ".join(map(str, missing)))

    chats: list[tuple[Path, Chat]] = []
    for path in args.files:
        try:
            chats.append((path, parse_file(path)))
        except UnicodeDecodeError as e:
            print(f"{path}: UTF-8 로 읽을 수 없음 ({e}). 카카오톡 내보내기 원본인지 확인하세요.", file=sys.stderr)
            return 1
        print(summarize(path, chats[-1][1]))

    if args.dry_run:
        return 0

    try:
        import psycopg
    except ImportError:
        print("psycopg 가 없습니다: uv run --with 'psycopg[binary]' ingest.py ... 또는 pip install -r requirements.txt", file=sys.stderr)
        return 1

    try:
        with psycopg.connect(args.db) as conn:
            conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
            for path, chat in chats:
                n = load_chat(conn, path.name, chat)
                print(f"  → kakao.messages 에 {n:,}건 적재 완료")
    except psycopg.OperationalError as e:
        print(f"DB 접속 실패 ({args.db}): {e}\n  docker compose up -d postgres 로 먼저 띄우세요.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
