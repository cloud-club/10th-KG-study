#!/usr/bin/env python3
"""kakao.chunks 검색: 벡터(pgvector) / 트라이그램(pg_trgm) / 하이브리드(RRF).

    uv run --with 'sentence-transformers>=3' --with 'psycopg[binary]' \
        members/sese2204/labs/02-kakao-chunk-embed/src/search.py "수강신청 언제였지" -k 5 --mode hybrid

- vector : 질문을 같은 모델로 임베딩해 코사인 거리(<=>) 순. HNSW 인덱스 사용
- trgm   : word_similarity(질문, 본문) 순. 질문이 본문 어딘가에 "비슷하게 들어 있는지". GIN trgm 인덱스 사용
- hybrid : 두 결과를 RRF(1/(60+rank)) 로 합침. 기본값
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

RRF_K = 60
SNIPPET_CHARS = 240


def default_db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    return "postgresql://{u}:{p}@localhost:{port}/{db}".format(
        u=os.environ.get("POSTGRES_USER", "kg"), p=os.environ.get("POSTGRES_PASSWORD", "kg"),
        port=os.environ.get("POSTGRES_PORT", "5432"), db=os.environ.get("POSTGRES_DB", "kg"),
    )


def to_pgvector(vec) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in vec) + "]"


COLS = "c.id, r.name, c.started_at, c.ended_at, c.message_count, c.text"


def vector_search(conn, qvec: str, k: int):
    # 청크가 1만 개 정도면 플래너가 HNSW 대신 순차 스캔(74ms)을 고른다. 이 질의에서만 끄면 HNSW(1.8ms).
    with conn.transaction():
        conn.execute("SET LOCAL enable_seqscan = off")
        return conn.execute(
            f"SELECT {COLS}, 1 - (c.embedding <=> %s::vector) AS score FROM kakao.chunks c "
            "JOIN kakao.rooms r ON r.id = c.room_id ORDER BY c.embedding <=> %s::vector LIMIT %s",
            (qvec, qvec, k),
        ).fetchall()


def trgm_search(conn, query: str, k: int):
    # word_similarity 는 짧은 질문이 긴 본문에 들어 있을 때 높게 나옴. 임계값은 pg_trgm.word_similarity_threshold(0.6)
    return conn.execute(
        f"SELECT {COLS}, word_similarity(%s, c.text) AS score FROM kakao.chunks c "
        "JOIN kakao.rooms r ON r.id = c.room_id WHERE %s <%% c.text ORDER BY score DESC, c.id LIMIT %s",
        (query, query, k),
    ).fetchall()


def rrf(*ranked_lists):
    scores: dict[int, float] = defaultdict(float)
    rows: dict[int, tuple] = {}
    for ranked in ranked_lists:
        for rank, row in enumerate(ranked, 1):
            scores[row[0]] += 1 / (RRF_K + rank)
            rows.setdefault(row[0], row)
    return [rows[i][:6] + (s,) for i, s in sorted(scores.items(), key=lambda kv: -kv[1])]


def show(rows) -> None:
    if not rows:
        print("결과 없음")
        return
    for i, (cid, room, started, ended, n, text, score) in enumerate(rows, 1):
        snippet = text.replace("\n", " │ ")
        if len(snippet) > SNIPPET_CHARS:
            snippet = snippet[:SNIPPET_CHARS] + "…"
        print(f"{i}. [{score:.4f}] {room} {started:%Y-%m-%d %H:%M}~{ended:%H:%M} ({n}개, chunk {cid})\n   {snippet}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--mode", choices=["hybrid", "vector", "trgm"], default="hybrid")
    ap.add_argument("--db", default=default_db_url())
    ap.add_argument("--model", default=None, help="기본: kakao.chunks 에 기록된 모델")
    args = ap.parse_args(argv)

    import psycopg

    with psycopg.connect(args.db) as conn:
        if args.mode == "trgm":
            show(trgm_search(conn, args.query, args.k))
            return 0
        model_name = args.model or (conn.execute("SELECT model FROM kakao.chunks LIMIT 1").fetchone() or [None])[0]
        if model_name is None:
            print("kakao.chunks 가 비어 있습니다. embed.py 먼저 실행하세요.", file=sys.stderr)
            return 1
        import transformers
        from sentence_transformers import SentenceTransformer
        transformers.logging.set_verbosity_error()
        qvec = to_pgvector(SentenceTransformer(model_name).encode(args.query, normalize_embeddings=True))
        if args.mode == "vector":
            show(vector_search(conn, qvec, args.k))
            return 0
        show(rrf(vector_search(conn, qvec, args.k * 2), trgm_search(conn, args.query, args.k * 2))[: args.k])
    return 0


if __name__ == "__main__":
    sys.exit(main())
