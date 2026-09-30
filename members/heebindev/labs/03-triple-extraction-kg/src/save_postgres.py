"""추출한 엔티티·관계·근거를 PostgreSQL 테이블에 저장한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import psycopg


LAB_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = LAB_ROOT / "outputs/triples.jsonl"
DEFAULT_DSN = "postgresql://kg:kg@127.0.0.1:5432/kg"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    return parser.parse_args()


def stable_id(*parts: str) -> str:
    value = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:24]


def normalize_name(name: str) -> str:
    aliases = {
        "os": "운영체제",
        "operating system": "운영체제",
    }
    cleaned = " ".join(name.strip().split())
    return aliases.get(cleaned.casefold(), cleaned)


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"추출 결과를 찾지 못했습니다: {path}")
    with path.open(encoding="utf-8") as input_file:
        return [json.loads(line) for line in input_file if line.strip()]


def create_tables(connection: psycopg.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_entities (
            id text PRIMARY KEY,
            name text NOT NULL,
            normalized_name text NOT NULL,
            entity_type text NOT NULL,
            UNIQUE (normalized_name, entity_type)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_relations (
            id text PRIMARY KEY,
            subject_id text NOT NULL REFERENCES kg_entities(id),
            predicate text NOT NULL,
            object_id text NOT NULL REFERENCES kg_entities(id),
            UNIQUE (subject_id, predicate, object_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_evidence (
            relation_id text NOT NULL REFERENCES kg_relations(id),
            chunk_id text NOT NULL,
            source text NOT NULL,
            document_title text NOT NULL,
            heading text NOT NULL,
            evidence text NOT NULL,
            PRIMARY KEY (relation_id, chunk_id, evidence)
        )
        """
    )


def main() -> None:
    args = parse_args()
    rows = load_rows(args.input)
    entity_count = 0
    relation_count = 0
    evidence_count = 0

    with psycopg.connect(args.dsn) as connection:
        create_tables(connection)
        for row in rows:
            entity_ids: dict[str, str] = {}
            for entity in row["entities"]:
                normalized = normalize_name(entity["name"])
                entity_id = stable_id(entity["type"], normalized.casefold())
                entity_ids[entity["name"]] = entity_id
                result = connection.execute(
                    """
                    INSERT INTO kg_entities (id, name, normalized_name, entity_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (normalized_name, entity_type) DO NOTHING
                    """,
                    (entity_id, entity["name"], normalized, entity["type"]),
                )
                entity_count += result.rowcount

            for relation in row["relations"]:
                subject_id = entity_ids.get(relation["subject"])
                object_id = entity_ids.get(relation["object"])
                if not subject_id or not object_id:
                    continue
                relation_id = stable_id(subject_id, relation["predicate"], object_id)
                result = connection.execute(
                    """
                    INSERT INTO kg_relations (id, subject_id, predicate, object_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (subject_id, predicate, object_id) DO NOTHING
                    """,
                    (relation_id, subject_id, relation["predicate"], object_id),
                )
                relation_count += result.rowcount
                result = connection.execute(
                    """
                    INSERT INTO kg_evidence (
                        relation_id, chunk_id, source, document_title, heading, evidence
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        relation_id,
                        row["chunk_id"],
                        row["source"],
                        row["document_title"],
                        row["heading"],
                        relation["evidence"],
                    ),
                )
                evidence_count += result.rowcount

    print(f"새 엔티티: {entity_count}개")
    print(f"새 관계: {relation_count}개")
    print(f"새 근거: {evidence_count}개")
    print("PostgreSQL 테이블: kg_entities, kg_relations, kg_evidence")


if __name__ == "__main__":
    main()
