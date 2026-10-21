"""같은 질문을 v1 · v2 · v3 에 던진다.

  v1  청크 하이브리드 — nori BM25 + gemini 임베딩 kNN, RRF(k=60). 3주차와 같은 조건.
  v2  GraphRAG — 코드가 정한 세 경로 중 하나 (경로 선택만 LLM 분류, 질의는 코드/검증된 Cypher)
        local      질문·진입 청크의 엔티티 → Finding·Pitfall 확장 → 질문 유사도로 재정렬 → 근거 청크 회수
        aggregate  Text2Cypher (읽기 전용 검증, READ 세션)
        global     커뮤니티 요약 Map-Reduce
  v3  LLM 위키 — 위키 청크 하이브리드 + 위키링크 1홉 이웃 요약. (위키는 같은 노트를 LLM 이 미리 합성한 층)

v1·v2 는 members/ 소재만 읽는다. 위키(WikiPage·Contradiction·wiki_chunks)는 v3 만 읽는다.

실행: python ask.py "질문" [--mode v1|v2|v3|all] [--route local|aggregate|global] [--show]
"""
import argparse
import json
import re

import numpy as np

from common import CHAT_MODEL, ES_INDEX, JsonCache, llm, embed, es, neo4j_driver
from load_semantic import alias_patterns

WIKI_INDEX = "wiki_chunks"
RRF_K = 60
HUBS = {"RAG", "지식그래프", "임베딩", "RDF"}  # 거의 모든 청크가 언급 — 질문에 직접 나오지 않으면 진입점으로 쓰지 않는다
_cache = JsonCache("answers")
_pats = alias_patterns()


# ── 공통 ────────────────────────────────────────────────────────────────
def chat(messages, json_mode=False, model=CHAT_MODEL):
    k = JsonCache.key(model, json.dumps(messages, ensure_ascii=False), json_mode)
    hit = _cache.get(k)
    if hit is not None:
        return hit
    kw = {"response_format": {"type": "json_object"}} if json_mode else {}
    resp = llm().chat.completions.create(model=model, messages=messages, temperature=0, **kw)
    out = resp.choices[0].message.content
    _cache.put(k, out)
    return out


