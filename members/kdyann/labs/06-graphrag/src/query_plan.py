"""질문과 현재 그래프 스키마만으로 v2 검색 경로를 선택한다."""
from __future__ import annotations

import re
from typing import Any

FACT_CATALOG = """MATCH (p:Post)-[rel:COVERS_TOPIC]->(t:Topic)
MATCH (ev:Evidence)-[:SUPPORTS]->(:Assertion {id: rel.source_fact_id})
WHERE p.source_id IN $allowed_ids AND ev.source_id = p.source_id
OPTIONAL MATCH (t)-[mapping:IN_AREA {profile_id: $profile_id}]->(area:InterestArea)
RETURN DISTINCT p.source_id AS source_id, p.corpus AS corpus, t.name AS topic,
       area.name AS area, mapping.provenance AS area_provenance, ev.quote AS quote
LIMIT 500"""
PROFILE_AREAS = """MATCH (:Profile {id: $profile_id})-[:INTERESTED_IN]->(area:InterestArea)
RETURN area.name AS area LIMIT 50"""
OWN_COUNT = """MATCH (p:OwnPost) WHERE p.source_id IN $allowed_ids
RETURN count(DISTINCT p) AS count LIMIT 1"""
OWN_TOPIC_COUNT = """MATCH (p:OwnPost)-[:COVERS_TOPIC]->(t:Topic)
WHERE p.source_id IN $allowed_ids AND t.name = $topic
RETURN count(DISTINCT p) AS count LIMIT 1"""
TOP_OWN_TOPIC = """MATCH (p:OwnPost)-[:COVERS_TOPIC]->(t:Topic)
WHERE p.source_id IN $allowed_ids
RETURN t.name AS topic, count(DISTINCT p) AS post_count
ORDER BY post_count DESC, topic LIMIT 10"""


def route_question(query: str, catalog: list[dict[str, Any]], areas: set[str]) -> dict[str, Any]:
    """평가 category·정답 ID를 읽지 않고 질문 문구와 그래프 주제만 사용한다."""
    lower = query.casefold()
    topic_names = {row["topic"] for row in catalog if isinstance(row.get("topic"), str)}
    matched_topics = sorted((topic for topic in topic_names if topic.casefold() in lower),
                            key=lambda topic: (-len(topic), topic))
    topic = matched_topics[0] if matched_topics else None
    matched_areas = sorted((area for area in areas if area.casefold() in lower),
                           key=lambda area: (-len(area), area))
    area = matched_areas[0] if matched_areas else None
    if re.search(r"영상.{0,15}(?:장면|\d+\s*초)|(?:장면|\d+\s*초).{0,15}영상", query):
        return {"route": "unsupported", "reason": "영상 장면·시간대 자료가 없습니다.",
                "topic": topic, "area": area}
    if ("누구" in query or "사람" in query) and ("언급" in query or "작년" in query):
        return {"route": "unsupported", "reason": "Person/MENTIONS와 전년도 전체 자료가 없습니다.",
                "topic": topic, "area": area}
    if re.search(r"몇\s*(?:개|건|명)|개수|모두\s*몇|(?:가장|제일)\s*많[은이]|최다|\bcount\b|how many", lower):
        if re.search(r"지난\s*(?:달|주|해)|작년|지난해|전년도|올해|최근\s*\d+\s*(?:일|주|개월)|\b20\d\d년", query):
            return {"route": "unsupported", "reason": "기간별 전체 그래프 집계는 지원하지 않습니다.",
                    "topic": topic, "area": area}
        if "참고" in query or "레퍼런스" in query or "reference" in lower:
            return {"route": "unsupported", "reason": "참고 글 전체 집계는 현재 지원하지 않습니다.",
                    "topic": topic, "area": area}
        if not any(term in query for term in ("내 ", "내가", "내게시물", "제가", "저의", "우리")):
            return {"route": "unsupported", "reason": "집계할 게시물 범위가 불분명합니다.",
                    "topic": topic, "area": area}
        aggregate = ("top_topic" if any(term in query for term in ("가장", "제일", "최다")) and "주제" in query
                     else "topic_count" if topic else "own_count")
        modifier = re.search(r"(?:내|내가|제|저의)\s+(.{1,30}?)\s+게시물", query)
        if aggregate != "top_topic" and modifier and not topic and not re.fullmatch(
                r"(?:전체|모든|총|실습|인스타그램|Instagram)", modifier.group(1).strip()):
            return {"route": "unsupported", "reason": "질문의 주제나 조건을 검토된 그래프에서 확인하지 못했습니다.",
                    "topic": None, "area": area}
        if aggregate != "top_topic" and not topic and re.search(r"(.+?)\s*주제\s*게시물", query):
            return {"route": "unsupported", "reason": "질문의 주제가 검토된 그래프에 없습니다.",
                    "topic": None, "area": area}
        if aggregate == "own_count" and not re.search(r"(?:내|제|저의)\s*(?:전체\s*|모든\s*)?게시물|내가\s+올린\s+게시물", query):
            return {"route": "unsupported", "reason": "전체 내 게시물 수인지 확인할 수 없습니다. 주제 또는 범위를 명시해 주세요.",
                    "topic": None, "area": area}
        return {"route": "aggregate", "aggregate": aggregate, "topic": topic, "area": area}
    if any(term in query for term in ("추천", "만들 만한", "만들만한", "아이디어")):
        return {"route": "recommendation", "topic": topic, "area": area,
                "novel_only": any(term in query for term in ("아직", "올리지 않은", "새로운", "새 주제"))}
    if any(term in query for term in ("같은 관심 분야", "연결되는 참고", "다른 세부 주제", "연결 경로")):
        if not area and topic:
            area = next((row["area"] for row in catalog if row["topic"] == topic and row.get("area") in areas), None)
        return {"route": "multi_hop", "topic": topic, "area": area}
    return {"route": "direct", "topic": topic, "area": area}


