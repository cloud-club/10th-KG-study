"""기존 Neo4j 그래프에 검토한 관심 분야와 읽기 쉬운 표시 관계를 적재한다.

원문 근거는 Assertion/Evidence로 보존하고, 분야 분류 IN_AREA에는 수동 검토 출처를 표시한다.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "interests.json"
GRAPH_ID_PREFIX = "https://example.org/kdyann/content-graph/v0/"
PRESENTATION_FACTS = {
    "coversTopic": "COVERS_TOPIC",
    "describesProject": "DESCRIBES_PROJECT",
    "describesFeature": "DESCRIBES_FEATURE",
    "hasFeature": "HAS_FEATURE",
    "expressesConcept": "EXPRESSES_CONCEPT",
}


def validate_config(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"profile_id", "interests", "topic_areas"}:
        raise ValueError("profile_id, interests, topic_areas가 필요합니다.")
    profile = value["profile_id"]
    interests = value["interests"]
    mappings = value["topic_areas"]
    if not isinstance(profile, str) or not profile.strip() or len(profile) > 80:
        raise ValueError("profile_id를 확인해 주세요.")
    if not isinstance(interests, list) or not interests or any(
        not isinstance(area, str) or not area.strip() or len(area) > 80 for area in interests
    ) or len(set(interests)) != len(interests):
        raise ValueError("interests는 중복 없는 관심 분야 목록이어야 합니다.")
    if not isinstance(mappings, dict) or any(
        not isinstance(topic, str) or not topic.strip() or len(topic) > 120
        or not isinstance(area, str) or area not in interests
        for topic, area in mappings.items()
    ):
        raise ValueError("topic_areas는 관심 분야에 속하는 주제만 연결할 수 있습니다.")
    return value


def load_config(path: Path) -> dict:
    return validate_config(json.loads(path.read_text(encoding="utf-8")))


def post_caption(text: str, source_id: str) -> str:
    for line in text.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.lower().startswith(("comment ", "💬 comment ")):
            return line[:42] + ("…" if len(line) > 42 else "")
    return source_id


def load_neo4j(config: dict, uri: str, user: str, password: str, database: str | None = None,
               documents: list[dict] | None = None) -> dict:
    from neo4j import GraphDatabase

    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        kwargs = {"database_": database} if database else {}
        driver.execute_query("CREATE CONSTRAINT w6_profile_id IF NOT EXISTS FOR (n:Profile) REQUIRE n.id IS UNIQUE", **kwargs)
        driver.execute_query("CREATE CONSTRAINT w6_area_name IF NOT EXISTS FOR (n:InterestArea) REQUIRE n.name IS UNIQUE", **kwargs)
        driver.execute_query("""MATCH (n:W5Profile) WHERE n.id IN $managed_profiles
            SET n:Profile REMOVE n:W5Profile""",
            managed_profiles=[config["profile_id"], "kdyann"], **kwargs)
        driver.execute_query("""MATCH (p:Profile)-[:W5_INTERESTED_IN]->(n:W5InterestArea)
            WHERE p.id IN $managed_profiles AND n.name IN $areas
              AND NOT EXISTS {
                MATCH (other)-[:W5_INTERESTED_IN|INTERESTED_IN]->(n)
                WHERE other.id IS NULL OR NOT other.id IN $managed_profiles
              }
            SET n:InterestArea REMOVE n:W5InterestArea""",
            managed_profiles=[config["profile_id"], "kdyann"],
            areas=config["interests"], **kwargs)
        # 이전 적재의 내부 라벨을 의미 라벨로 옮긴 뒤 아래에서 접두 라벨을 제거한다.
        for entity_type, label in (("Post", "Post"), ("Topic", "Topic"),
                                   ("Project", "Project"), ("Feature", "Feature"),
                                   ("Concept", "Concept")):
            driver.execute_query(f"""MATCH (n:W5Entity {{entity_type: $entity_type}})
                WHERE n.id STARTS WITH $graph_prefix SET n:{label}""",
                entity_type=entity_type, graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        driver.execute_query("""MATCH (n:W5Entity)
            WHERE n.id STARTS WITH $graph_prefix
            REMOVE n:W5Post:W5OwnPost:W5ReferencePost:W5Topic:W5Project:W5Feature:W5Concept
            SET n.display_name = coalesce(n.display_name, n.name)""",
            graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        driver.execute_query("""MATCH (n:Post {corpus: 'own'}) WHERE n.id STARTS WITH $graph_prefix
            SET n:OwnPost REMOVE n:ReferencePost""", graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        driver.execute_query("""MATCH (n:Post {corpus: 'reference'}) WHERE n.id STARTS WITH $graph_prefix
            SET n:ReferencePost REMOVE n:OwnPost""", graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        if documents:
            for doc in documents:
                source_id = doc.get("source_id", doc.get("id"))
                if not isinstance(source_id, str) or not isinstance(doc.get("text"), str):
                    raise ValueError("표시 제목을 만들 문서에 source_id와 text가 필요합니다.")
                driver.execute_query("""MATCH (n:Post {source_id: $source_id})
                    WHERE n.id STARTS WITH $graph_prefix
                    SET n.display_name = CASE
                        WHEN n.corpus = 'own' AND n.post_number IS NOT NULL THEN n.post_number
                        ELSE $display_name END""", source_id=source_id,
                    display_name=post_caption(doc["text"], source_id),
                    graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        for predicate, label in PRESENTATION_FACTS.items():
            driver.execute_query(f"""MATCH (s:W5Entity)-[fact:W5_FACT {{predicate: $predicate}}]->(o:W5Entity)
                WHERE fact.id STARTS WITH $graph_prefix
                MERGE (s)-[view:{label} {{source_fact_id: fact.id}}]->(o)
                SET view.provenance = 'caption_evidence'""", predicate=predicate,
                graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        # 이전 실험 프로필은 다른 관계가 없을 때만 제거한다.
        if config["profile_id"] != "kdyann":
            driver.execute_query("""MATCH (legacy:Profile {id: 'kdyann'})
                WHERE NOT EXISTS { MATCH (legacy)-[r]-() WHERE type(r) <> 'W5_INTERESTED_IN' }
                DETACH DELETE legacy""", **kwargs)
            driver.execute_query("""MATCH (t)-[r:W5_CURATED_IN_AREA]->()
                WHERE t.id STARTS WITH $graph_prefix AND r.profile_id = 'kdyann'
                DELETE r""", graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        driver.execute_query("""MATCH (p:Profile {id: $profile_id})-[r:INTERESTED_IN]->(a)
            WHERE NOT a.name IN $areas DELETE r""",
            profile_id=config["profile_id"], areas=config["interests"], **kwargs)
        driver.execute_query("""MATCH (t:Topic)-[r:IN_AREA]->(a:InterestArea)
            WHERE t.id STARTS WITH $graph_prefix AND r.profile_id = $profile_id
              AND none(item IN $mappings WHERE item.topic = t.name AND item.area = a.name)
            DELETE r""", profile_id=config["profile_id"],
            graph_prefix=GRAPH_ID_PREFIX,
            mappings=[{"topic": topic, "area": area} for topic, area in config["topic_areas"].items()], **kwargs)
        for area in config["interests"]:
            driver.execute_query("""MERGE (p:Profile {id: $profile_id})
                SET p.display_name = $profile_id
                MERGE (a:InterestArea {name: $area})
                SET a.display_name = $area
                MERGE (p)-[r:INTERESTED_IN]->(a)
                SET r.provenance = 'user_curated'""",
                profile_id=config["profile_id"], area=area, **kwargs)
        driver.execute_query("""MATCH (p:Profile {id: $profile_id}), (post:OwnPost)
            WHERE post.id STARTS WITH $graph_prefix
            MERGE (p)-[r:PUBLISHED]->(post)
            SET r.provenance = 'reviewed_own_document', r.account_id = $profile_id""",
            profile_id=config["profile_id"], graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        missing = []
        for topic, area in config["topic_areas"].items():
            records, _, _ = driver.execute_query("""MATCH (t:Topic {name: $topic})
                WHERE t.id STARTS WITH $graph_prefix
                MATCH (a:InterestArea {name: $area})
                MERGE (t)-[r:IN_AREA {profile_id: $profile_id}]->(a)
                SET r.provenance = 'manual_review'
                RETURN count(t) AS linked""", topic=topic, area=area,
                profile_id=config["profile_id"], graph_prefix=GRAPH_ID_PREFIX, **kwargs)
            if not records[0]["linked"]:
                missing.append(topic)
        unsupported, _, _ = driver.execute_query("""MATCH ()-[r:W5_FACT]->()
            WHERE r.id STARTS WITH $graph_prefix AND NOT r.predicate IN $predicates
            RETURN count(r) AS count""",
            graph_prefix=GRAPH_ID_PREFIX, predicates=list(PRESENTATION_FACTS), **kwargs)
        if unsupported[0]["count"]:
            raise RuntimeError("변환되지 않은 W5_FACT 관계가 있어 원본 관계를 유지합니다.")
        for predicate, label in PRESENTATION_FACTS.items():
            unmatched, _, _ = driver.execute_query(f"""MATCH (s)-[fact:W5_FACT {{predicate: $predicate}}]->(o)
                WHERE fact.id STARTS WITH $graph_prefix
                  AND NOT EXISTS {{ MATCH (s)-[:{label} {{source_fact_id: fact.id}}]->(o) }}
                RETURN count(fact) AS count""", predicate=predicate,
                graph_prefix=GRAPH_ID_PREFIX, **kwargs)
            if unmatched[0]["count"]:
                raise RuntimeError(f"{predicate} 표시 관계 검증에 실패해 원본 관계를 유지합니다.")
        driver.execute_query("""MATCH ()-[r:W5_FACT]->() WHERE r.id STARTS WITH $graph_prefix
            DELETE r""", graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        driver.execute_query("""MATCH (p:Profile)-[r:W5_INTERESTED_IN]->()
            WHERE p.id IN $managed_profiles AND r.provenance = 'user_curated' DELETE r""",
            managed_profiles=[config["profile_id"], "kdyann"], **kwargs)
        driver.execute_query("""MATCH (t)-[r:W5_CURATED_IN_AREA]->()
            WHERE t.id STARTS WITH $graph_prefix AND r.profile_id IN $managed_profiles
            DELETE r""", managed_profiles=[config["profile_id"], "kdyann"],
            graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        driver.execute_query("""MATCH (n:W5Entity) WHERE n.id STARTS WITH $graph_prefix
            REMOVE n:W5Entity""", graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        driver.execute_query("""MATCH (n:W5Assertion) WHERE n.id STARTS WITH $graph_prefix
            SET n:Assertion REMOVE n:W5Assertion""", graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        driver.execute_query("""MATCH (n:W5Evidence) WHERE n.id STARTS WITH $graph_prefix
            SET n:Evidence REMOVE n:W5Evidence""", graph_prefix=GRAPH_ID_PREFIX, **kwargs)
        return {"mapped_topics": len(config["topic_areas"]) - len(missing), "missing_topics": missing}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--documents", type=Path, default=Path(__file__).resolve().parents[5]
                        / "data/kdyann/processed/content_graph/w6-reviewed/documents.jsonl")
    args = parser.parse_args()
    config = load_config(args.config)
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        parser.error("NEO4J_PASSWORD 환경 변수가 필요합니다.")
    documents = []
    if args.documents.is_file():
        documents = [json.loads(line) for line in args.documents.read_text(encoding="utf-8").split("\n") if line.strip()]
    result = load_neo4j(config, os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687"),
                        os.environ.get("NEO4J_USER", "neo4j"), password,
                        os.environ.get("NEO4J_DATABASE"), documents)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