def loads_json(text):
    """JSON 모드라도 모델이 코드 펜스나 설명을 붙여 보낼 때가 있다(claude 심판) — 첫 { 부터 마지막 } 까지만 읽는다."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(text[text.index("{") : text.rindex("}") + 1])


def hybrid(index, q, k=8, pool=50, extra_fields=()):
    """BM25 top-pool 과 kNN top-pool 을 RRF 로 합친다."""
    client = es()
    qv = embed([q])[0]
    src = ["text", "title", "heading", *extra_fields]
    bm = client.search(index=index, size=pool, source=src,
                       query={"multi_match": {"query": q, "fields": ["text", "title^2", "heading^1.5"]}})["hits"]["hits"]
    kn = client.search(index=index, size=pool, source=src,
                       knn={"field": "embedding", "query_vector": qv, "k": pool, "num_candidates": pool * 4})["hits"]["hits"]
    score, docs = {}, {}
    for hits in (bm, kn):
        for rank, h in enumerate(hits):
            score[h["_id"]] = score.get(h["_id"], 0) + 1 / (RRF_K + rank + 1)
            docs[h["_id"]] = h["_source"]
    top = sorted(score, key=score.get, reverse=True)[:k]
    return [dict(docs[i], id=i) for i in top]


ANSWER_SYS = """너는 스터디 저장소에 대한 질문에 답한다. 아래 근거만 쓴다.
- 문장마다 근거 번호를 [C1]·[G2]처럼 붙인다. C 는 원문 청크, G 는 그래프 사실, W 는 위키, S 는 커뮤니티 요약이다.
- 누가 확인했는지(멤버 github id)를 반드시 밝힌다. "정리했다"와 "측정했다"를 구분한다.
- 근거로 답할 수 없으면 "근거 없음"이라고 하고 부족한 것을 말한다. 추측으로 채우지 않는다.
- 6문장 이내, 한국어."""


def answer(q, blocks):
    ctx = "\n\n".join(blocks)
    return chat([{"role": "system", "content": ANSWER_SYS}, {"role": "user", "content": f"## 근거\n{ctx}\n\n## 질문\n{q}"}])


def member_of(path):
    return path.split("/")[1] if path.startswith("members/") else "?"


# ── v1 ──────────────────────────────────────────────────────────────────
def v1(q, show=False):
    hits = hybrid(ES_INDEX, q, extra_fields=("path", "member"))
    blocks = [f"[C{i+1}] {h['member']} · {h['path']} · {h['heading']}\n{h['text'][:1200]}" for i, h in enumerate(hits)]
    return {"mode": "v1", "answer": answer(q, blocks), "context": blocks if show else len(blocks),
            "sources": [h["path"] for h in hits]}


# ── v2 ──────────────────────────────────────────────────────────────────
ROUTE_SYS = """질문을 세 경로 중 하나로 분류한다. JSON 으로만: {"route": "local|aggregate|global", "why": "<한 줄>"}
- local: 특정 기법·도구·멤버·실험 주변의 사실과 관계 ("RRF가 진 사례에서 원인은?", "kdyann은 6주차에 무엇을 비교했나")
- aggregate: 개수·순위·최다·목록·"누가 모두"처럼 전체를 세거나 걸러야 하는 질문 ("가장 많은 멤버가 다룬 기법은?")
- global: 스터디 전체의 주제·경향·공통점 ("10기가 공통으로 부딪힌 문제는?")"""

SCHEMA_DOC = """노드
  (:Member {id, cohort})                     스터디 멤버. id 는 github id (예: 'kdyann')
  (:Document {path, kind, title, date, week}) kind ∈ note|lab|readme|readings. week ∈ 1..6 (추정치)
  (:Chunk {id, heading, text})
  (:Tag {name})                              노트 frontmatter 태그 원문(소문자, 표기 불일치 있음)
  (:Week {n})
  (:Technique {name}) (:Tool {name})         닫힌 사전의 정규 이름. 예: 'BM25','RRF','하이브리드 검색','GraphRAG','Text2Cypher','Elasticsearch','Neo4j','pgvector'
  (:Finding {kind, metric, value, condition, claim, evidence})  kind ∈ measured(직접 실험)|cited(인용)
  (:Pitfall {name, description, mitigation, evidence})
  (:Dataset {name})                          데이터 유형. 예: '인스타그램 캡션','카카오톡 대화'
