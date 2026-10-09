"""두 힌디어 Topic과 전용 Assertion/Evidence만 Neo4j에서 제거한다 (기본 dry-run)."""
from __future__ import annotations

import argparse
import json
import os

from enrich_interests import GRAPH_ID_PREFIX

TOPICS = {
    GRAPH_ID_PREFIX + "topic/686253b8783b18074b428d05": "AI खतरे",
    GRAPH_ID_PREFIX + "topic/5328d3bbad8dbd15c89d1b9a": "AI कानून और नियमन",
}


def unexpected_topic_relationships(rows: list[dict], assertion_ids: list[str]) -> list[dict]:
    """대상 Topic에 연결된 관계 중 삭제가 다른 데이터를 훼손할 수 있는 것을 찾는다."""
    allowed_assertions = set(assertion_ids)
    unexpected = []
    for row in rows:
        kind, props = row["type"], row["properties"]
        incoming = row["end_id"] == row["topic_id"]
        other_labels = set(row["other_labels"])
        safe = (
            kind == "OBJECT" and incoming and "Assertion" in other_labels
            and row["other_id"] in allowed_assertions
            or kind == "COVERS_TOPIC" and incoming and "ReferencePost" in other_labels
            and props.get("source_fact_id") in allowed_assertions
            or kind == "IN_AREA" and not incoming and "InterestArea" in other_labels
            and props.get("profile_id") == "junyounge"
        )
        if not safe:
            unexpected.append(row)
    return unexpected


def audit(tx) -> dict:
    topics = tx.run("""MATCH (t:Topic) WHERE any(item IN $targets
        WHERE t.id = item.id AND t.name = item.name)
        RETURN collect(t.id) AS ids""",
        targets=[{"id": topic_id, "name": name} for topic_id, name in TOPICS.items()]).single()["ids"]
    assertions = tx.run("""MATCH (a:Assertion)-[:OBJECT]->(t:Topic)
        WHERE t.id IN $ids RETURN collect(DISTINCT a.id) AS ids""", ids=topics).single()["ids"]
    evidence = tx.run("""MATCH (e:Evidence)-[:SUPPORTS]->(a:Assertion)
        WHERE a.id IN $ids RETURN collect(DISTINCT e.id) AS ids""", ids=assertions).single()["ids"]
    own = tx.run("""MATCH (p:OwnPost)-[:COVERS_TOPIC]->(t:Topic)
        WHERE t.id IN $ids RETURN count(DISTINCT p) AS count""", ids=topics).single()["count"]
    shared_assertions = tx.run("""MATCH (a:Assertion)-[:OBJECT]->(other)
        WHERE a.id IN $assertions AND NOT (other.id IN $topics)
        RETURN count(DISTINCT a) AS count""", assertions=assertions, topics=topics).single()["count"]
    shared_evidence = tx.run("""MATCH (e:Evidence)-[:SUPPORTS]->(other:Assertion)
        WHERE e.id IN $evidence AND NOT (other.id IN $assertions)
        RETURN count(DISTINCT e) AS count""", evidence=evidence, assertions=assertions).single()["count"]
    other_profiles = tx.run("""MATCH (t:Topic)-[r:IN_AREA]->(:InterestArea)
        WHERE t.id IN $ids AND (r.profile_id IS NULL OR r.profile_id <> $profile_id)
        RETURN count(r) AS count""", ids=topics, profile_id="junyounge").single()["count"]
    relationship_rows = [dict(record) for record in tx.run("""
        MATCH (t:Topic)-[r]-(other) WHERE t.id IN $ids
        RETURN t.id AS topic_id, type(r) AS type, properties(r) AS properties,
               startNode(r).id AS start_id, endNode(r).id AS end_id,
               other.id AS other_id, labels(other) AS other_labels
        """, ids=topics)]
    unexpected = unexpected_topic_relationships(relationship_rows, assertions)
    result = {"topics": topics, "assertions": assertions, "evidence": evidence,
              "own_links": own, "shared_assertions": shared_assertions,
              "shared_evidence": shared_evidence, "other_profile_links": other_profiles,
              "unexpected_relationships": unexpected}
    if any(result[key] for key in ("own_links", "shared_assertions", "shared_evidence",
                                   "other_profile_links", "unexpected_relationships")):
        raise RuntimeError(f"공유된 근거/관계가 있어 삭제를 중단합니다: {result}")
    return result


def apply(tx) -> dict:
    result = audit(tx)
    for label, ids in (("Evidence", result["evidence"]),
                       ("Assertion", result["assertions"]),
                       ("Topic", result["topics"])):
        if ids:
            tx.run(f"MATCH (n:{label}) WHERE n.id IN $ids DETACH DELETE n", ids=ids).consume()
    return result


def main() -> None:
    from neo4j import GraphDatabase

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="검토한 dry-run 결과를 실제 반영")
    args = parser.parse_args()
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        parser.error("NEO4J_PASSWORD 환경 변수가 필요합니다.")
    with GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687"),
                              auth=(os.environ.get("NEO4J_USER", "neo4j"), password)) as driver:
        with driver.session(database=os.environ.get("NEO4J_DATABASE")) as session:
            result = session.execute_write(apply) if args.apply else session.execute_read(audit)
    print(json.dumps({"mode": "apply" if args.apply else "dry-run",
                      "topics": len(result["topics"]), "assertions": len(result["assertions"]),
                      "evidence": len(result["evidence"]), "topic_ids": result["topics"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
