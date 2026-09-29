#!/usr/bin/env python3
"""Postgres의 정규화된 지식 그래프를 Neo4j 5.x에 배치 적재한다."""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from collections.abc import Iterable, Sequence
from typing import Any


DEFAULT_PG_DSN = "postgresql://study:study@localhost:5433/study"
DEFAULT_NEO4J_URI = "bolt://localhost:7687"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "study-password"
DEFAULT_NEO4J_DATABASE = "neo4j"

ENTITY_TYPES = ("Project", "Technology", "TechnologyUse")
RowGroups = dict[str, list[dict[str, Any]]]
RELATION_TYPES = {
    "partOf": "PART_OF",
    "usesTechnology": "USES_TECHNOLOGY",
    "replaces": "REPLACES",
}

CONSTRAINT_QUERIES = (
    "CREATE CONSTRAINT project_id_unique IF NOT EXISTS "
    "FOR (node:Project) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT technology_id_unique IF NOT EXISTS "
    "FOR (node:Technology) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT technology_use_id_unique IF NOT EXISTS "
    "FOR (node:TechnologyUse) REQUIRE node.id IS UNIQUE",
)

NODE_QUERIES = {
    "Project": """
        UNWIND $rows AS row
        MERGE (node:Project {id: row.id})
        SET node.entity_id = row.id,
            node.label = row.label,
            node.ingested_from = 'postgres'
    """,
    "Technology": """
        UNWIND $rows AS row
        MERGE (node:Technology {id: row.id})
        SET node.entity_id = row.id,
            node.label = row.label,
            node.ingested_from = 'postgres'
    """,
    "TechnologyUse": """
        UNWIND $rows AS row
        MERGE (node:TechnologyUse {id: row.id})
        SET node.entity_id = row.id,
            node.label = row.label,
            node.purpose = row.purpose,
            node.status = row.status,
            node.ingested_from = 'postgres'
    """,
}

RELATION_QUERIES = {
    "partOf": """
        UNWIND $rows AS row
        MATCH (source:TechnologyUse {id: row.subject})
        MATCH (target:Project {id: row.object})
        MERGE (source)-[relation:PART_OF {edge_key: row.edge_key}]->(target)
        SET relation.chunk_id = row.chunk_id,
            relation.evidence = row.evidence,
            relation.confidence = row.confidence,
            relation.extraction_run = row.extraction_run,
            relation.ingested_from = 'postgres'
    """,
    "usesTechnology": """
        UNWIND $rows AS row
        MATCH (source:TechnologyUse {id: row.subject})
        MATCH (target:Technology {id: row.object})
        MERGE (source)-[relation:USES_TECHNOLOGY {edge_key: row.edge_key}]->(target)
        SET relation.chunk_id = row.chunk_id,
            relation.evidence = row.evidence,
            relation.confidence = row.confidence,
            relation.extraction_run = row.extraction_run,
            relation.ingested_from = 'postgres'
    """,
    "replaces": """
        UNWIND $rows AS row
        MATCH (source:TechnologyUse {id: row.subject})
        MATCH (target:TechnologyUse {id: row.object})
        MERGE (source)-[relation:REPLACES {edge_key: row.edge_key}]->(target)
        SET relation.chunk_id = row.chunk_id,
            relation.evidence = row.evidence,
            relation.confidence = row.confidence,
            relation.extraction_run = row.extraction_run,
            relation.ingested_from = 'postgres'
    """,
}


