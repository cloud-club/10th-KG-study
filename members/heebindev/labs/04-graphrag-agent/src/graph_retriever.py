import json
from pathlib import Path

from common import LAB_DIR, neo4j_query


ALL_RELATIONS = """
MATCH (subject:Entity)-[relation]->(object:Entity)
RETURN subject.name AS subject,
       type(relation) AS predicate,
       object.name AS object,
       coalesce(relation.evidence, []) AS evidence,
       coalesce(relation.chunk_ids, []) AS chunk_ids
"""


def load_review_queue(path: Path | None = None) -> set[tuple[str, str, str]]:
    path = path or LAB_DIR / "review_queue.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    return {
        (item["subject"], item["predicate"], item["object"])
        for item in items
        if item.get("status") is None
    }


def retrieve_graph_context(
    question: str,
    chunk_ids: list[str],
    limit: int = 5,
) -> tuple[list[dict], list[dict]]:
    relations = neo4j_query(ALL_RELATIONS)
    review_signatures = load_review_queue()
    question_lower = question.casefold()
    chunk_id_set = set(chunk_ids)
    ranked = []
    excluded = []

    for relation in relations:
        signature = (
            relation["subject"],
            relation["predicate"],
            relation["object"],
        )
        if signature in review_signatures:
            excluded.append(relation)
            continue

        score = 0
        overlap = chunk_id_set.intersection(relation.get("chunk_ids") or [])
        if overlap:
            score += 2
        for name in (relation["subject"], relation["object"]):
            if len(name.strip()) >= 2 and name.casefold() in question_lower:
                score += 3
        if score:
            relation["retrieval_score"] = score
            ranked.append(relation)

    ranked.sort(
        key=lambda item: (
            -item["retrieval_score"],
            item["subject"],
            item["predicate"],
            item["object"],
        )
    )
    return ranked[:limit], excluded


def format_graph_context(relations: list[dict]) -> str:
    if not relations:
        return "검색된 그래프 관계 없음"
    lines = []
    for index, relation in enumerate(relations, 1):
        evidence = relation.get("evidence") or []
        evidence_text = evidence[0] if evidence else "근거 없음"
        lines.append(
            f"[G{index}] {relation['subject']} -{relation['predicate']}-> "
            f"{relation['object']}\n근거: {evidence_text}"
        )
    return "\n\n".join(lines)
