-- 컨테이너 최초 기동 시(볼륨이 비어 있을 때) 한 번만 실행됩니다.
-- 이미 만들어진 DB에 적용하려면: docker compose exec postgres psql -U kg -d kg -f /docker-entrypoint-initdb.d/01-extensions.sql

-- 벡터 검색 (임베딩 저장, <-> / <=> / <#> 거리 연산, HNSW/IVFFlat 인덱스)
CREATE EXTENSION IF NOT EXISTS vector;

-- 트라이그램 유사도 (ILIKE 가속, 오타 허용 검색). 하이브리드 검색 실습에서 BM25 대용으로 유용
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 쓰는 법 예시 (주석 해제해서 psql 에서 실행):
-- CREATE TABLE chunks (
--   id        bigserial PRIMARY KEY,
--   doc_id    text NOT NULL,
--   content   text NOT NULL,
--   embedding vector(1536)          -- 임베딩 모델 차원에 맞춰 조정
-- );
-- CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
-- SELECT id, content FROM chunks ORDER BY embedding <=> '[...]'::vector LIMIT 5;
