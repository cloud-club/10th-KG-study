"""실제 Neo4j에서 그래프 개요 질의의 범위를 읽기 전용으로 검증한다."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]


def main() -> None:
    from neo4j import GraphDatabase, RoutingControl

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        parser.error("NEO4J_PASSWORD 환경 변수가 필요합니다.")
    config = json.loads((LAB / "interests.json").read_text(encoding="utf-8"))
    profile_id = config["profile_id"]
    def read_query(name: str) -> str:
        source = (LAB / "src/queries" / name).read_text(encoding="utf-8")
        return "\n".join(line for line in source.splitlines()
                         if not line.lstrip().startswith("//")).rstrip().rstrip(";")

    overview = read_query("01_graph_overview.cypher")
    all_own = read_query("03_all_own_posts.cypher")
    kwargs = {"database_": os.environ["NEO4J_DATABASE"]} if os.environ.get("NEO4J_DATABASE") else {}
    with GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687"),
                              auth=(os.environ.get("NEO4J_USER", "neo4j"), password)) as driver:
        for query in (overview, all_own):
            driver.execute_query("EXPLAIN " + query, profile_id=profile_id, as_of=args.as_of,
                                 routing_=RoutingControl.READ, **kwargs)
        overview_rows, _, _ = driver.execute_query(overview, profile_id=profile_id, as_of=args.as_of,
                                                   routing_=RoutingControl.READ, **kwargs)
        own_rows, _, _ = driver.execute_query(all_own, profile_id=profile_id,
                                              routing_=RoutingControl.READ, **kwargs)
        expected, _, _ = driver.execute_query("""
            MATCH (p:Profile {id: $profile_id})
            OPTIONAL MATCH (p)-[:PUBLISHED]->(own:OwnPost)
            WITH p, collect(DISTINCT own.id) AS own_ids
            OPTIONAL MATCH (p)-[:INTERESTED_IN]->(area:InterestArea)
            WITH p, own_ids, collect(DISTINCT area.name) AS area_names
            OPTIONAL MATCH (p)-[:PUBLISHED]->(:OwnPost)-[:COVERS_TOPIC]->(topic:Topic)
            RETURN own_ids, area_names, collect(DISTINCT topic.id) AS own_topic_ids
            """, profile_id=profile_id, routing_=RoutingControl.READ, **kwargs)
        baseball, _, _ = driver.execute_query("""
            MATCH (p:Profile {id: $profile_id})-[:PUBLISHED]->(:OwnPost)
                  -[:COVERS_TOPIC]->(topic:Topic {name: '야구'})
            RETURN count(topic) AS count
            """, profile_id=profile_id, routing_=RoutingControl.READ, **kwargs)
    if not expected:
        raise RuntimeError(f"Profile {profile_id!r}가 없습니다.")
    def visible_ids(rows: list, label: str) -> set[str]:
        return {node["id"] for row in rows for node in row["path"].nodes if label in node.labels}

    visible = {"own_ids": visible_ids(own_rows, "OwnPost"),
               "area_names": {node["name"] for row in overview_rows
                              for node in row["path"].nodes if "InterestArea" in node.labels},
               "own_topic_ids": visible_ids(own_rows, "Topic")}
    missing = {key: sorted(set(expected[0][key]) - visible[key]) for key in visible}
    missing["configured_areas"] = sorted(set(config["interests"]) - visible["area_names"])
    if baseball[0]["count"] and not any(
            node["name"] == "야구" for row in overview_rows for node in row["path"].nodes
            if "Topic" in node.labels):
        missing["baseball_topic"] = ["야구"]
    if any(missing.values()):
        raise AssertionError(f"개요 그래프에서 빠진 노드: {missing}")
    print(json.dumps({"overview_paths": len(overview_rows), "own_paths": len(own_rows),
                      "own_posts": len(visible["own_ids"]),
                      "interest_areas": len(visible["area_names"]),
                      "visible_topics": len(visible["own_topic_ids"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
