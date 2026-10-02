#!/usr/bin/env python3
"""1) 청크에서 트리플을 추출하고, 2) Postgres/Neo4j 로더가 같이 쓸 그래프 자료구조로 조립한다.

Period·Activity·Document·Organization과 그 사이 관계(hasDocument·occursInPeriod·
relatedToOrganization·status·activityKind·activityScope)는 노션 폴더 경로와 본문의
Status/type 필드만 보면 결정적으로 알 수 있어 코드로 직접 뽑는다. Topic(schema:about)만
본문을 읽어야 아는 의미 정보라 LLM으로 {subject, predicate, object} 트리플을 뽑는다.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DEFAULT_MODEL, LAB_ROOT, call_openai_json, load_documents

TTL_PATH = LAB_ROOT / "data" / "graph.ttl"
PERIOD_FOLDERS = {"2026 1학기", "2026 2학기", "2026 Winter", "2026 여름방학"}
ORGANIZATIONS = {"KB 국민은행", "Naver", "리코", "페이타랩", "필드유"}
ACTIVITY_KIND_VALUES = {"공부", "프로젝트", "수업", "취업 준비"}
ACTIVITY_SCOPE_VALUES = {"개인", "덕성", "대외"}

STATUS_RE = re.compile(r"Status:\s*([^\n]+?)(?:\s+type:|\s*$)")
TYPE_RE = re.compile(r"\btype:\s*([^\n]+)")

TOPIC_INSTRUCTIONS = """당신은 텍스트에서 RDF 트리플을 뽑는 추출기입니다.
아래 닫힌 스키마의 술어만 쓰세요: schema:about (Document의 대표 주제 → Topic)

주어진 문서 제목·본문에서 이 술어로 표현되는 트리플의 object(Topic)를 5단어 이내로 뽑으세요.
문서에 실제로 없는 내용은 지어내지 마세요. subject와 predicate는 호출한 쪽에서 이미 정해져 있으니
object 값만 판단하면 됩니다.

