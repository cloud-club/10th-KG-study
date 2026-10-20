#!/usr/bin/env python3
"""kakao.messages (text) → 대화 청크 → 로컬 임베딩 → kakao.chunks (pgvector + pg_trgm).

레포 루트에서:
    set -a; . ./.env; set +a
    uv run --with 'sentence-transformers>=3' --with 'psycopg[binary]' \
        members/sese2204/labs/02-kakao-chunk-embed/src/embed.py

기본 모델은 jhgan/ko-sroberta-multitask (한국어 SBERT, 768차원, 입력 128토큰). 로컬에서 돌아가므로
대화가 밖으로 나가지 않습니다. --max-chars 를 안 주면 모델 입력 길이에 맞춰 자동(1.5자/토큰)으로 잡습니다.
같은 방을 다시 돌리면 그 방의 청크를 지우고 다시 씁니다. 다른 차원의 모델로 바꾸려면 --recreate.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from chunker import ChunkParams, MessageRow, chunk_messages

DEFAULT_MODEL = "jhgan/ko-sroberta-multitask"
CHARS_PER_TOKEN = 1.3  # 한국어 채팅 실측 평균 1.6 이지만 ㅋㅋㅋ·이모지·영어가 섞이면 낮아져서 보수적으로


def default_db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    return "postgresql://{u}:{p}@localhost:{port}/{db}".format(
        u=os.environ.get("POSTGRES_USER", "kg"), p=os.environ.get("POSTGRES_PASSWORD", "kg"),
        port=os.environ.get("POSTGRES_PORT", "5432"), db=os.environ.get("POSTGRES_DB", "kg"),
    )


def chunks_ddl(dim: int) -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS kakao.chunks (
      id            bigserial PRIMARY KEY,
      room_id       integer   NOT NULL REFERENCES kakao.rooms(id) ON DELETE CASCADE,
      chunk_idx     integer   NOT NULL,          -- 방 안 순서 (0부터)
      start_seq     integer   NOT NULL,          -- kakao.messages.seq 범위
      end_seq       integer   NOT NULL,
      started_at    timestamp NOT NULL,
      ended_at      timestamp NOT NULL,
      message_count integer   NOT NULL,
      text          text      NOT NULL,          -- "이름: 내용" 줄들
      model         text      NOT NULL,          -- 임베딩 모델 이름
      embedding     vector({dim}) NOT NULL,      -- 정규화됨 → <=> 코사인 거리
      UNIQUE (room_id, chunk_idx)
    )"""


INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS chunks_room_started_idx ON kakao.chunks (room_id, started_at)",
    "CREATE INDEX IF NOT EXISTS chunks_text_trgm_idx ON kakao.chunks USING gin (text gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx ON kakao.chunks USING hnsw (embedding vector_cosine_ops)",
)


def existing_embedding_type(conn) -> str | None:
    row = conn.execute(
        """SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a
           JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'kakao' AND c.relname = 'chunks' AND a.attname = 'embedding'"""
    ).fetchone()
    return row[0] if row else None


def ensure_table(conn, dim: int, recreate: bool) -> None:
    current = existing_embedding_type(conn)
    if current is not None and recreate:
        conn.execute("DROP TABLE kakao.chunks")
        current = None
    if current is not None and current != f"vector({dim})":
        sys.exit(f"kakao.chunks.embedding 이 {current} 인데 모델 차원은 {dim} 입니다. 모델을 맞추거나 --recreate 로 다시 만드세요.")
    conn.execute(chunks_ddl(dim))


def to_pgvector(vec) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in vec) + "]"


def fetch_rooms(conn, room_filter: str | None):
    sql = "SELECT id, name, source_file FROM kakao.rooms"
    if room_filter:
        return conn.execute(sql + " WHERE name = %s OR source_file = %s ORDER BY id", (room_filter, room_filter)).fetchall()
    return conn.execute(sql + " ORDER BY id").fetchall()


def fetch_text_rows(conn, room_id: int) -> list[MessageRow]:
    cur = conn.execute(
        "SELECT seq, sent_at, sender, content FROM kakao.messages "
        "WHERE room_id = %s AND kind = 'text' AND sender IS NOT NULL ORDER BY seq",
        (room_id,),
    )
    return [MessageRow(*r) for r in cur]


def count_truncated(model, texts: list[str]) -> int:
    lengths = [len(ids) for ids in model.tokenizer(texts, truncation=False)["input_ids"]]
    return sum(n > model.max_seq_length for n in lengths)


