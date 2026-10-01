"""추출한 엔티티와 관계를 Neo4j 프로퍼티 그래프에 적재한다."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parents[3]
DEFAULT_INPUT = LAB_ROOT / "outputs/triples.jsonl"
DEFAULT_SCHEMA = LAB_ROOT / "schema/ontology.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--url", default="http://127.0.0.1:7474")
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password")
    return parser.parse_args()


def read_env_value(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{name}="):
                return line.partition("=")[2].strip().strip("\"'")
    return None


def stable_id(entity_type: str, name: str) -> str:
    aliases = {"os": "운영체제", "operating system": "운영체제"}
    normalized = " ".join(name.strip().split())
    normalized = aliases.get(normalized.casefold(), normalized)
    value = f"{entity_type}\x1f{normalized.casefold()}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:24]


def run_query(
    base_url: str,
    database: str,
    user: str,
    password: str,
    statement: str,
    parameters: dict,
) -> None:
    endpoint = f"{base_url.rstrip('/')}/db/{database}/tx/commit"
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    body = {"statements": [{"statement": statement, "parameters": parameters}]}
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Neo4j 요청 실패 ({error.code}): {detail}") from error
    if result.get("errors"):
        raise RuntimeError(f"Neo4j 질의 실패: {result['errors']}")


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"추출 결과를 찾지 못했습니다: {args.input}")
    ontology = json.loads(args.schema.read_text(encoding="utf-8"))
    allowed_predicates = set(ontology["predicates"])
    with args.input.open(encoding="utf-8") as input_file:
        rows = [json.loads(line) for line in input_file if line.strip()]

    entities: dict[str, dict] = {}
    relations_by_type: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        name_to_id: dict[str, str] = {}
        for entity in row["entities"]:
            entity_id = stable_id(entity["type"], entity["name"])
            name_to_id[entity["name"]] = entity_id
            entities[entity_id] = {
                "id": entity_id,
                "name": entity["name"],
                "kind": entity["type"],
            }
        for relation in row["relations"]:
            predicate = relation["predicate"]
            if predicate not in allowed_predicates:
                continue
            subject_id = name_to_id.get(relation["subject"])
            object_id = name_to_id.get(relation["object"])
            if not subject_id or not object_id:
                continue
            relations_by_type[predicate].append(
                {
                    "subject_id": subject_id,
                    "object_id": object_id,
                    "chunk_id": row["chunk_id"],
                    "evidence": relation["evidence"],
                }
            )

    password = args.password or read_env_value("NEO4J_PASSWORD") or "kgstudy2026"
    run_query(
        args.url,
        args.database,
        args.user,
        password,
        """
        UNWIND $rows AS row
        MERGE (n:Entity {id: row.id})
        SET n.name = row.name, n.kind = row.kind
        """,
        {"rows": list(entities.values())},
    )

    relation_count = 0
    for predicate, relation_rows in relations_by_type.items():
        query = f"""
        UNWIND $rows AS row
        MATCH (s:Entity {{id: row.subject_id}})
        MATCH (o:Entity {{id: row.object_id}})
        MERGE (s)-[r:{predicate}]->(o)
        SET r.evidence = CASE
              WHEN row.evidence IN coalesce(r.evidence, []) THEN r.evidence
              ELSE coalesce(r.evidence, []) + [row.evidence]
            END,
            r.chunk_ids = CASE
              WHEN row.chunk_id IN coalesce(r.chunk_ids, []) THEN r.chunk_ids
              ELSE coalesce(r.chunk_ids, []) + [row.chunk_id]
            END
        """
        run_query(
            args.url,
            args.database,
            args.user,
            password,
            query,
            {"rows": relation_rows},
        )
        relation_count += len(relation_rows)

    print(f"Neo4j 엔티티: {len(entities)}개")
    print(f"Neo4j에 처리한 관계 근거: {relation_count}개")
    print(f"브라우저: {args.url}")


if __name__ == "__main__":
    main()