관계
  (Member)-[:WROTE]->(Document)-[:HAS_CHUNK]->(Chunk)
  (Document)-[:TAGGED]->(Tag)   (Document)-[:IN_WEEK]->(Week)
  (Chunk)-[:MENTIONS]->(Technique|Tool)
  (Technique|Tool)-[:PART_OF]->(Technique)
  (Member)-[:REPORTED]->(Finding)-[:EVIDENCED_BY]->(Chunk)
  (Finding)-[:ABOUT]->(Technique|Tool)
  (Finding)-[:COMPARED_WITH {outcome: 'win'|'lose'|'tie'}]->(Technique|Tool)   outcome 은 Finding 의 ABOUT 쪽 기준
  (Finding)-[:ON_DATA]->(Dataset)
  (Member)-[:HIT]->(Pitfall)-[:OCCURS_IN]->(Technique|Tool)
  (Pitfall)-[:MITIGATED_BY]->(Technique|Tool)"""

ENTITY_NAMES = "\n".join(
    f"  {label}: " + ", ".join(names) for label, names in
    ((lbl, list(d)) for lbl, d in __import__("load_semantic").ENTS.items())
)

# 1회차(eval_run1.json)에서 Q03·Q04 가 0행 오답 — f.outcome(관계 속성을 노드에서 찾음), '벡터 검색'(정규 이름은 '임베딩')
T2C_SYS = f"""너는 Neo4j Cypher 를 쓴다. 아래 스키마만 쓴다(다른 라벨·관계는 없다). 읽기 전용.
{SCHEMA_DOC}
엔티티 정규 이름 전체 (이 철자만 존재한다. 벡터 검색·dense retrieval 은 '임베딩', 키워드 검색 일반은 '키워드 검색'):
{ENTITY_NAMES}
규칙: 엔티티 이름은 위 목록 그대로 쓴다. outcome 은 관계 속성이다 — (f)-[cw:COMPARED_WITH]->(o) WHERE cw.outcome = 'lose'.
멤버를 셀 때는 count(DISTINCT m). 결과는 50행 이하.
"직접 실험"을 묻는다면 Finding.kind = 'measured' 로 거른다.
JSON 으로만: {{"cypher": "<쿼리>", "assumption": "<해석한 가정 한 줄>"}}"""

WRITE_CLAUSE = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|FOREACH)\b|apoc\.(create|merge|refactor|periodic)|CALL\s+db\.", re.I)
V3_ONLY = re.compile(r":\s*(WikiPage|Contradiction|Community)\b|IN_COMMUNITY|LINKS_TO|CITES|CREDITS|INVOLVES", re.I)


def run_read(cypher, params=None):
    with neo4j_driver() as drv, drv.session(default_access_mode="READ") as s:
        return s.run(cypher, params or {}, timeout=15).data()


def stable_rows(cy, rows):
    """행 순서·collect() 목록 순서는 저장 순서를 따라서, DB 를 스냅샷에서 다시 불러오면 바뀐다.
    프롬프트가 바뀌면 답이 달라지므로 문자열 목록은 정렬하고, ORDER BY 가 없으면 행도 정렬한다."""
    rows = [{k: sorted(v) if isinstance(v, list) and all(isinstance(x, str) for x in v) else v for k, v in r.items()}
            for r in rows]
    if not re.search(r"\bORDER\s+BY\b", cy, re.I):
        rows.sort(key=lambda r: json.dumps(r, ensure_ascii=False, sort_keys=True))
    return rows


def text2cypher(q):
    msgs = [{"role": "system", "content": T2C_SYS}, {"role": "user", "content": q}]
    trace = []
    for attempt in range(2):
        gen = loads_json(chat(msgs, json_mode=True))
        cy = gen["cypher"].strip().rstrip(";")
        if WRITE_CLAUSE.search(cy) or V3_ONLY.search(cy):
            err = "쓰기 구문 또는 v2 범위 밖 라벨 사용 — 거절"
        else:
            if not re.search(r"\bLIMIT\b", cy, re.I):
                cy += " LIMIT 50"
            try:
                rows = run_read(cy)
                trace.append({"cypher": cy, "assumption": gen.get("assumption"), "rows": len(rows)})
                return cy, gen.get("assumption"), rows, trace
            except Exception as e:  # 문법·실행 오류는 한 번 고쳐 쓰게 한다
                err = str(e)[:300]
        trace.append({"cypher": cy, "error": err})
        msgs += [{"role": "assistant", "content": json.dumps(gen, ensure_ascii=False)},
                 {"role": "user", "content": f"오류: {err}\n고쳐서 다시 JSON 으로."}]
    return None, None, [], trace


def link_entities(text):
    return [name for name, p in _pats.items() if p.search(text)]


LOCAL_Q = """
MATCH (e) WHERE (e:Technique OR e:Tool) AND e.name IN $ents
MATCH (x)-[r:ABOUT|COMPARED_WITH|OCCURS_IN|MITIGATED_BY]->(e)
MATCH (m:Member)-[:REPORTED|HIT]->(x)-[:EVIDENCED_BY]->(c:Chunk)<-[:HAS_CHUNK]-(d:Document)
OPTIONAL MATCH (x)-[:ON_DATA]->(ds:Dataset)
OPTIONAL MATCH (x)-[cw:COMPARED_WITH]->(o)
RETURN DISTINCT labels(x)[0] AS type, x.id AS id, m.id AS member, d.path AS path, d.week AS week, c.id AS chunk,
       coalesce(x.claim, x.name + ': ' + x.description) AS fact, x.kind AS kind, x.metric AS metric, x.value AS value,
       x.condition AS condition, x.mitigation AS mitigation, ds.name AS dataset,
       collect(DISTINCT o.name + '(' + cw.outcome + ')') AS vs, collect(DISTINCT e.name) AS via
