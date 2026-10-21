"""개인 지식그래프 조회 도구 — MCP 서버(mcp_server.py)가 감싸는 순수 함수 모음.

원칙
- LLM을 부르지 않는다. 데이터와 근거만 돌려주고 답은 대화 중인 AI가 만든다.
- 모든 결과에 chunk_id · 문서 경로 · evidence를 붙인다.
- 읽기 전용. Postgres는 READ ONLY 트랜잭션, Neo4j는 READ_ACCESS + execute_read.
- 그래프 도구는 기본적으로 1차 문서 근거만 쓴다(edge.source_tier != 'secondary').
  문서 검색은 전체 코퍼스를 쓰고, 결과마다 source_tier를 표시한다.

검색(v1)·그래프 확장(v2.1)·Cypher 보안 장치는 기존 모듈을 그대로 호출한다.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

# 임베딩 모델은 로컬 캐시만 쓴다. 질의 시점에 허브로 나가지 않게 가장 먼저 고정한다.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import psycopg  # noqa: E402
from neo4j import GraphDatabase, READ_ACCESS  # noqa: E402
from neo4j.exceptions import Neo4jError  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

import graph_retriever as graph  # noqa: E402
import text2cypher as tc  # noqa: E402
from common import LAB, PG_DSN, active_runtime, load_chunks_by_id  # noqa: E402
from hybrid_search import hybrid_search  # noqa: E402
from run_v21_x01 import rank_candidates  # noqa: E402

SNIPPET_CHARS = 600      # 검색 결과 원문 미리보기
CONTEXT_CHARS = 900      # explore_graph가 돌려주는 청크 원문 상한
EVIDENCE_CHARS = 300     # 그래프 사실의 evidence 상한
MAX_TOP_K = 20
MAX_CYPHER_CHARS = 4000
PRIMARY = "source_tier IS DISTINCT FROM 'secondary'"

# 한글·별칭 표기 → DB의 Technology 라벨(소문자). DB에 없는 라벨로 보내면 정규화 실패로 처리된다.
TECH_ALIASES = {
    "레디스": "redis", "도커": "docker", "도커 컴포즈": "docker compose", "도커컴포즈": "docker compose",
    "쿠버네티스": "kubernetes", "k8s": "kubernetes", "카프카": "kafka", "래빗엠큐": "rabbitmq",
    "그라파나": "grafana", "프로메테우스": "prometheus", "로키": "loki", "템포": "tempo",
    "스프링": "spring", "스프링 부트": "spring boot", "스프링부트": "spring boot", "springboot": "spring boot",
    "깃허브 액션": "github actions", "깃허브액션": "github actions", "깃헙 액션": "github actions",
    "자바": "java", "마이에스큐엘": "mysql", "파이어베이스": "firebase", "패스트api": "fastapi",
    "플라스크": "flask", "멤캐시드": "memcached", "주스탠드": "zustand", "리액트 쿼리": "react query",
    "오픈서치": "opensearch", "키바나": "kibana", "카프카 커넥트": "kafka",
}
# 프로젝트 표기 → 그래프 id
PROJECT_ALIASES = {
    "secause": "kg:secause", "세코즈": "kg:secause",
    "teamficial": "kg:teamficial", "팀피셜": "kg:teamficial",
    "jikhaeng": "kg:jikhaeng", "직행": "kg:jikhaeng",
    "cheongbaji": "kg:cheongbaji", "청바지": "kg:cheongbaji",
    "moandi": "kg:moandi", "모앤디": "kg:moandi",
}
STATUS_KO = {"implemented": "구현됨", "proposed": "제안만", "not_implemented": "미구현"}


# ─── 연결 ────────────────────────────────────────────────────────────────

def _env_file() -> dict[str, str]:
    """lab/.env에서 Neo4j 접속 정보만 읽는다. 값은 어디에도 출력하지 않는다."""
    path = LAB / ".env"
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name.startswith("NEO4J_"):
                values[name] = value.strip().strip("\"'")
    return values


def graph_schema() -> str:
    schema = active_runtime().get("graph_schema", "public")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
        raise ValueError("잘못된 그래프 스키마 이름")
    return schema


def _pg():
    conn = psycopg.connect(os.getenv("POSTGRES_DSN", PG_DSN), row_factory=dict_row)
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    return conn


@lru_cache(maxsize=1)
def _driver():
    env = _env_file()
    # 활성 런타임(active_corpus.json)의 그래프가 우선이다. .env의 NEO4J_URI는 v0 그래프를 가리킬 수 있다.
    uri = os.getenv("KG_NEO4J_URI") or active_runtime().get("neo4j_uri") or env.get("NEO4J_URI") \
        or "bolt://localhost:7687"
    user = os.getenv("NEO4J_USER") or env.get("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD") or env.get("NEO4J_PASSWORD")
    if not password:
        raise ValueError("NEO4J_PASSWORD 없음 (.env 또는 환경변수)")
    return GraphDatabase.driver(uri, auth=(user, password))


def _neo4j_session():
    database = os.getenv("NEO4J_DATABASE") or _env_file().get("NEO4J_DATABASE", "neo4j")
    return _driver().session(database=database, default_access_mode=READ_ACCESS)


@lru_cache(maxsize=1)
def _corpus() -> dict[str, dict]:
    return load_chunks_by_id()


# ─── 근거 표기 ────────────────────────────────────────────────────────────

def _cut(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _evidence(chunk_id: str, evidence: str | None) -> dict:
    row = _corpus().get(chunk_id, {})
    return {
        "chunk_id": chunk_id,
        "document": row.get("document_path") or row.get("source", ""),
        "heading": row.get("heading", ""),
        "source_tier": row.get("source_tier"),
        "evidence": _cut(evidence, EVIDENCE_CHARS),
    }


# ─── 이름 정규화 ──────────────────────────────────────────────────────────

def _slug(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "-", value.lower()).strip("-")


def _technologies() -> list[dict]:
    with _pg() as conn:
        return conn.execute(
            f"SELECT entity_id, label FROM {graph_schema()}.entities WHERE type='Technology' ORDER BY entity_id"
        ).fetchall()


def normalize_technology(name: str, techs: list[dict] | None = None) -> dict:
    """기술 이름을 그래프 id로 바꾼다. 확실한 것만 matched에 넣고, 비슷한 건 related로만 알린다."""
    techs = _technologies() if techs is None else techs
    raw = re.sub(r"\s+", " ", (name or "").strip().lower())
    if not raw:
        raise ValueError("기술 이름이 비었다")
    key = TECH_ALIASES.get(raw, raw)
    target = _slug(key.removeprefix("kg:tech-"))
    matched = [t for t in techs
               if t["entity_id"] == raw or _slug(t["label"]) == target
               or t["entity_id"] == f"kg:tech-{target}"
               or TECH_ALIASES.get(t["label"].lower()) == key]   # 예: '프로메테우스' 노드도 prometheus로 묶음
    seen = {t["entity_id"] for t in matched}
    related = [t for t in techs if t["entity_id"] not in seen and target and target in _slug(t["label"])]
    return {
        "input": name,
        "matched": [{"id": t["entity_id"], "label": t["label"]} for t in matched],
        "related_not_merged": [{"id": t["entity_id"], "label": t["label"]} for t in related][:15],
    }


def normalize_project(name: str | None) -> str | None:
    if name is None or not str(name).strip():
        return None
    raw = str(name).strip().lower()
    if raw.startswith("kg:"):
        return raw
    if raw in PROJECT_ALIASES:
        return PROJECT_ALIASES[raw]
    raise ValueError(f"알 수 없는 프로젝트: {name}. 가능한 값: {sorted(set(PROJECT_ALIASES.values()))}")


# ─── 1. 문서 검색 (v1) ────────────────────────────────────────────────────

def search_documents(query: str, top_k: int = 5) -> dict:
    top_k = max(1, min(int(top_k), MAX_TOP_K))
    corpus = _corpus()
    results = []
    for row in hybrid_search(query, limit=top_k):
        chunk = corpus.get(row["id"], {})
        results.append({
            "rank": row["rank"],
            "chunk_id": row["id"],
            "document": chunk.get("document_path") or row.get("source", ""),
            "title": row.get("title", ""),
            "heading": row.get("heading", ""),
            "source_tier": chunk.get("source_tier"),
            "bm25_rank": row.get("bm25_rank"),
            "vector_rank": row.get("vector_rank"),
            "rrf_score": round(row["rrf_score"], 6),
            "snippet": _cut(row.get("text"), SNIPPET_CHARS),
        })
    return {
        "query": query,
        "method": "v1: Elasticsearch BM25(nori) top-50 + pgvector(bge-m3) top-50 → RRF k=60",
        "scope": "전체 코퍼스(1차·2차 문서 모두). source_tier=secondary는 면접 대비 등 2차 정리 문서",
        "results": results,
    }


# ─── 2. 그래프 탐색 (v2.1) ────────────────────────────────────────────────

def load_primary_graph() -> dict:
    """graph_retriever.load_graph와 같은 모양으로 읽되, 1차 문서 근거 엣지만 남긴다."""
    schema = graph_schema()
    with _pg() as conn:
        entities = conn.execute(
            f"SELECT entity_id,type,label,props FROM {schema}.entities ORDER BY entity_id").fetchall()
        edges = conn.execute(
            f"SELECT id,subject,predicate,object,chunk_id,evidence FROM {schema}.edges "
            f"WHERE {PRIMARY} ORDER BY id").fetchall()
    return {"entities": entities, "edges": edges}


def explore_graph(query: str, top_k: int = 5) -> dict:
    top_k = max(1, min(int(top_k), MAX_TOP_K))
    corpus = _corpus()
    state = load_primary_graph()
    retrieved = hybrid_search(query, limit=top_k)
    top = [r["id"] for r in retrieved]
    expansion = graph.expand(state, set(top))
    candidates = sorted({e["chunk_id"] for e in expansion["support_edges"]} - set(top))
    ranking_note = "회수 후보를 질문과의 bge-m3 코사인 유사도 순으로 정렬 (v2.1)"
    try:
        order = [r["chunk_id"] for r in rank_candidates(query, candidates, corpus)]
    except ValueError as exc:   # 임베딩 누락 등: 후보를 임의로 바꾸지 않고 chunk_id 정렬로 둔다
        order, ranking_note = None, f"유사도 정렬 실패로 chunk_id 정렬 사용: {exc}"
    _context, mapping, trace = graph.assemble_v2(retrieved, state, corpus,
                                                 recovery_order=order, expansion=expansion)
    labels = {n["entity_id"]: n["label"] for n in state["entities"]}
    chunks = [{
        "n": n,
        "chunk_id": row["id"],
        "origin": "search" if row["id"] in top else "graph",
        "document": row.get("document_path") or row.get("source", ""),
        "heading": row.get("heading", ""),
        "source_tier": row.get("source_tier"),
        "text": _cut(row.get("text"), CONTEXT_CHARS),
    } for n, row in mapping.items()]
    facts = [line for line in trace.get("graph_facts_text", "").splitlines()
             if line.strip() and not line.startswith("그래프 파생 사실")]
    return {
        "query": query,
        "method": "v2.1: v1 top-k 청크의 엣지로 진입 → TechnologyUse→Technology←TechnologyUse 2홉, "
                  "이웃 20개 초과 노드는 확장 중단 → 회수 원문 예산 2,200자",
        "graph_scope": "1차 문서 근거 엣지만 (source_tier != secondary)",
        "fallback_v1": trace.get("fallback_v1", False),
        "graph_facts": facts,
        "graph_facts_note": "사실 문장의 [근거 n]은 chunks[].n을 가리킨다. 사실 문장 자체는 원문이 아니다",
        "seed_nodes": [{"id": i, "label": labels.get(i)} for i in trace["seed_nodes"]],
        "expanded_nodes": [{"id": i, "label": labels.get(i)} for i in trace["expanded_nodes"]],
        "skipped_high_degree": trace.get("skipped_high_degree", []),
        "recovery_ranking": ranking_note,
        "budget_dropped_chunks": trace.get("budget_dropped_chunks", []),
        "chunks": chunks,
    }


# ─── 3~5. 구조화 조회 (Postgres 그래프, 1차 근거만) ───────────────────────

def _use_facts(conn, schema: str, use_ids: list[str]) -> dict[str, dict]:
    """사용례별 프로젝트·기술·목적·상태와 각 근거를 모은다."""
    rows = conn.execute(
        f"SELECT subject,predicate,object,chunk_id,evidence FROM {schema}.edges "
        f"WHERE {PRIMARY} AND subject = ANY(%s) "
        "AND predicate IN ('partOf','usesTechnology','hasPurpose','hasStatus') ORDER BY subject,predicate,id",
        (use_ids,)).fetchall()
    labels = {r["entity_id"]: r["label"] for r in conn.execute(
        f"SELECT entity_id,label FROM {schema}.entities WHERE type IN ('Project','Technology')").fetchall()}
    uses: dict[str, dict] = {}
    for r in rows:
        use = uses.setdefault(r["subject"], {"use_id": r["subject"], "projects": [], "technologies": [],
                                             "purposes": [], "statuses": [], "evidence": []})
        value = r["object"]
        if r["predicate"] == "partOf" and value not in [p["id"] for p in use["projects"]]:
            use["projects"].append({"id": value, "label": labels.get(value, value)})
        elif r["predicate"] == "usesTechnology" and value not in [t["id"] for t in use["technologies"]]:
            use["technologies"].append({"id": value, "label": labels.get(value, value)})
        elif r["predicate"] == "hasPurpose" and value not in use["purposes"]:
            use["purposes"].append(value)
        elif r["predicate"] == "hasStatus" and value not in use["statuses"]:
            use["statuses"].append(value)
        use["evidence"].append({"predicate": r["predicate"], **_evidence(r["chunk_id"], r["evidence"])})
    for use in uses.values():
        use["status"] = use["statuses"][0] if len(use["statuses"]) == 1 else (
            "상태 미기재" if not use["statuses"] else "상태 충돌: " + ", ".join(use["statuses"]))
        use["status_ko"] = STATUS_KO.get(use["status"], use["status"])
    return uses


def technology_experience(technology: str) -> dict:
    schema = graph_schema()
    norm = normalize_technology(technology)
    ids = [m["id"] for m in norm["matched"]]
    if not ids:
        return {"normalization": norm, "projects": [],
                "message": "이 이름과 정확히 맞는 기술 노드가 없다. related_not_merged에서 id를 골라 다시 호출할 것"}
    with _pg() as conn:
        use_ids = [r["subject"] for r in conn.execute(
            f"SELECT DISTINCT subject FROM {schema}.edges WHERE {PRIMARY} "
            "AND predicate='usesTechnology' AND object = ANY(%s) ORDER BY subject", (ids,)).fetchall()]
        secondary_only = conn.execute(
            f"SELECT count(DISTINCT subject) AS n FROM {schema}.edges WHERE source_tier='secondary' "
            "AND predicate='usesTechnology' AND object = ANY(%s) AND NOT (subject = ANY(%s))",
            (ids, use_ids)).fetchone()["n"]
        uses = _use_facts(conn, schema, use_ids)
    by_project: dict[str, dict] = {}
    for use in uses.values():
        targets = use["projects"] or [{"id": "unresolved", "label": "프로젝트 미확정"}]
        for p in targets:
            group = by_project.setdefault(p["id"], {"project": p, "uses": []})
            group["uses"].append({k: use[k] for k in ("use_id", "technologies", "purposes", "status",
                                                      "status_ko", "evidence")})
    return {
        "normalization": norm,
        "graph_scope": "1차 문서 근거만",
        "excluded_secondary_only_uses": secondary_only,
        "projects": sorted(by_project.values(), key=lambda g: g["project"]["id"]),
    }


def list_issues(project: str | None = None, technology: str | None = None) -> dict:
    schema = graph_schema()
    project_id = normalize_project(project)
    tech_norm = normalize_technology(technology) if technology else None
    tech_ids = {m["id"] for m in tech_norm["matched"]} if tech_norm else None
    if tech_norm and not tech_ids:
        return {"technology_normalization": tech_norm, "issues": [],
                "message": "기술 이름이 정확히 맞는 노드가 없다. related_not_merged에서 골라 다시 호출할 것"}
    with _pg() as conn:
        occurred = conn.execute(
            f"SELECT subject,object,chunk_id,evidence FROM {schema}.edges WHERE {PRIMARY} "
            "AND predicate='occurredIn' ORDER BY subject,id").fetchall()
        uses = _use_facts(conn, schema, sorted({r["object"] for r in occurred}))
        details = conn.execute(
            f"SELECT subject,predicate,object,chunk_id,evidence FROM {schema}.edges WHERE {PRIMARY} "
            "AND predicate IN ('hasCause','hasFix','hasVerification') ORDER BY subject,predicate,id").fetchall()
        labels = {r["entity_id"]: r["label"] for r in conn.execute(
            f"SELECT entity_id,label FROM {schema}.entities WHERE type='Issue'").fetchall()}
    issues: dict[str, dict] = {}
    for r in occurred:
        use = uses.get(r["object"], {"use_id": r["object"], "projects": [], "technologies": [],
                                     "purposes": [], "status": "상태 미기재"})
        if project_id and project_id not in [p["id"] for p in use["projects"]]:
            continue
        if tech_ids and not tech_ids & {t["id"] for t in use["technologies"]}:
            continue
        issue = issues.setdefault(r["subject"], {"issue_id": r["subject"], "label": labels.get(r["subject"]),
                                                 "occurred_in": [], "cause": [], "fix": [], "verification": [],
                                                 "evidence": []})
        issue["occurred_in"].append({k: use.get(k) for k in ("use_id", "projects", "technologies",
                                                             "purposes", "status")})
        issue["evidence"].append({"predicate": "occurredIn", **_evidence(r["chunk_id"], r["evidence"])})
    field = {"hasCause": "cause", "hasFix": "fix", "hasVerification": "verification"}
    for r in details:
        if r["subject"] in issues:
            issues[r["subject"]][field[r["predicate"]]].append(
                {"value": r["object"], **_evidence(r["chunk_id"], r["evidence"])})
    return {
        "filters": {"project": project_id, "technology": sorted(tech_ids) if tech_ids else None},
        "graph_scope": "1차 문서 근거만",
        "note": "cause/fix/verification이 빈 목록이면 문서에 그 항목이 명시되지 않았다는 뜻이다. 추측해서 채우지 말 것",
        "issues": list(issues.values()),
    }


def proposed_only(project: str | None = None) -> dict:
    schema = graph_schema()
    project_id = normalize_project(project)
    with _pg() as conn:
        status_rows = conn.execute(
            f"SELECT DISTINCT subject,object FROM {schema}.edges WHERE {PRIMARY} AND predicate='hasStatus'"
        ).fetchall()
        proposed = sorted({r["subject"] for r in status_rows if r["object"] == "proposed"})
        implemented = sorted({r["subject"] for r in status_rows if r["object"] == "implemented"})
        facts = _use_facts(conn, schema, proposed + implemented)
    implemented_by_tech: dict[str, set[str]] = {}
    for use_id in implemented:
        use = facts.get(use_id)
        if use and use["status"] == "implemented":
            for t in use["technologies"]:
                implemented_by_tech.setdefault(t["id"], set()).update(p["id"] for p in use["projects"])
    items = []
    for use_id in proposed:
        use = facts[use_id]   # 상태가 충돌하는 사용례도 빼지 않는다. status 필드에 '상태 충돌'로 드러난다
        if project_id and project_id not in [p["id"] for p in use["projects"]]:
            continue
        items.append({**{k: use[k] for k in ("use_id", "projects", "technologies", "purposes", "status",
                                             "evidence")},
                      "same_technology_implemented_in": sorted(
                          {p for t in use["technologies"] for p in implemented_by_tech.get(t["id"], set())})})
    return {
        "filter": {"project": project_id},
        "graph_scope": "1차 문서 근거만",
        "meaning": "status=proposed 사용례. 이 목적으로는 '써봤다/구현했다'고 말하면 안 된다. 단 같은 기술을 다른 "
                   "사용례에서 구현했을 수 있으니(same_technology_implemented_in) 기술 전체를 '안 써봤다'로 일반화하지 말 것",
        "uses": items,
    }


# ─── 6~7. Neo4j 스키마와 읽기 전용 Cypher ─────────────────────────────────

CYPHER_NOTES = [
    "(TechnologyUse)-[:PART_OF]->(Project), (TechnologyUse)-[:USES_TECHNOLOGY]->(Technology), "
    "(Issue)-[:OCCURRED_IN]->(TechnologyUse). 프로젝트와 기술은 TechnologyUse를 거쳐 2개 관계로 이어진다",
    "purpose/status는 TechnologyUse의 문자열 속성이다. Technology 속성이나 관계가 아니다. NULL일 수 있다",
    "status 허용값: implemented / proposed / not_implemented. NULL을 implemented나 proposed로 추정하지 않는다",
    "Issue.cause/fix/verification은 문자열 배열이며 []일 수 있다. 존재 확인은 size(coalesce(i.fix,[]))>0",
    "id·label은 소문자다. 기술 id 형식은 kg:tech-<이름> (예: kg:tech-redis, kg:tech-spring-boot)",
    "같은 사실에 청크별 근거 관계가 여러 개 있다. 개수를 셀 때 count(DISTINCT x.id)를 쓴다",
    "모든 관계에 chunk_id·evidence·source_tier 속성이 있다. 근거는 관계의 chunk_id/evidence로 돌려준다",
    "기본 범위는 1차 문서다. 모든 관계에 WHERE coalesce(r.source_tier,'primary') <> 'secondary'를 건다 "
    "(2차까지 보려면 명시적으로 빼고, 답에 2차 포함이라고 밝힌다)",
    "purpose 조건은 정확 일치보다 CONTAINS로 핵심 단어 하나씩. 여러 단어를 한 문자열 조건에 묶으면 0건이 나기 쉽다",
    "허용: MATCH / OPTIONAL MATCH / WITH로 시작하는 단일 읽기 쿼리. 금지: CALL, APOC, LOAD CSV, USE, 쓰기, 주석, 여러 문장",
    "보안 검사는 단어 단위·대소문자 무시다. 별칭·변수에 use, set, load, call, merge, remove 같은 단어를 쓰면 "
    "읽기 쿼리여도 차단된다 (AS use ✗ → AS use_id ✓)",
    "결과는 최대 200행. 넘으면 실행 자체가 거절되므로 LIMIT이나 집계로 줄인다",
]


def get_graph_schema() -> dict:
    with _neo4j_session() as s:
        labels = s.run("MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count ORDER BY label").data()
        props = s.run(
            "MATCH (n) UNWIND labels(n) AS label UNWIND keys(n) AS key "
            "WITH label, key, n[key] AS v WHERE v IS NOT NULL AND NOT (v = []) "
            "RETURN label, key, count(*) AS non_empty ORDER BY label, key").data()
        rels = s.run("MATCH (a)-[r]->(b) RETURN labels(a)[0] AS from, type(r) AS type, labels(b)[0] AS to, "
                     "count(*) AS count ORDER BY count DESC").data()
        rel_props = s.run("MATCH ()-[r]->() UNWIND keys(r) AS key RETURN type(r) AS type, collect(DISTINCT key) "
                          "AS keys ORDER BY type").data()
        tiers = s.run("MATCH ()-[r]->() RETURN coalesce(r.source_tier,'NULL') AS source_tier, count(*) AS count "
                      "ORDER BY source_tier").data()
        projects = s.run("MATCH (p:Project) RETURN p.id AS id, p.label AS label ORDER BY id").data()
        statuses = s.run("MATCH (u:TechnologyUse) RETURN coalesce(u.status,'NULL') AS status, count(*) AS count "
                         "ORDER BY count DESC").data()
        top_tech = s.run(
            "MATCH (u:TechnologyUse)-[r:USES_TECHNOLOGY]->(t:Technology) "
            "WHERE coalesce(r.source_tier,'primary') <> 'secondary' "
            "RETURN t.id AS id, t.label AS label, count(DISTINCT u.id) AS uses ORDER BY uses DESC, id LIMIT 15").data()
    names = {}
    for alias, pid in PROJECT_ALIASES.items():
        names.setdefault(pid, []).append(alias)
    by_label: dict[str, list] = {}
    for row in props:
        by_label.setdefault(row["label"], []).append({"key": row["key"], "non_empty": row["non_empty"]})
    return {
        "labels": [{**l, "properties": by_label.get(l["label"], [])} for l in labels],
        "relationships": rels,
        "relationship_properties": rel_props,
        "source_tier_counts": tiers,
        "projects": [{**p, "names": sorted(names.get(p["id"], []))} for p in projects],
        "technology_use_status_counts": statuses,
        "top_technologies_primary": top_tech,
        "notes": CYPHER_NOTES,
        "examples": tc.FEW_SHOTS + [{
            "question": "Redis를 쓴 프로젝트와 목적·상태 (1차 근거만, 근거 포함)",
            "cypher": "MATCH (p:Project)<-[r1:PART_OF]-(u:TechnologyUse)-[r2:USES_TECHNOLOGY]->"
                      "(t:Technology {id:'kg:tech-redis'}) "
                      "WHERE coalesce(r1.source_tier,'primary') <> 'secondary' "
                      "AND coalesce(r2.source_tier,'primary') <> 'secondary' "
                      "RETURN p.id AS project, u.id AS use_id, u.purpose AS purpose, u.status AS status, "
                      "collect(DISTINCT r2.chunk_id) AS chunk_ids ORDER BY project, use_id"}],
    }


def run_cypher(query: str) -> dict:
    query = (query or "").strip()
    if not query:
        return {"ok": False, "error": "빈 쿼리"}
    if len(query) > MAX_CYPHER_CHARS:
        return {"ok": False, "error": f"쿼리가 {MAX_CYPHER_CHARS}자를 넘는다", "query": query[:200] + "…"}
    try:
        tc.guard(query)   # DB에 닿기 전에 정적 검사부터 (쓰기·CALL·APOC·LOAD CSV·주석·다중 문장 차단)
        with _neo4j_session() as session:
            rows, notifications = tc.execute(session, query)   # EXPLAIN 읽기 확인 + execute_read + 10초
    except ValueError as exc:
        hint = "LIMIT이나 집계로 행 수를 줄여 다시 실행" if "200행" in str(exc) else \
            "get_graph_schema의 notes에 맞게 고쳐 다시 실행"
        return {"ok": False, "error": str(exc), "hint": hint, "query": query}
    except Neo4jError as exc:
        return {"ok": False, "error": f"{exc.code}: {exc.message}", "query": query}
    rows = json.loads(json.dumps(rows, ensure_ascii=False, default=str))
    filtered = "source_tier" in query
    result = {"ok": True, "query": query, "row_count": len(rows), "rows": rows,
              "scope": "1차 문서 필터 포함" if filtered else
              "⚠️ source_tier 필터가 없다: 2차 문서 근거가 섞였을 수 있음. 답에 그렇게 밝히거나 필터를 넣어 다시 실행"}
    if not rows:
        result["message"] = ("이 조건으로 0건. 데이터에 없다는 뜻이 아니다 — id 소문자 표기, purpose 문자열 조건, "
                             "status NULL, source_tier 필터를 점검하고, 필요하면 search_documents로 교차 확인할 것")
    if notifications:
        result["notifications"] = [str(n) for n in notifications][:5]
    return result
