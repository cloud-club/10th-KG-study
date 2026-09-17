CREATE TABLE IF NOT EXISTS do_dop_company_analysis_chunks (
    chunk_id       TEXT PRIMARY KEY,
    document_id    TEXT NOT NULL,
    title          TEXT NOT NULL,
    companies      JSONB NOT NULL,
    source         TEXT NOT NULL,
    published_at   DATE NOT NULL,
    content        TEXT NOT NULL,
    url            TEXT NOT NULL,
    embedding      VECTOR(1024)
);

CREATE INDEX IF NOT EXISTS do_dop_company_analysis_chunks_embedding_hnsw
    ON do_dop_company_analysis_chunks
    USING hnsw (embedding vector_cosine_ops);

