#!/usr/bin/env python3
"""추출한 그래프를 Postgres 3개 테이블(엔티티/엣지/근거)에 저장한다."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg

from common import get_env, load_documents, postgres_dsn
from extract_triples import Graph, build_graph, group_by_activity


def create_schema(connection) -> None:
    sql = (Path(__file__).resolve().parent / "schema.sql").read_text(encoding="utf-8")
    connection.execute(sql)


def store_graph(connection, graph: Graph) -> None:
    create_schema(connection)

    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO kg_entities (id, types, name) VALUES (%s, %s, %s)",
            [(entity.id, entity.types, entity.name) for entity in graph.entities.values()],
        )
        for edge in graph.edges:
            cursor.execute(
                """
                INSERT INTO kg_edges (subject_id, predicate, object_id, object_literal)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (edge.subject_id, edge.predicate, edge.object_id, edge.object_literal),
            )
            edge_id = cursor.fetchone()[0]
            if edge.source:
                cursor.execute(
                    "INSERT INTO kg_evidence (edge_id, source) VALUES (%s, %s)",
                    (edge_id, edge.source),
                )
    connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="추출한 그래프를 Postgres에 저장합니다.")
    parser.add_argument("--topics-from", type=Path, help="extract_triples.py가 만든 .ttl에서 Topic만 재사용 (없으면 Topic 없이 저장)")
    args = parser.parse_args()

    groups = group_by_activity(load_documents())
    topics: dict[str, str] = {}
    if args.topics_from and args.topics_from.exists():
        # 아주 단순한 파서: `about "..."` 줄에서 값만 꺼낸다 (schema:about 재파싱용, rdflib 불필요)
        import re

        pattern = re.compile(r':(activity_\S+|doc_\S+) schema:about "([^"]+)"')
        by_id = {}
        for line in args.topics_from.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line)
            if match:
                by_id[match.group(1)] = match.group(2)
        for (period, activity, org), pages in groups.items():
            from extract_triples import slug

            activity_id = f"activity_{slug(activity)}"
            if activity_id in by_id:
                topics[activity] = by_id[activity_id]

    graph = build_graph(groups, topics)

    dsn = postgres_dsn()
    with psycopg.connect(dsn) as connection:
        store_graph(connection, graph)
    print(f"엔티티 {len(graph.entities)}개, 엣지 {len(graph.edges)}개를 Postgres({dsn})에 저장했습니다.")


if __name__ == "__main__":
    main()