ORDER BY id
"""


def v2_local(q, show=False):
    entry = hybrid(ES_INDEX, q, k=8, extra_fields=("path", "member"))
    q_ents = link_entities(q)
    chunk_ents = {}
    for h in entry:
        for e in link_entities(h["text"]):
            chunk_ents[e] = chunk_ents.get(e, 0) + 1
    # 질문에 나온 엔티티 우선, 없으면 진입 청크에서 자주 나온 비허브 엔티티 3개
    ents = q_ents or [e for e, _ in sorted(chunk_ents.items(), key=lambda x: -x[1]) if e not in HUBS][:3]
    facts = run_read(LOCAL_Q, {"ents": ents}) if ents else []
    for f in facts:  # collect() 순서도 저장 순서를 따른다
        f["vs"], f["via"] = sorted(f["vs"]), sorted(f["via"])
    # 질문 이름에 멤버 id 가 있으면 그 멤버의 사실로 좁힌다
    member_ids = {r["member"] for r in facts}
    named = [m for m in member_ids if re.search(rf"\b{re.escape(m)}\b", q, re.I)]
    if named:
        facts = [f for f in facts if f["member"] in named]
    if facts:  # 확장 결과도 재정렬한다 (6주차 dldusgh318: 확장해도 회수 순서가 나쁘면 근거를 못 가져온다)
        qv = np.array(embed([q])[0])
        fv = np.array(embed([f["fact"] for f in facts]))
        sims = fv @ qv / (np.linalg.norm(fv, axis=1) * np.linalg.norm(qv) + 1e-9)
        facts = [facts[i] for i in np.argsort(-sims)[:15]]
    g_blocks = []
    for i, f in enumerate(facts):
        detail = " · ".join(x for x in [
            f"{f['metric']}={f['value']}" if f.get("value") else "", f"조건: {f['condition']}" if f.get("condition") else "",
            f"데이터: {f['dataset']}" if f.get("dataset") else "", f"비교: {', '.join(f['vs'])}" if f.get("vs") else "",
            f"처방: {f['mitigation']}" if f.get("mitigation") else "",
        ] if x)
        tag = "실험" if f.get("kind") == "measured" else ("인용" if f["type"] == "Finding" else "함정")
        g_blocks.append(f"[G{i+1}] {f['member']} · {f['week']}주차(추정) · {tag} · {f['fact']}  ({detail}) ← {f['path']}")
    c_blocks = [f"[C{i+1}] {h['member']} · {h['path']} · {h['heading']}\n{h['text'][:900]}" for i, h in enumerate(entry[:5])]
    return {"mode": "v2/local", "entities": ents, "answer": answer(q, g_blocks + c_blocks),
            "context": (g_blocks + c_blocks) if show else f"G{len(g_blocks)} + C{len(c_blocks)}",
            "sources": sorted({f["path"] for f in facts} | {h["path"] for h in entry[:5]})}


def v2_aggregate(q, show=False):
    cy, assumption, rows, trace = text2cypher(q)
    if cy is None or not rows:
        # 0행은 '없음'이 아니다(6주차 sunghyun) — 같은 질문을 로컬 서치로 다시 찾는다
        res = v2_local(q, show)
        return dict(res, mode="v2/aggregate→local", cypher=cy, rows=0, trace=trace)
    rows = stable_rows(cy, rows)
    blocks = [f"[G1] Cypher: {cy}\n가정: {assumption}\n결과 {len(rows)}행:\n" + json.dumps(rows[:50], ensure_ascii=False)]
    return {"mode": "v2/aggregate", "cypher": cy, "rows": len(rows), "answer": answer(q, blocks),
            "context": blocks if show else f"{len(rows)} rows", "trace": trace}


MAP_SYS = """커뮤니티 요약 하나를 보고 질문에 도움이 되는 점을 뽑는다. JSON 으로만:
{"points": [{"text": "<멤버 id 를 붙인 한 줄>", "score": <0~100 질문 관련도>}]}  관련 없으면 빈 배열."""


def v2_global(q, show=False):
    comms = run_read("MATCH (c:Community) RETURN c.id AS id, c.title AS title, c.summary AS summary, "
                     "c.key_points AS kp, c.members AS members, c.size AS size ORDER BY c.size DESC")
    points = []
    for c in comms:  # Map
        body = f"[{c['id']}] {c['title']} (멤버 {', '.join(c['members'])})\n{c['summary']}\n" + "\n".join(f"- {p}" for p in c["kp"])
        out = loads_json(chat([{"role": "system", "content": MAP_SYS}, {"role": "user", "content": f"질문: {q}\n\n{body}"}], json_mode=True))
        points += [dict(p, community=c["id"], title=c["title"]) for p in out.get("points", []) if p.get("score", 0) >= 30]
    points.sort(key=lambda p: -p["score"])
    blocks = [f"[S{i+1}] ({p['community']} {p['title']}) {p['text']}" for i, p in enumerate(points[:20])]  # Reduce
    return {"mode": "v2/global", "communities": len(comms), "answer": answer(q, blocks),
            "context": blocks if show else f"{len(points)} points from {len(comms)} communities"}


def v2(q, show=False, route=None):
    if not route:
        r = loads_json(chat([{"role": "system", "content": ROUTE_SYS}, {"role": "user", "content": q}], json_mode=True))
        route = r["route"]
    return {"local": v2_local, "aggregate": v2_aggregate, "global": v2_global}[route](q, show)


# ── v3 ──────────────────────────────────────────────────────────────────
def v3(q, show=False):
    hits = hybrid(WIKI_INDEX, q, k=6, extra_fields=("page",))
    pages = list(dict.fromkeys(h["page"] for h in hits))
    nbrs = run_read(
        "MATCH (p:WikiPage)-[:LINKS_TO]->(n:WikiPage) WHERE p.name IN $pages AND NOT n.name IN $pages AND n.summary <> '' "
        "RETURN n.name AS name, n.summary AS summary, count(*) AS deg ORDER BY deg DESC, name LIMIT 5", {"pages": pages})
    blocks = [f"[W{i+1}] 위키 {h['page']} · {h['heading']}\n{h['text'][:1200]}" for i, h in enumerate(hits)]
    blocks += [f"[W{len(hits)+i+1}] 위키 {n['name']} (이웃 요약)\n{n['summary']}" for i, n in enumerate(nbrs)]
    return {"mode": "v3", "answer": answer(q, blocks), "context": blocks if show else len(blocks), "pages": pages}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--mode", default="all", choices=["v1", "v2", "v3", "all"])
    ap.add_argument("--route", choices=["local", "aggregate", "global"])
    ap.add_argument("--show", action="store_true", help="컨텍스트 전체 출력")
    a = ap.parse_args()
    modes = ["v1", "v2", "v3"] if a.mode == "all" else [a.mode]
    for m in modes:
        res = v2(a.question, a.show, a.route) if m == "v2" else globals()[m](a.question, a.show)
        print(f"\n━━ {res['mode']} ━━")
        for k, v in res.items():
            if k not in ("mode", "answer"):
                print(f"  {k}: {json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v}")
        print(res["answer"])
