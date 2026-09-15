-- pgvector 확장은 루트 infra/postgres/init/01-extensions.sql에서 이미 생성된다
-- (CREATE EXTENSION IF NOT EXISTS vector;). 여기서는 이 실습 전용 테이블만 만든다.
--
-- 공용 Postgres 인스턴스이므로 다른 멤버와 겹치지 않도록 테이블명에 do_dop_ 접두사를 둔다.

CREATE TABLE IF NOT EXISTS do_dop_kakao_chunks (
    -- 청크 원문과 검색용 임베딩을 한 행에 함께 저장한다.
    id            BIGSERIAL PRIMARY KEY,
    chunk_id      TEXT NOT NULL UNIQUE,
    sender_id     TEXT NOT NULL,
    started_at    TIMESTAMP NOT NULL,
    ended_at      TIMESTAMP NOT NULL,
    message_count INT NOT NULL,
    content       TEXT NOT NULL,
    embedding     VECTOR(1024)  -- bge-m3 차원. 다른 모델로 바꾸면 함께 조정
);

CREATE INDEX IF NOT EXISTS do_dop_kakao_chunks_embedding_hnsw
    -- 코사인 거리 기준으로 가까운 벡터를 빠르게 찾는 HNSW 인덱스다.
    ON do_dop_kakao_chunks USING hnsw (embedding vector_cosine_ops);
