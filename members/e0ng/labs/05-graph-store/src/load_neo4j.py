#!/usr/bin/env python3
"""추출한 그래프를 Neo4j에 MERGE로 적재한다. 여러 번 실행해도 노드·관계가 중복 생기지 않는다."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from neo4j import GraphDatabase

from common import load_documents, neo4j_auth, neo4j_uri
from extract_triples import Graph, build_graph, group_by_activity

LITERAL_LIST_PREDICATES = {"activityKind", "activityScope"}  # 한 노드에 여러 값이 붙을 수 있음


def to_rel_type(predicate: str) -> str:
    """occursInPeriod -> OCCURS_IN_PERIOD (Cypher 관계 타입 관례)."""
    predicate = predicate.replace("schema:", "")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", predicate).upper()


def to_property_name(predicate: str) -> str:
    return predicate.replace("schema:", "")


def load_graph(driver, graph: Graph) -> None:
    with driver.session() as session:
        # 1) 노드: id로 MERGE, 라벨은 타입 전체(예: Activity, Activity:Document)
        for entity in graph.entities.values():
            labels = ":".join(entity.types)
            session.run(
                f"MERGE (n:{labels} {{id: $id}}) SET n.name = $name",
                id=entity.id,
                name=entity.name,
            )

        # 2) 리터럴 값은 노드 속성으로 (같은 predicate가 여러 값이면 리스트로 모음)
        literal_by_subject: dict[str, dict[str, list[str]]] = {}
        for edge in graph.edges:
            if edge.object_literal is None:
                continue
            prop = to_property_name(edge.predicate)
            values = literal_by_subject.setdefault(edge.subject_id, {}).setdefault(prop, [])
            if edge.object_literal not in values:
                values.append(edge.object_literal)

        for subject_id, props in literal_by_subject.items():
            for prop, values in props.items():
                value = values if prop in LITERAL_LIST_PREDICATES else values[0]
                session.run(f"MATCH (n {{id: $id}}) SET n.{prop} = $value", id=subject_id, value=value)

        # 3) 엔티티-엔티티 관계는 MERGE로 (중복 제거)
        seen: set[tuple[str, str, str]] = set()
        for edge in graph.edges:
            if edge.object_id is None:
                continue
            key = (edge.subject_id, edge.predicate, edge.object_id)
            if key in seen:
                continue
            seen.add(key)
            rel_type = to_rel_type(edge.predicate)
            session.run(
                f"MATCH (a {{id: $subj}}), (b {{id: $obj}}) MERGE (a)-[:{rel_type}]->(b)",
                subj=edge.subject_id,
                obj=edge.object_id,
            )


def main() -> None:
    groups = group_by_activity(load_documents())
    graph = build_graph(groups, {})  # Topic(LLM)은 필수가 아니라 구조 적재만으로도 충분

    uri = neo4j_uri()
    driver = GraphDatabase.driver(uri, auth=neo4j_auth())
    try:
        driver.verify_connectivity()
        load_graph(driver, graph)
    finally:
        driver.close()
    print(f"엔티티 {len(graph.entities)}개를 Neo4j({uri})에 MERGE로 적재했습니다.")


if __name__ == "__main__":
    main()