def load_room(conn, model, model_name: str, room, params: ChunkParams, batch_size: int) -> dict:
    room_id, name, _ = room
    rows = fetch_text_rows(conn, room_id)
    chunks = chunk_messages(rows, params)
    if not chunks:
        return {"room": name, "messages": len(rows), "chunks": 0}
    texts = [c.text for c in chunks]
    t0 = time.time()
    vectors = model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    encode_s = time.time() - t0
    with conn.transaction():
        conn.execute("DELETE FROM kakao.chunks WHERE room_id = %s", (room_id,))
        with conn.cursor().copy(
            "COPY kakao.chunks (room_id, chunk_idx, start_seq, end_seq, started_at, ended_at, message_count, text, model, embedding) FROM STDIN"
        ) as copy:
            for c, v in zip(chunks, vectors):
                copy.write_row((room_id, c.chunk_idx, c.start_seq, c.end_seq, c.started_at, c.ended_at,
                                c.message_count, c.text, model_name, to_pgvector(v)))
    return {
        "room": name, "messages": len(rows), "chunks": len(chunks),
        "avg_messages": len(rows) / len(chunks), "avg_chars": sum(map(len, texts)) / len(texts),
        "truncated": count_truncated(model, texts), "encode_s": encode_s,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=default_db_url())
    ap.add_argument("--model", default=DEFAULT_MODEL, help="sentence-transformers 모델 이름 또는 경로")
    ap.add_argument("--device", default=None, help="mps / cuda / cpu (기본: 자동)")
    ap.add_argument("--room", default=None, help="방 이름 또는 파일명. 기본: 모든 방")
    ap.add_argument("--gap-minutes", type=float, default=30)
    ap.add_argument("--max-chars", type=int, default=None, help="기본: 모델 max_seq_length × 1.5")
    ap.add_argument("--max-messages", type=int, default=60)
    ap.add_argument("--min-chars", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--recreate", action="store_true", help="kakao.chunks 를 지우고 다시 만듦 (모델 차원이 바뀔 때)")
    args = ap.parse_args(argv)

    try:
        import psycopg
        import transformers
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        print(f"의존성 없음 ({e}). uv run --with 'sentence-transformers>=3' --with 'psycopg[binary]' embed.py ...", file=sys.stderr)
        return 1
    transformers.logging.set_verbosity_error()

    t0 = time.time()
    model = SentenceTransformer(args.model, device=args.device)
    get_dim = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension  # st<6 호환
    dim = get_dim()
    max_chars = args.max_chars or int(model.max_seq_length * CHARS_PER_TOKEN)
    params = ChunkParams(gap_minutes=args.gap_minutes, max_chars=max_chars,
                         max_messages=args.max_messages, min_chars=args.min_chars)
    print(f"모델 {args.model}: {dim}차원, 입력 {model.max_seq_length}토큰, device={model.device} ({time.time() - t0:.1f}s)")
    print(f"청킹: 간격 {params.gap_minutes:g}분 / 최대 {params.max_chars}자 / 최대 {params.max_messages}개 / 최소 {params.min_chars}자")

    try:
        with psycopg.connect(args.db) as conn:
            ensure_table(conn, dim, args.recreate)
            rooms = fetch_rooms(conn, args.room)
            if not rooms:
                print("kakao.rooms 가 비어 있습니다. 01-kakao-ingest 먼저 실행하세요.", file=sys.stderr)
                return 1
            for room in rooms:
                s = load_room(conn, model, args.model, room, params, args.batch_size)
                if s["chunks"] == 0:
                    print(f"  {s['room']}: 텍스트 메시지 {s['messages']:,}건, 청크 없음")
                    continue
                print(f"  {s['room']}: 텍스트 {s['messages']:,}건 → 청크 {s['chunks']:,}개 "
                      f"(평균 {s['avg_messages']:.1f}개 / {s['avg_chars']:.0f}자, 토큰 초과로 잘림 {s['truncated']}개), "
                      f"인코딩 {s['encode_s']:.1f}s")
            t1 = time.time()
            for ddl in INDEX_DDL:
                conn.execute(ddl)
            conn.execute("ANALYZE kakao.chunks")
            conn.commit()
            print(f"인덱스(HNSW cosine, trgm) + ANALYZE {time.time() - t1:.1f}s. 총 {time.time() - t0:.1f}s")
    except psycopg.OperationalError as e:
        print(f"DB 접속 실패 ({args.db}): {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
