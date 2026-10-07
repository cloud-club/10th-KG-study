"""검토한 W6 사실을 단일 Neo4j 그래프와 PostgreSQL에 중복 없이 적재한다."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(LAB.parent / "05-content-graph" / "src"))
from persist import load_postgres, prepare  # noqa: E402
from pipeline import _read_jsonl  # noqa: E402
from enrich_interests import PRESENTATION_FACTS, load_config, load_neo4j as enrich_graph, post_caption
from language_policy import validate_reference_records


def assign_post_numbers(existing: dict, documents: list[dict]) -> dict[str, int]:
    if (not isinstance(existing, dict) or any(not isinstance(source_id, str) or not source_id
            or type(number) is not int or number < 1 for source_id, number in existing.items())
            or len(set(existing.values())) != len(existing)):
        raise ValueError("게시글 번호 파일에는 중복 없는 양의 정수가 필요합니다.")
    result = dict(existing)
    own = [doc for doc in documents if doc["corpus"] == "own"]
    next_number = max(result.values(), default=0) + 1
    for doc in sorted(own, key=lambda item: (str(item.get("published_at") or ""), item["source_id"])):
        if doc["source_id"] not in result:
            result[doc["source_id"]] = next_number
            next_number += 1
    return result


def display_name_for_entity(entity: dict, captions: dict[str, str],
                            post_numbers: dict[str, int]) -> str:
    if entity["entity_type"] == "Post" and entity["corpus"] == "own":
        return f"게시글 {post_numbers[entity['source_id']]}"
    return captions.get(entity["source_id"], entity["name"])


def load_unified(records: dict, uri: str, user: str, password: str, database: str | None = None,
                 post_numbers: dict[str, int] | None = None) -> None:
    from neo4j import GraphDatabase

    entity_types = {entity["id"]: entity["entity_type"] for entity in records["entities"]}
    captions = {doc["source_id"]: post_caption(doc["text"], doc["source_id"])
                for doc in records["documents"]}
    post_numbers = post_numbers if post_numbers is not None else assign_post_numbers({}, records["documents"])
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        kwargs = {"database_": database} if database else {}
        for label in ("Post", "Topic", "Project", "Feature", "Concept", "Assertion", "Evidence"):
            driver.execute_query(f"CREATE CONSTRAINT w6_{label.lower()}_id IF NOT EXISTS "
                                 f"FOR (n:{label}) REQUIRE n.id IS UNIQUE", **kwargs)
        for entity in records["entities"]:
            label = entity["entity_type"]
            if label not in ("Post", "Topic", "Project", "Feature", "Concept"):
                raise ValueError(f"알 수 없는 엔티티 유형: {label}")
            driver.execute_query(f"""MERGE (n:{label} {{id: $id}})
                SET n.name = $name, n.display_name = $display_name,
                    n.post_number = $post_number, n.source_id = $source_id,
                    n.corpus = $corpus, n.published_at = $published_at,
                    n.collected_at = $collected_at, n.permalink = $permalink,
                    n.selection_score = $selection_score, n.observed_likes = $observed_likes,
                    n.observed_comments = $observed_comments""",
                id=entity["id"], name=entity["name"],
                display_name=display_name_for_entity(entity, captions, post_numbers),
                post_number=(f"게시글 {post_numbers[entity['source_id']]}"
                             if label == "Post" and entity["corpus"] == "own" else None),
                source_id=entity["source_id"], corpus=entity["corpus"],
                published_at=entity["published_at"].isoformat() if entity["published_at"] else None,
                collected_at=entity["collected_at"].isoformat() if entity["collected_at"] else None,
                permalink=entity["permalink"], selection_score=entity["selection_score"],
                observed_likes=entity["observed_likes"], observed_comments=entity["observed_comments"], **kwargs)
            if label == "Post":
                role = "OwnPost" if entity["corpus"] == "own" else "ReferencePost"
                other = "ReferencePost" if role == "OwnPost" else "OwnPost"
                driver.execute_query(f"MATCH (n:Post {{id: $id}}) SET n:{role} REMOVE n:{other}",
                                     id=entity["id"], **kwargs)
        for edge in records["edges"]:
            subject_label = entity_types[edge["subject_id"]]
            driver.execute_query(f"""MATCH (s:{subject_label} {{id: $subject_id}})
                MERGE (a:Assertion {{id: $id}})
                SET a.predicate = $predicate, a.object_literal = $object_literal,
                    a.display_name = $predicate
                MERGE (a)-[:SUBJECT]->(s)""", **edge, **kwargs)
            if edge["object_id"] is not None:
                object_label = entity_types[edge["object_id"]]
                relation = PRESENTATION_FACTS[edge["predicate"]]
                driver.execute_query(f"""MATCH (s:{subject_label} {{id: $subject_id}}),
                    (o:{object_label} {{id: $object_id}}), (a:Assertion {{id: $id}})
                    MERGE (s)-[r:{relation} {{source_fact_id: $id}}]->(o)
                    SET r.provenance = 'caption_evidence'
                    MERGE (a)-[:OBJECT]->(o)""", **edge, **kwargs)
        for item in records["evidence"]:
            driver.execute_query("""MATCH (a:Assertion {id: $edge_id}), (p:Post {source_id: $source_id})
                MERGE (e:Evidence {id: $id})
                SET e.quote = $quote, e.start_offset = $start, e.end_offset = $end,
                    e.source_id = $source_id, e.display_name = $quote
                MERGE (e)-[:SUPPORTS]->(a)
                MERGE (e)-[:SOURCE_POST]->(p)""", **item, **kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/kdyann/processed/content_graph/w6-reviewed")
    parser.add_argument("--config", type=Path, default=LAB / "interests.json")
    parser.add_argument("--post-numbers", type=Path, default=LAB / "own_post_numbers.json")
    parser.add_argument("--target", choices=("neo4j", "postgres", "both"), default="both")
    args = parser.parse_args()
    documents = _read_jsonl(args.output / "documents.jsonl")
    facts = _read_jsonl(args.output / "facts.jsonl")
    validate_reference_records(documents, facts)
    records = prepare(documents, facts)
    existing_numbers = json.loads(args.post_numbers.read_text(encoding="utf-8")) if args.post_numbers.exists() else {}
    post_numbers = assign_post_numbers(existing_numbers, records["documents"])
    if post_numbers != existing_numbers:
        args.post_numbers.write_text(json.dumps(post_numbers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.target in ("postgres", "both"):
        load_postgres(records, os.environ.get("PG_DSN", "postgresql://kg:kg@127.0.0.1:5432/kg"))
    if args.target in ("neo4j", "both"):
        password = os.environ.get("NEO4J_PASSWORD")
        if not password:
            parser.error("NEO4J_PASSWORD 환경 변수가 필요합니다.")
        config = load_config(args.config)
        uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        database = os.environ.get("NEO4J_DATABASE")
        enrich_graph(config, uri, user, password, database, records["documents"])
        load_unified(records, uri, user, password, database, post_numbers)
        enrich_graph(config, uri, user, password, database, records["documents"])
    print(json.dumps({key: len(value) for key, value in records.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
