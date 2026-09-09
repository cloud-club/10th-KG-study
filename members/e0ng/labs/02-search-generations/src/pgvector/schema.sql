CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chat_chunks (
    id bigserial PRIMARY KEY,
    sender text NOT NULL,
    message text NOT NULL,
    timestamp timestamptz NOT NULL,
    end_timestamp timestamptz NOT NULL,
    source_message_count integer NOT NULL,
    embedding vector(1024) NOT NULL
);

CREATE INDEX IF NOT EXISTS chat_chunks_embedding_hnsw
ON chat_chunks USING hnsw (embedding vector_cosine_ops);
