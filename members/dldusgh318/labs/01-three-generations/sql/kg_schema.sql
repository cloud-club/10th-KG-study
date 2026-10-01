CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    type      TEXT NOT NULL,
    label     TEXT NOT NULL,
    props     JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS edges (
    id             BIGSERIAL PRIMARY KEY,
    subject        TEXT NOT NULL REFERENCES entities(entity_id),
    predicate      TEXT NOT NULL,
    object         TEXT NOT NULL,
    chunk_id       TEXT NOT NULL REFERENCES chunks(chunk_id),
    evidence       TEXT NOT NULL,
    confidence     REAL,
    extraction_run TEXT NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS edges_subject_predicate_idx
    ON edges (subject, predicate);
CREATE INDEX IF NOT EXISTS edges_object_predicate_idx
    ON edges (object, predicate);
CREATE UNIQUE INDEX IF NOT EXISTS edges_unique_spoc_idx
    ON edges (subject, predicate, object, chunk_id);