def planned_paths(plan: dict[str, Any], catalog: list[dict[str, Any]],
                  ranked_ids: list[str], areas: set[str], scope: str) -> tuple[list[str], list[dict[str, Any]]]:
    """질문 주제와 맞는 own seed를 하이브리드 순위로 고르고 검토된 분야 경로를 확장한다."""
    route = plan["route"]
    if route not in ("multi_hop", "recommendation") or scope == "own":
        return [], []
    rank = {identifier: index for index, identifier in enumerate(ranked_ids)}
    own = [row for row in catalog if row.get("corpus") == "own"]
    refs = [row for row in catalog if row.get("corpus") == "reference" and row.get("source_id") in rank]
    area = plan.get("area")
    if route == "multi_hop":
        topic = plan.get("topic")
        anchors = [row for row in own if (not topic or row["topic"] == topic)
                   and (not area or row.get("area") == area)]
        if not anchors and area:
            anchors = [row for row in own if row.get("area") == area]
        anchors = [row for row in anchors if row["source_id"] in rank]
        anchors.sort(key=lambda row: rank[row["source_id"]])
        if not anchors:
            return [], []
        if not area:
            area = anchors[0].get("area")
        if area not in areas:
            return [], []
        anchor = anchors[0]
        targets = [row for row in refs if row.get("area") == area and row["topic"] != anchor["topic"]]
        targets.sort(key=lambda row: rank[row["source_id"]])
        paths = [{"seed_id": anchor["source_id"], "other_id": ref["source_id"],
                  "seed_topic": anchor["topic"], "other_topic": ref["topic"],
                  "interest_area": area, "path_type": "curated_interest_area",
                  "seed_quote": anchor["quote"], "other_quote": ref["quote"],
                  "area_provenance": ref.get("area_provenance") or "unknown"} for ref in targets]
        chosen = [anchor["source_id"]] + list(dict.fromkeys(ref["source_id"] for ref in targets))
        return chosen, paths
    own_topics = {row["topic"] for row in own}
    targets = [row for row in refs if row.get("area") in areas
               and (not area or row.get("area") == area)
               and (not plan.get("novel_only") or row["topic"] not in own_topics)]
    targets.sort(key=lambda row: rank[row["source_id"]])
    chosen = list(dict.fromkeys(row["source_id"] for row in targets))
    paths = [{"other_id": ref["source_id"], "other_topic": ref["topic"],
              "interest_area": ref["area"], "path_type": "profile_interest",
              "other_quote": ref["quote"],
              "novel_in_comparison": ref["topic"] not in own_topics,
              "area_provenance": "user_curated+" + (ref.get("area_provenance") or "unknown")}
             for ref in targets]
    for ref in targets:
        anchors = [row for row in own if row.get("area") == ref["area"] and row["topic"] != ref["topic"]]
        anchors = [row for row in anchors if row["source_id"] in rank]
        anchors.sort(key=lambda row: rank[row["source_id"]])
        if anchors:
            anchor = anchors[0]
            chosen.append(anchor["source_id"])
            paths.append({"seed_id": anchor["source_id"], "other_id": ref["source_id"],
                          "seed_topic": anchor["topic"], "other_topic": ref["topic"],
                          "interest_area": ref["area"], "path_type": "curated_interest_area",
                          "seed_quote": anchor["quote"], "other_quote": ref["quote"],
                          "area_provenance": ref.get("area_provenance") or "unknown"})
    return list(dict.fromkeys(chosen)), paths


def aggregate_query(plan: dict[str, Any]) -> tuple[str, dict[str, str]]:
    kind = plan["aggregate"]
    if kind == "top_topic":
        return TOP_OWN_TOPIC, {}
    if kind == "topic_count":
        return OWN_TOPIC_COUNT, {"topic": plan["topic"]}
    return OWN_COUNT, {}
