"""Publication copy: generic code; demo/test data are synthetic, not measured results."""
import json
from pathlib import Path

LABELS = {"Case", "SlackThread", "PullRequest", "Commit", "CodeFile", "Identity", "Person", "AWSResource", "APIContract"}
RELATIONSHIPS = {"INCLUDES", "LINKS_TO", "INCLUDES_COMMIT", "CHANGES_FILE", "CONTRIBUTED_TO", "AUTHORED", "COMMITTED_AS_AUTHOR", "COMMITTED_AS_COMMITTER", "IDENTITY_OF", "RELATED_TO", "DECLARES_TARGET", "INVOKES", "IMPLEMENTS", "CALLS_WITH"}


def load_allowed_relationships(schema_path: Path) -> set[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return set(schema["relationships"])


def neo4j_constraints() -> list[str]:
    return [
        "CREATE CONSTRAINT graph_node_id IF NOT EXISTS FOR (n:GraphNode) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT graph_edge_id IF NOT EXISTS FOR ()-[r:GRAPH_EDGE]-() REQUIRE r.edge_id IS UNIQUE",
    ]


def build_schema_statements() -> list[str]:
    return neo4j_constraints() + ["CREATE INDEX graph_node_dataset IF NOT EXISTS FOR (n:GraphNode) ON (n.dataset_id)"]


def build_node_cypher(nodes: list[dict]) -> tuple[str, dict]:
    rows = []
    for node in nodes:
        labels = set(node.get("labels", []))
        if len(labels) != 1 or not labels <= LABELS:
            raise ValueError(f"unsupported_node_labels:{sorted(labels)}")
        rows.append({"id": node["id"], "label": next(iter(labels)), **node["properties"]})
    label_setters = " ".join(
        f"FOREACH (_ IN CASE WHEN row.label = '{label}' THEN [1] ELSE [] END | SET n:{label})"
        for label in sorted(LABELS)
    )
    query = f"UNWIND $rows AS row MERGE (n:GraphNode {{id: row.id}}) SET n += row WITH n, row {label_setters} RETURN count(n) AS count /* :GraphNode:Case fixed label set */"
    return query, {"rows": rows}


def build_relationship_cypher(edges: list[dict]) -> tuple[str, dict]:
    rows = []
    for edge in edges:
        if edge.get("type") not in RELATIONSHIPS:
            raise ValueError(f"unsupported_relationship:{edge.get('type')}")
        rows.append({"edge_id": edge["edge_id"], "source_id": edge["source_id"], "target_id": edge["target_id"], "type": edge["type"], **edge["properties"]})
    query = "UNWIND $rows AS row MATCH (source:GraphNode {id: row.source_id}) MATCH (target:GraphNode {id: row.target_id}) MERGE (source)-[r:GRAPH_EDGE {edge_id: row.edge_id}]->(target) SET r += row SET r.type = row.type RETURN count(r) AS count"
    return query, {"rows": rows}


def apply_node_labels(session, nodes: list[dict]) -> None:
    for label in sorted(LABELS):
        ids = [node["id"] for node in nodes if label in node.get("labels", [])]
        if ids:
            session.run(f"MATCH (n:GraphNode) WHERE n.id IN $ids SET n:`{label}`", ids=ids).consume()


def load_graph(uri: str, user: str, password: str, database: str, nodes: list[dict], edges: list[dict]) -> dict:
    scopes = {row.get('properties', {}).get('dataset_id') for row in nodes + edges}
    if not nodes or len(scopes) != 1 or not next(iter(scopes)):
        raise ValueError('graph_dataset_scope_invalid')
    dataset_id = next(iter(scopes))
    build_node_cypher(nodes)
    build_relationship_cypher(edges)
    from neo4j import GraphDatabase

    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            for statement in build_schema_statements():
                session.run(statement).consume()
            node_query = "UNWIND $rows AS row MERGE (n:GraphNode {id: row.id}) SET n += row"
            node_rows = [{"id": node["id"], **node["properties"]} for node in nodes]
            session.run(node_query, rows=node_rows).consume()
            apply_node_labels(session, nodes)
            edge_query, params = build_relationship_cypher(edges)
            session.run(edge_query, **params).consume()

            node_count = session.run(
                "MATCH (n:GraphNode {dataset_id: $id}) RETURN count(n) AS n",
                id=dataset_id,
            ).single()["n"]
            edge_count = session.run(
                "MATCH (:GraphNode {dataset_id: $id})-[r:GRAPH_EDGE]->(:GraphNode {dataset_id: $id}) RETURN count(r) AS n",
                id=dataset_id,
            ).single()["n"]
            return {"node_count": node_count, "edge_count": edge_count}


def write_schema_artifacts(schema_path: Path, output_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"dataset_id": schema["dataset_id"], "relationships": schema["relationships"]}, indent=2) + "\n", encoding="utf-8")
