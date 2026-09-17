CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id text PRIMARY KEY,
    page_id text NOT NULL,
    title text NOT NULL,
    content text NOT NULL,
    source text NOT NULL,
    chunk_index integer NOT NULL,
    embedding vector(1024) NOT NULL
);

CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw
ON document_chunks USING hnsw (embedding vector_cosine_ops);