def batches(rows: Sequence[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    if size <= 0:
        raise ValueError("batch size는 1 이상이어야 합니다")
    for start in range(0, len(rows), size):
        yield list(rows[start : start + size])


def make_edge_key(subject: str, predicate: str, obj: str, chunk_id: str) -> str:
    raw = "\x1f".join((subject, predicate, obj, chunk_id)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_postgres(dsn: str) -> tuple[RowGroups, RowGroups]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("psycopg가 없습니다. requirements.txt를 설치하세요.") from exc

    nodes = {entity_type: [] for entity_type in ENTITY_TYPES}
    relationships = {predicate: [] for predicate in RELATION_TYPES}
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT entity_id, type, label, props FROM entities ORDER BY entity_id"
            )
            for entity_id, entity_type, label, props in cursor.fetchall():
                if entity_type not in nodes:
                    continue
                props = props or {}
                nodes[entity_type].append(
                    {
                        "id": entity_id,
                        "label": label,
                        "purpose": props.get("purpose"),
                        "status": props.get("status"),
                    }
                )

            cursor.execute(
                """
                SELECT subject, predicate, object, chunk_id,
                       evidence, confidence, extraction_run
                FROM edges
                WHERE predicate = ANY(%s)
                ORDER BY id
                """,
                (list(RELATION_TYPES),),
            )
            for subject, predicate, obj, chunk_id, evidence, confidence, run in cursor.fetchall():
                relationships[predicate].append(
                    {
                        "edge_key": make_edge_key(subject, predicate, obj, chunk_id),
                        "subject": subject,
                        "object": obj,
                        "chunk_id": chunk_id,
                        "evidence": evidence,
                        "confidence": confidence,
                        "extraction_run": run,
                    }
                )
    return nodes, relationships


def create_constraints(session) -> None:
    for query in CONSTRAINT_QUERIES:
        session.run(query).consume()


def run_batches(session, query: str, rows: list[dict[str, Any]], batch_size: int) -> None:
    for batch in batches(rows, batch_size):
        session.execute_write(lambda tx, items=batch: tx.run(query, rows=items).consume())


def load_graph(
    session,
    nodes: RowGroups,
    relationships: RowGroups,
    batch_size: int,
) -> None:
    # 제약조건을 먼저 만든 뒤 노드, 관계 순서로 적재한다.
    create_constraints(session)
    for entity_type in ENTITY_TYPES:
        run_batches(session, NODE_QUERIES[entity_type], nodes[entity_type], batch_size)
    for predicate in RELATION_TYPES:
        run_batches(
            session,
            RELATION_QUERIES[predicate],
            relationships[predicate],
            batch_size,
        )


def graph_counts(session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label in ENTITY_TYPES:
        record = session.run(f"MATCH (node:{label}) RETURN count(node) AS count").single()
        counts[label] = int(record["count"])
    for relationship_type in RELATION_TYPES.values():
        record = session.run(
            f"MATCH ()-[relation:{relationship_type}]->() RETURN count(relation) AS count"
        ).single()
        counts[relationship_type] = int(record["count"])
    return counts


def expected_counts(
    nodes: RowGroups,
    relationships: RowGroups,
) -> dict[str, int]:
    result = {entity_type: len(rows) for entity_type, rows in nodes.items()}
    result.update(
        {RELATION_TYPES[predicate]: len(rows) for predicate, rows in relationships.items()}
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Postgres 지식 그래프를 Neo4j에 배치 적재합니다.")
    parser.add_argument("--pg-dsn", default=os.environ.get("POSTGRES_DSN", DEFAULT_PG_DSN))
    parser.add_argument("--neo4j-uri", default=os.environ.get("NEO4J_URI", DEFAULT_NEO4J_URI))
    parser.add_argument("--neo4j-user", default=os.environ.get("NEO4J_USER", DEFAULT_NEO4J_USER))
    parser.add_argument(
        "--neo4j-password",
        default=os.environ.get("NEO4J_PASSWORD", DEFAULT_NEO4J_PASSWORD),
    )
    parser.add_argument(
        "--neo4j-database",
        default=os.environ.get("NEO4J_DATABASE", DEFAULT_NEO4J_DATABASE),
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--verify-idempotency",
        action="store_true",
        help="같은 데이터를 즉시 한 번 더 적재하고 개수 불변을 확인",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        from neo4j import GraphDatabase

        nodes, relationships = read_postgres(args.pg_dsn)
        expected = expected_counts(nodes, relationships)
        with GraphDatabase.driver(
            args.neo4j_uri,
            auth=(args.neo4j_user, args.neo4j_password),
        ) as driver:
            driver.verify_connectivity()
            with driver.session(database=args.neo4j_database) as session:
                load_graph(session, nodes, relationships, args.batch_size)
                first_counts = graph_counts(session)
                if args.verify_idempotency:
                    load_graph(session, nodes, relationships, args.batch_size)
                    second_counts = graph_counts(session)
                    if first_counts != second_counts:
                        raise RuntimeError(
                            f"재적재 후 개수가 달라졌습니다: {first_counts} -> {second_counts}"
                        )
                    print("재실행 검증: 노드/관계 개수 불변 (중복 없음)")

        print("Postgres 원본:", expected)
        print("Neo4j 적재 후:", first_counts)
        mismatches = {
            key: (expected[key], first_counts.get(key, 0))
            for key in expected
            if expected[key] != first_counts.get(key, 0)
        }
        if mismatches:
            print(
                "주의: 기존 Neo4j 데이터가 있거나 MATCH되지 않은 행이 있습니다: "
                f"{mismatches}",
                file=sys.stderr,
            )
            return 2
        return 0
    except Exception as exc:
        print(f"오류: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
