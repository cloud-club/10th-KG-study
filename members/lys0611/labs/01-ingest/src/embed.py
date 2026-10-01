#!/usr/bin/env python3
"""chunks 테이블의 텍스트를 임베딩해 chunk_embeddings(pgvector)에 저장한다.

  python src/embed.py                 # 아직 임베딩 없는 청크만 처리 (중단 후 재실행하면 이어서 함)
  python src/embed.py --room 여행모임  # 특정 방만

.env 로 제공자를 고른다.
  EMBED_PROVIDER=openai  EMBED_MODEL=text-embedding-3-small  EMBED_DIM=1536   (OPENAI_API_KEY)
  EMBED_PROVIDER=gemini  EMBED_MODEL=gemini-embedding-001    EMBED_DIM=768    (GEMINI_API_KEY, pip install google-genai)
  EMBED_PROVIDER=local   EMBED_MODEL=BAAI/bge-m3             EMBED_DIM=1024   (pip install sentence-transformers)
                         EMBED_MODEL=nlpai-lab/KURE-v1       EMBED_DIM=1024   (한국어 특화, bge-m3 기반)

주의: chunk_embeddings.embedding 은 vector(EMBED_DIM) 고정. 차원이 다른 모델로 바꾸려면
      테이블을 지우거나(DROP TABLE chunk_embeddings) 새 테이블 이름을 써야 한다.
"""
from __future__ import annotations

import argparse
import math
import sys
import time

from common import (EMBED_BATCH, EMBED_DIM, EMBED_MODEL, EMBED_PROVIDER, get_pg, room_filter_sql,
                    vec_literal)


# ------------------------------------------------------------------ 제공자별 임베더
def _normalize(vecs: list[list[float]]) -> list[list[float]]:
    out = []
    for v in vecs:
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


class Embedder:
    """embed(texts, is_query) -> list[list[float]] (L2 정규화됨)."""

    def __init__(self):
        self.provider, self.model, self.dim = EMBED_PROVIDER, EMBED_MODEL, EMBED_DIM
        if self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI()  # OPENAI_API_KEY 환경변수 사용
        elif self.provider == "gemini":
            from google import genai
            self.client = genai.Client()  # GEMINI_API_KEY 환경변수 사용
        elif self.provider == "local":
            from sentence_transformers import SentenceTransformer
            self.client = SentenceTransformer(self.model)
        else:
            raise SystemExit(f"EMBED_PROVIDER 값이 이상합니다: {self.provider}")

    def _call(self, texts: list[str], is_query: bool) -> list[list[float]]:
        if self.provider == "openai":
            res = self.client.embeddings.create(model=self.model, input=texts, dimensions=self.dim)
            return [d.embedding for d in res.data]
        if self.provider == "gemini":
            from google.genai import types
            cfg = types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT",
                output_dimensionality=self.dim,
            )
            res = self.client.models.embed_content(model=self.model, contents=texts, config=cfg)
            return [list(e.values) for e in res.embeddings]
        # local: bge-m3 / KURE 는 접두어 불필요. (e5 계열은 "query: " / "passage: " 접두어를 붙여야 함)
        arr = self.client.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        return [list(map(float, v)) for v in arr]

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        for attempt in range(6):
            try:
                vecs = self._call(texts, is_query)
                if vecs and len(vecs[0]) != self.dim:
                    raise SystemExit(f"모델이 돌려준 차원 {len(vecs[0])} ≠ EMBED_DIM {self.dim}. .env 를 맞춰 주세요.")
                return _normalize(vecs)
            except SystemExit:
                raise
            except Exception as e:  # 429/5xx/네트워크 → 지수 백오프
                wait = 2 ** attempt
                print(f"  [retry {attempt + 1}] {type(e).__name__}: {str(e)[:120]} → {wait}s 대기", file=sys.stderr)
                time.sleep(wait)
        raise SystemExit("임베딩 API 호출이 계속 실패합니다.")


# ------------------------------------------------------------------ 테이블
def ensure_table(cur, dim: int):
    cur.execute(
        f"""CREATE TABLE IF NOT EXISTS chunk_embeddings (
              chunk_id   BIGINT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
              model      TEXT NOT NULL,
              embedding  vector({dim}) NOT NULL,
              created_at TIMESTAMPTZ DEFAULT now(),
              PRIMARY KEY (chunk_id, model)
            )"""
    )
    cur.execute(
        """SELECT format_type(atttypid, atttypmod) FROM pg_attribute
           WHERE attrelid = 'chunk_embeddings'::regclass AND attname = 'embedding'"""
    )
    existing = cur.fetchone()[0]
    if existing != f"vector({dim})":
        raise SystemExit(f"chunk_embeddings.embedding 은 {existing} 인데 EMBED_DIM={dim} 입니다. "
                         "DROP TABLE chunk_embeddings; 후 다시 실행하거나 EMBED_DIM 을 맞춰 주세요.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--room", help="특정 방만 임베딩")
    ap.add_argument("--limit", type=int, default=0, help="테스트용: 최대 N개 청크만")
    args = ap.parse_args()

    emb = Embedder()
    where, params = room_filter_sql(args.room, "r")
    with get_pg() as conn, conn.cursor() as cur:
        ensure_table(cur, emb.dim)
        conn.commit()
        cur.execute(
            f"""SELECT c.id, c.text FROM chunks c JOIN rooms r ON r.id = c.room_id
                LEFT JOIN chunk_embeddings e ON e.chunk_id = c.id AND e.model = %s
                WHERE e.chunk_id IS NULL{where} ORDER BY c.id""" + (f" LIMIT {args.limit}" if args.limit else ""),
            [emb.model] + params,
        )
        todo = cur.fetchall()
        total_chars = sum(len(t) for _, t in todo)
        print(f"[embed] provider={emb.provider} model={emb.model} dim={emb.dim} → 대상 {len(todo):,}청크 "
              f"(~{total_chars:,}자)", file=sys.stderr)

        done = 0
        for i in range(0, len(todo), EMBED_BATCH):
            batch = todo[i:i + EMBED_BATCH]
            vecs = emb.embed([t for _, t in batch], is_query=False)
            cur.executemany(
                "INSERT INTO chunk_embeddings (chunk_id, model, embedding) VALUES (%s, %s, %s::vector) "
                "ON CONFLICT DO NOTHING",
                [(cid, emb.model, vec_literal(v)) for (cid, _), v in zip(batch, vecs)],
            )
            conn.commit()  # 배치마다 커밋 → 중간에 끊겨도 재실행 시 이어서
            done += len(batch)
            print(f"  {done:,}/{len(todo):,}", file=sys.stderr, end="\r")
        print(file=sys.stderr)

        # HNSW 인덱스(코사인). 데이터 적재 후 만드는 편이 빠르다. 이미 있으면 통과.
        cur.execute("CREATE INDEX IF NOT EXISTS chunk_embeddings_hnsw ON chunk_embeddings "
                    "USING hnsw (embedding vector_cosine_ops)")
        conn.commit()
        cur.execute("SELECT count(*) FROM chunk_embeddings WHERE model = %s", (emb.model,))
        print(f"[embed] 완료. chunk_embeddings({emb.model}) = {cur.fetchone()[0]:,}행, HNSW 인덱스 준비됨", file=sys.stderr)


if __name__ == "__main__":
    main()
