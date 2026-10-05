"""03 전용 Nori·pgvector 인덱스를 동일 코퍼스로 갱신한다. 01 저장소는 변경하지 않는다."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

from hybrid_search import (DIMENSION, OUTPUT_DIR, SearchBackendError, check_manifest, corpus_manifest,
                           embedding_model, es_request, load_corpus, settings, vector_literal)


def index_config(manifest: dict[str, Any]) -> dict[str, Any]:
    return {"settings": {"analysis": {
                "tokenizer": {"korean_nori": {"type": "nori_tokenizer", "decompound_mode": "mixed"}},
                "analyzer": {"korean_nori_analyzer": {"type": "custom", "tokenizer": "korean_nori",
                                                       "filter": ["nori_part_of_speech", "nori_readingform", "lowercase"]}}}},
            "mappings": {"dynamic": "strict", "_meta": {**manifest, "status": "building"},
                         "properties": {"id": {"type": "keyword"}, "text": {"type": "text", "analyzer": "korean_nori_analyzer"},
                                        "permalink": {"type": "keyword", "index": False}, "corpus": {"type": "keyword"},
                                        "provenance": {"type": "keyword"}, "published_at": {"type": "date"},
                                        "collected_at": {"type": "date"}}}}


def index_documents() -> dict[str, Any]:
    import psycopg
    from psycopg import sql
    from psycopg.types.json import Jsonb
    config = settings()
    documents = load_corpus()
    manifest = corpus_manifest(documents)
    index, table = config["es_index"], config["pg_table"]
    metadata_table = table + "_metadata"
    existing_index = False
    try:
        mapping = es_request("GET", f"{index}/_mapping")[index]["mappings"]
        check_manifest(mapping.get("_meta", {}), manifest, indexing=True)
        existing_index = True
    except SearchBackendError as error:
        if str(error) != "Elasticsearch HTTP 404":
            raise
    # Ownership checks on both stores precede any indexing mutation.
    with psycopg.connect(config["pg_dsn"]) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s), to_regclass(%s)", (table, metadata_table))
        data_exists, meta_exists = cursor.fetchone()
        if bool(data_exists) != bool(meta_exists):
            raise ValueError("03 데이터 테이블과 소유 메타데이터가 함께 있어야 합니다.")
        if meta_exists:
            cursor.execute(sql.SQL("SELECT manifest FROM {} WHERE id = 1").format(sql.Identifier(metadata_table)))
            row = cursor.fetchone()
            check_manifest(row[0] if row else {}, manifest, indexing=True)
    model = embedding_model()
    embeddings = model.encode([f"passage: {row['text']}" for row in documents], batch_size=16,
                              normalize_embeddings=True, show_progress_bar=False)
    if len(embeddings) != len(documents):
        raise ValueError("문서와 임베딩 개수가 다릅니다.")
    literals = [vector_literal(values) for values in embeddings]
    if existing_index:
        es_request("PUT", f"{index}/_mapping", {"_meta": {**manifest, "status": "building"}})
    else:
        es_request("PUT", index, index_config(manifest))
    lines = []
    for row in documents:
        lines.extend((json.dumps({"index": {"_index": index, "_id": row["id"]}}), json.dumps(row, ensure_ascii=False)))
    result = es_request("POST", "_bulk", ("\n".join(lines) + "\n").encode("utf-8"), "application/x-ndjson")
    if result.get("errors"):
        raise RuntimeError("03 Elasticsearch bulk 적재가 실패했습니다. 검색을 시작하지 않았습니다.")
    # Remove stale IDs only from the owned, explicitly named 03 index.
    es_request("POST", f"{index}/_delete_by_query?refresh=true", {"query": {"bool": {"must_not": [{"ids": {"values": [row["id"] for row in documents]}}]}}})
    es_request("POST", f"{index}/_refresh")
    if es_request("GET", f"{index}/_count")["count"] != len(documents):
        raise RuntimeError("03 Elasticsearch 적재 문서 수가 다릅니다.")
    with psycopg.connect(config["pg_dsn"]) as connection, connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cursor.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (id text PRIMARY KEY, text text NOT NULL, permalink text NOT NULL, corpus text NOT NULL CHECK (corpus IN ('own', 'reference')), provenance jsonb NOT NULL, published_at text, collected_at text, embedding vector({}) NOT NULL)")
                       .format(sql.Identifier(table), sql.Literal(DIMENSION)))
        cursor.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (id integer PRIMARY KEY CHECK (id = 1), manifest jsonb NOT NULL)").format(sql.Identifier(metadata_table)))
        statement = sql.SQL("INSERT INTO {} (id, text, permalink, corpus, provenance, published_at, collected_at, embedding) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector) ON CONFLICT (id) DO UPDATE SET text=EXCLUDED.text, permalink=EXCLUDED.permalink, corpus=EXCLUDED.corpus, provenance=EXCLUDED.provenance, published_at=EXCLUDED.published_at, collected_at=EXCLUDED.collected_at, embedding=EXCLUDED.embedding").format(sql.Identifier(table))
        cursor.executemany(statement, [(row["id"], row["text"], row["permalink"], row["corpus"], Jsonb(row["provenance"]),
                                        row["published_at"], row["collected_at"], literal) for row, literal in zip(documents, literals)])
        cursor.execute(sql.SQL("DELETE FROM {} WHERE NOT (id = ANY(%s))").format(sql.Identifier(table)), ([row["id"] for row in documents],))
        cursor.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)")
                       .format(sql.Identifier(table + "_embedding_hnsw"), sql.Identifier(table)))
        ready = {**manifest, "status": "ready"}
        cursor.execute(sql.SQL("INSERT INTO {} (id, manifest) VALUES (1, %s) ON CONFLICT (id) DO UPDATE SET manifest=EXCLUDED.manifest").format(sql.Identifier(metadata_table)), (Jsonb(ready),))
        cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
        if cursor.fetchone()[0] != len(documents):
            raise RuntimeError("03 pgvector 적재 문서 수가 다릅니다.")
        cursor.execute(sql.SQL("ANALYZE {}").format(sql.Identifier(table)))
    es_request("PUT", f"{index}/_mapping", {"_meta": ready})
    result = {**ready, "es_index": index, "pg_table": table, "indexed_at": datetime.now(timezone.utc).isoformat(),
              "vector_search": "pgvector cosine with HNSW index available (planner chooses); exact scoped scan for own/reference to avoid filtered ANN under-return"}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_DIR / "index_metadata.json.tmp"
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT_DIR / "index_metadata.json")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(index_documents(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