JSON만 출력하세요: {"subject": "<활동명>", "predicate": "schema:about", "object": "<5단어 이내 주제>"}"""


@dataclass
class Entity:
    id: str
    types: list[str]
    name: str


@dataclass
class Edge:
    subject_id: str
    predicate: str
    object_id: str | None = None
    object_literal: str | None = None
    source: str | None = None  # 근거: 원본 노션 페이지 상대 경로


@dataclass
class Graph:
    entities: dict[str, Entity] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def add_entity(self, entity_id: str, type_: str, name: str) -> None:
        existing = self.entities.get(entity_id)
        if existing:
            if type_ not in existing.types:
                existing.types.append(type_)
        else:
            self.entities[entity_id] = Entity(entity_id, [type_], name)

    def add_edge(self, subject_id: str, predicate: str, *, object_id=None, object_literal=None, source=None) -> None:
        self.edges.append(Edge(subject_id, predicate, object_id, object_literal, source))


def period_and_activity(source: str, title: str) -> tuple[str | None, str, str | None]:
    """경로에서 Period·Activity·Organization을 결정적으로 뽑는다 (LLM 불필요).

    회사 폴더(예: Naver)는 Activity 이름을 "Naver 지원 준비"로 두고, 조직 자체는
    별도로 반환해 relatedToOrganization으로 연결한다 — 조직과 활동은 다른 개체다.
    """
    parts = source.split("/")
    if len(parts) < 2:
        return None, title, None

    domain = parts[1]
    if domain == "덕성":
        activity = f"덕성 {parts[2]}" if len(parts) > 2 else "덕성"
        return None, activity, None

    if domain == "2026":
        if len(parts) > 2 and parts[2] in PERIOD_FOLDERS:
            period = parts[2]
            activity = parts[3] if len(parts) > 4 else title
            return period, activity, None
        folder = parts[2] if len(parts) > 3 else title
        if folder in ORGANIZATIONS:
            return None, f"{folder} 지원 준비", folder
        return None, folder, None

    return None, title, None


def slug(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", text).strip("_") or "x"


def parse_status_and_type(content: str) -> tuple[str | None, list[str], list[str]]:
    """본문의 'Status: ...', 'type: ...' 필드를 파싱한다. type은 콤마로 여러 값이
    같이 올 수 있고(예: "대외, 프로젝트"), 활동 종류/범위 어휘 목록으로 분리한다.
    둘 다 아닌 값(예: "돈 :)")은 닫힌 스키마 밖이라 버린다."""
    status_match = STATUS_RE.search(content)
    status = status_match.group(1).strip() if status_match else None

    kinds: list[str] = []
    scopes: list[str] = []
    type_match = TYPE_RE.search(content)
    if type_match:
        for token in type_match.group(1).split(","):
            token = token.strip()
            if token in ACTIVITY_KIND_VALUES:
                kinds.append(token)
            elif token in ACTIVITY_SCOPE_VALUES:
                scopes.append(token)
    return status, kinds, scopes


def group_by_activity(documents: list[dict]) -> dict[tuple[str | None, str, str | None], list[dict]]:
    pages: dict[str, dict] = {d["page_id"]: d for d in documents}
    groups: dict[tuple[str | None, str, str | None], list[dict]] = {}
    for page in pages.values():
        period, activity, org = period_and_activity(page["source"], page["title"])
        groups.setdefault((period, activity, org), []).append(page)
    return groups


def extract_activity_topic(activity: str, pages: list[dict], api_key: str, model: str) -> dict:
    """Activity당 한 번만 LLM을 불러 {subject, predicate, object} 트리플을 뽑는다."""
    listing = "\n".join(f"- {p['title']}: {' '.join(p['content'].split())[:150]}" for p in pages[:5])
    input_text = f"활동: {activity}\n문서 목록:\n{listing}"
    return call_openai_json(TOPIC_INSTRUCTIONS, input_text, api_key, model)


def build_graph(
    groups: dict[tuple[str | None, str, str | None], list[dict]],
    topics: dict[str, str],
) -> Graph:
    graph = Graph()

    for (period, activity, org), pages in groups.items():
        activity_id = f"activity_{slug(activity)}"
        graph.add_entity(activity_id, "Activity", activity)

        status, kinds, scopes = (None, [], [])
        dual_typed = False
        if len(pages) == 1:
            status, kinds, scopes = parse_status_and_type(pages[0]["content"])
            if status or kinds or scopes:
                dual_typed = True
                # add_entity()를 거쳐야 같은 activity_id로 합쳐지는 경우(예: "git 정리"가
                # 1학기·Winter 두 기간에 걸쳐 있는 경우)에도 :Document가 중복 추가되지 않는다.
                graph.add_entity(activity_id, "Document", activity)

        if status:
            graph.add_edge(activity_id, "status", object_literal=status, source=pages[0]["source"])
        for kind in kinds:
            graph.add_edge(activity_id, "activityKind", object_literal=kind, source=pages[0]["source"])
        for scope in scopes:
            graph.add_edge(activity_id, "activityScope", object_literal=scope, source=pages[0]["source"])

        if org:
            org_id = f"org_{slug(org)}"
            graph.add_entity(org_id, "Organization", org)
            graph.add_edge(activity_id, "relatedToOrganization", object_id=org_id)

        if period:
            period_id = f"period_{slug(period)}"
            graph.add_entity(period_id, "Period", period)
            graph.add_edge(activity_id, "occursInPeriod", object_id=period_id)

        topic = topics.get(activity)
        if dual_typed:
            if topic:
                graph.add_edge(activity_id, "schema:about", object_literal=topic, source=pages[0]["source"])
            graph.add_edge(activity_id, "hasDocument", object_id=activity_id)
        else:
            for page in pages:
                doc_id = f"doc_{slug(page['page_id'])}"
                graph.add_entity(doc_id, "Document", page["title"])
                if topic:
                    graph.add_edge(doc_id, "schema:about", object_literal=topic, source=page["source"])
                graph.add_edge(activity_id, "hasDocument", object_id=doc_id, source=page["source"])

    return graph


def write_turtle(graph: Graph, path: Path) -> None:
    lines = [
        "@prefix : <https://example.org/kb-lab/> .",
        "@prefix schema: <https://schema.org/> .",
        "",
    ]
    for entity in graph.entities.values():
        name = entity.name.replace('"', "'")
        types = ", ".join(f":{t}" for t in entity.types)
        lines.append(f':{entity.id} a {types} ; schema:name "{name}" .')
    lines.append("")
    for edge in graph.edges:
        predicate = edge.predicate if edge.predicate.startswith("schema:") else f":{edge.predicate}"
        if edge.object_id:
            lines.append(f":{edge.subject_id} {predicate} :{edge.object_id} .")
        else:
            value = str(edge.object_literal).replace('"', "'")
            lines.append(f':{edge.subject_id} {predicate} "{value}" .')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="청크에서 트리플을 추출해 Turtle로 내보냅니다.")
    parser.add_argument("--model", help="OpenAI 모델; 기본값 gpt-4.1-mini")
    parser.add_argument("--output", type=Path, default=TTL_PATH)
    parser.add_argument("--dry-run", action="store_true", help="OpenAI 없이 구조만 출력")
    args = parser.parse_args()

    groups = group_by_activity(load_documents())

    if args.dry_run:
        for (period, activity, org), pages in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            org_note = f" [조직: {org}]" if org else ""
            print(f"[{period or '-'}] {activity}{org_note}  (페이지 {len(pages)}개)")
        return

    from common import get_env

    api_key = get_env("OPENAI_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY가 없습니다. 레포 루트 .env에 설정하세요.")
    model = args.model or get_env("OPENAI_MODEL", DEFAULT_MODEL)

    topics: dict[str, str] = {}
    for (period, activity, org), pages in groups.items():
        triple = extract_activity_topic(activity, pages, api_key, model)
        print(f"  추출된 트리플: {triple}")
        topics[activity] = str(triple["object"]).strip()
        print(f"[{period or '-'}] {activity} -> {topics[activity]}  ({len(pages)}개 Document에 복사)")

    graph = build_graph(groups, topics)
    write_turtle(graph, args.output)
    print(f"\n엔티티 {len(graph.entities)}개, 엣지 {len(graph.edges)}개를 {args.output}에 저장했습니다.")


if __name__ == "__main__":
    main()
