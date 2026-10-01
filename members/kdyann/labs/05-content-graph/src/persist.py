"""검토한 W5 추출 결과를 PostgreSQL과 Neo4j에 중복 없이 적재한다.

실행: python3 src/persist.py --output /path/to/content_graph --target postgres|neo4j|both
PG_DSN 또는 NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD를 환경에 설정한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from pipeline import BASE, RELATIONS, ValidationError, _node_id, _post_id, _published_utc, _read_jsonl


def _hash_id(kind: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:24]
    return BASE + kind + "/" + digest


def _nonnegative_number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def _nonnegative_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def prepare(documents: list[dict[str, Any]], facts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """RDF와 동일한 Post/엔티티 식별자를 쓰고 근거 범위를 다시 확인한다."""
    docs = {}
    entities = {}
    edges = {}
    evidence = {}
    for doc in documents:
        source_id = doc["id"]
        if source_id in docs:
            raise ValidationError(f"중복 문서 ID: {source_id}")
        if doc.get("corpus") not in ("own", "reference") or not isinstance(doc.get("text"), str):
            raise ValidationError(f"문서에 corpus/text가 필요합니다: {source_id}")
        published = _published_utc(doc.get("published_at"))
        collected = _published_utc(doc.get("collected_at"))
        selection = doc.get("selection") if isinstance(doc.get("selection"), dict) else {}
        metrics = doc.get("metrics") if isinstance(doc.get("metrics"), dict) else {}
        selected_score = _nonnegative_number(selection.get("score"))
        observed_likes = _nonnegative_int(selection.get("observed_likes", metrics.get("likes")))
        observed_comments = _nonnegative_int(selection.get("observed_comments", metrics.get("comments")))
        docs[source_id] = {"source_id": source_id, "corpus": doc["corpus"], "text": doc["text"],
                           "published_at": published, "collected_at": collected,
                           "permalink": doc.get("permalink"), "selection_score": selected_score,
                           "observed_likes": observed_likes, "observed_comments": observed_comments}
        post_id = _post_id(source_id)
        entities[post_id] = {"id": post_id, "entity_type": "Post", "name": source_id,
                             "source_id": source_id, "corpus": doc["corpus"],
                             "published_at": published, "collected_at": collected,
                             "permalink": doc.get("permalink"), "selection_score": selected_score,
                             "observed_likes": observed_likes, "observed_comments": observed_comments}
    for fact in facts:
        source_id = fact["source_id"]
        if source_id not in docs:
            raise ValidationError(f"근거 문서가 없습니다: {source_id}")
        predicate = fact["predicate"]
        signature = (fact["subject_type"], fact["object_type"])
        if predicate not in RELATIONS or signature != RELATIONS[predicate]:
            raise ValidationError(f"스키마 밖 관계: {predicate} {signature}")
        quote, start, end = fact["evidence"], fact["start"], fact["end"]
        if (not isinstance(quote, str) or not isinstance(start, int) or not isinstance(end, int)
                or start < 0 or end <= start or docs[source_id]["text"][start:end] != quote):
            raise ValidationError(f"근거 범위가 원문과 다릅니다: {source_id}")
        if fact["subject_type"] == "Post":
            if fact["subject_name"] != source_id:
                raise ValidationError("Post 주어 이름은 source_id여야 합니다.")
            subject_id = _post_id(source_id)
        else:
            subject_id = _node_id(fact["subject_type"], fact["subject_name"])
            entities[subject_id] = {"id": subject_id, "entity_type": fact["subject_type"],
                                    "name": fact["subject_name"], "source_id": None,
                                    "corpus": None, "published_at": None, "collected_at": None,
                                    "permalink": None, "selection_score": None,
                                    "observed_likes": None, "observed_comments": None}
        is_literal = fact["object_type"] == "Literal"
        object_id = None if is_literal else _node_id(fact["object_type"], fact["object_name"])
        literal = fact["object_name"] if is_literal else None
        if object_id:
            entities[object_id] = {"id": object_id, "entity_type": fact["object_type"],
                                   "name": fact["object_name"], "source_id": None,
                                   "corpus": None, "published_at": None, "collected_at": None,
                                   "permalink": None, "selection_score": None,
                                   "observed_likes": None, "observed_comments": None}
        edge_id = _hash_id("edge", subject_id, predicate, object_id or "", literal or "")
        edges[edge_id] = {"id": edge_id, "subject_id": subject_id, "predicate": predicate,
                          "object_id": object_id, "object_literal": literal}
        evidence_id = _hash_id("evidence", source_id, subject_id, BASE + predicate,
                               fact["object_type"], object_id or literal or "", str(start), str(end))
        evidence[evidence_id] = {"id": evidence_id, "edge_id": edge_id,
                                 "source_id": source_id, "quote": quote, "start": start, "end": end}
    return {"documents": list(docs.values()), "entities": list(entities.values()),
            "edges": list(edges.values()), "evidence": list(evidence.values())}


SCHEMA = (
    """CREATE TABLE IF NOT EXISTS cg_w5_documents (
        source_id TEXT PRIMARY KEY, corpus TEXT NOT NULL, text TEXT NOT NULL,
        published_at TIMESTAMPTZ, collected_at TIMESTAMPTZ, permalink TEXT,
        selection_score DOUBLE PRECISION, observed_likes BIGINT, observed_comments BIGINT)""",
    """CREATE TABLE IF NOT EXISTS cg_w5_entities (
        id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, name TEXT NOT NULL,
        source_id TEXT REFERENCES cg_w5_documents(source_id))""",
    """CREATE TABLE IF NOT EXISTS cg_w5_edges (
        id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES cg_w5_entities(id),
        predicate TEXT NOT NULL, object_id TEXT REFERENCES cg_w5_entities(id),
        object_literal TEXT,
        CHECK ((object_id IS NULL) <> (object_literal IS NULL)))""",
    """CREATE TABLE IF NOT EXISTS cg_w5_evidence (
        id TEXT PRIMARY KEY, edge_id TEXT NOT NULL REFERENCES cg_w5_edges(id),
        source_id TEXT NOT NULL REFERENCES cg_w5_documents(source_id),
        quote TEXT NOT NULL, start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
        CHECK (start_offset >= 0 AND end_offset > start_offset))""",
    "CREATE INDEX IF NOT EXISTS cg_w5_evidence_edge_idx ON cg_w5_evidence(edge_id)",
    "ALTER TABLE cg_w5_documents ADD COLUMN IF NOT EXISTS collected_at TIMESTAMPTZ",
    "ALTER TABLE cg_w5_documents ADD COLUMN IF NOT EXISTS selection_score DOUBLE PRECISION",
    "ALTER TABLE cg_w5_documents ADD COLUMN IF NOT EXISTS observed_likes BIGINT",
    "ALTER TABLE cg_w5_documents ADD COLUMN IF NOT EXISTS observed_comments BIGINT",
)


def load_postgres(records: dict[str, list[dict[str, Any]]], dsn: str) -> None:
    import psycopg

    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        for statement in SCHEMA:
            cursor.execute(statement)
        for doc in records["documents"]:
            cursor.execute("""INSERT INTO cg_w5_documents
                (source_id, corpus, text, published_at, collected_at, permalink,
                 selection_score, observed_likes, observed_comments)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (source_id) DO UPDATE SET
                corpus = EXCLUDED.corpus, text = EXCLUDED.text,
                published_at = EXCLUDED.published_at, collected_at = EXCLUDED.collected_at,
                permalink = EXCLUDED.permalink, selection_score = EXCLUDED.selection_score,
                observed_likes = EXCLUDED.observed_likes, observed_comments = EXCLUDED.observed_comments""",
                (doc["source_id"], doc["corpus"], doc["text"], doc["published_at"],
                 doc["collected_at"], doc["permalink"], doc["selection_score"],
                 doc["observed_likes"], doc["observed_comments"]))
        for entity in records["entities"]:
            cursor.execute("""INSERT INTO cg_w5_entities (id, entity_type, name, source_id)
                VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name""",
                (entity["id"], entity["entity_type"], entity["name"], entity["source_id"]))
        for edge in records["edges"]:
            cursor.execute("""INSERT INTO cg_w5_edges (id, subject_id, predicate, object_id, object_literal)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING""",
                (edge["id"], edge["subject_id"], edge["predicate"], edge["object_id"], edge["object_literal"]))
        for item in records["evidence"]:
            cursor.execute("""INSERT INTO cg_w5_evidence
                (id, edge_id, source_id, quote, start_offset, end_offset)
                VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING""",
                (item["id"], item["edge_id"], item["source_id"], item["quote"], item["start"], item["end"]))


NEO4J_CONSTRAINTS = (
    "CREATE CONSTRAINT cg_w5_entity_id IF NOT EXISTS FOR (n:W5Entity) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT cg_w5_assertion_id IF NOT EXISTS FOR (n:W5Assertion) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT cg_w5_evidence_id IF NOT EXISTS FOR (n:W5Evidence) REQUIRE n.id IS UNIQUE",
)


def load_neo4j(records: dict[str, list[dict[str, Any]]], uri: str, user: str, password: str,
               database: str | None = None) -> None:
    from neo4j import GraphDatabase

    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        kwargs = {"database_": database} if database else {}
        for statement in NEO4J_CONSTRAINTS:
            driver.execute_query(statement, **kwargs)
        for entity in records["entities"]:
            driver.execute_query("""MERGE (n:W5Entity {id: $id})
                SET n.entity_type = $entity_type, n.name = $name, n.source_id = $source_id,
                    n.corpus = $corpus, n.published_at = $published_at,
                    n.collected_at = $collected_at, n.permalink = $permalink,
                    n.selection_score = $selection_score, n.observed_likes = $observed_likes,
                    n.observed_comments = $observed_comments""",
                id=entity["id"], entity_type=entity["entity_type"], name=entity["name"],
                source_id=entity["source_id"], corpus=entity["corpus"],
                published_at=entity["published_at"].isoformat() if entity["published_at"] else None,
                collected_at=entity["collected_at"].isoformat() if entity["collected_at"] else None,
                permalink=entity["permalink"], selection_score=entity["selection_score"],
                observed_likes=entity["observed_likes"], observed_comments=entity["observed_comments"], **kwargs)
        for edge in records["edges"]:
            driver.execute_query("""MATCH (s:W5Entity {id: $subject_id})
                MERGE (a:W5Assertion {id: $id})
                SET a.predicate = $predicate, a.object_literal = $object_literal
                MERGE (a)-[:SUBJECT]->(s)""", **edge, **kwargs)
            if edge["object_id"] is not None:
                driver.execute_query("""MATCH (s:W5Entity {id: $subject_id}), (o:W5Entity {id: $object_id}),
                    (a:W5Assertion {id: $id})
                    MERGE (s)-[r:W5_FACT {id: $id}]->(o)
                    SET r.predicate = $predicate
                    MERGE (a)-[:OBJECT]->(o)""", **edge, **kwargs)
        for item in records["evidence"]:
            driver.execute_query("""MATCH (a:W5Assertion {id: $edge_id}),
                (p:W5Entity {id: $source_post_id})
                MERGE (e:W5Evidence {id: $id})
                SET e.quote = $quote, e.start_offset = $start, e.end_offset = $end,
                    e.source_id = $source_id
                MERGE (e)-[:SUPPORTS]->(a)
                MERGE (e)-[:SOURCE_POST]->(p)""",
                **item, source_post_id=_post_id(item["source_id"]), **kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="pipeline.py 출력 폴더")
    parser.add_argument("--target", choices=("postgres", "neo4j", "both"), default="both")
    args = parser.parse_args()
    records = prepare(_read_jsonl(args.output / "documents.jsonl"), _read_jsonl(args.output / "facts.jsonl"))
    if args.target in ("postgres", "both"):
        dsn = os.environ.get("PG_DSN", "postgresql://kg:kg@127.0.0.1:5432/kg")
        load_postgres(records, dsn)
    if args.target in ("neo4j", "both"):
        password = os.environ.get("NEO4J_PASSWORD")
        if not password:
            parser.error("NEO4J_PASSWORD 환경 변수가 필요합니다.")
        load_neo4j(records, os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687"),
                   os.environ.get("NEO4J_USER", "neo4j"), password,
                   os.environ.get("NEO4J_DATABASE"))
    print(json.dumps({key: len(value) for key, value in records.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
