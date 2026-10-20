"""글로벌 서치 준비 — 커뮤니티 탐지(Leiden) + 커뮤니티 요약 (빌드 시점 선지불).

GDS 플러그인은 사내망 SSL 가로채기로 설치가 안 돼서 igraph + leidenalg 로 계산하고 결과만 Neo4j 에 쓴다.
투영: Finding·Pitfall ─(ABOUT·COMPARED_WITH·OCCURS_IN·MITIGATED_BY)─ Technique·Tool ─(PART_OF)─ Technique.
청크 공동 언급(MENTIONS)은 넣지 않는다 — RAG·지식그래프 같은 허브가 전부를 한 덩어리로 묶는다.

  (Finding|Pitfall|Technique|Tool)-[:IN_COMMUNITY]->(Community {id, title, summary, size, members})

실행: python communities.py [--resolution 1.0]
"""
import argparse
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import igraph as ig
import leidenalg

from common import CHAT_MODEL, OUT, JsonCache, llm, embed, neo4j_driver

EDGES_Q = """
MATCH (a)-[r:ABOUT|COMPARED_WITH|OCCURS_IN|MITIGATED_BY|PART_OF]->(b)
RETURN elementId(a) AS a, elementId(b) AS b
"""
NODES_Q = """
MATCH (n) WHERE n:Finding OR n:Pitfall OR n:Technique OR n:Tool
OPTIONAL MATCH (m:Member)-[:REPORTED|HIT]->(n)
RETURN elementId(n) AS eid, labels(n)[0] AS label, coalesce(n.name, n.id) AS key,
       n.claim AS claim, n.value AS value, n.metric AS metric, n.description AS description, n.kind AS kind,
       m.id AS member
"""

SUMMARY_PROMPT = """아래는 스터디 지식그래프의 한 커뮤니티(서로 강하게 연결된 기법·도구·실험 결과·함정 묶음)다.
이 묶음을 스터디 멤버가 읽을 보고서로 요약하라. 근거에 없는 내용은 쓰지 않는다. 멤버 id 는 그대로 쓴다.
JSON 으로만: {{"title": "<12~30자 제목>", "summary": "<3~5문장. 무엇을 다뤘고, 멤버들이 무엇을 확인했고, 어디서 갈렸나>",
 "key_points": ["<멤버 id 를 붙인 핵심 사실 한 줄>", "... 최대 6개"]}}

## 엔티티
{entities}

## 실험 결과 (멤버 · 결론 · 값)
{findings}

## 함정 (멤버 · 이름 · 설명)
{pitfalls}"""


def detect(resolution):
    with neo4j_driver() as drv, drv.session() as s:
        nodes = s.run(NODES_Q).data()
        edges = s.run(EDGES_Q).data()
    idx = {n["eid"]: i for i, n in enumerate(nodes)}
    g = ig.Graph(n=len(nodes), edges=[(idx[e["a"]], idx[e["b"]]) for e in edges if e["a"] in idx and e["b"] in idx])
    g.simplify()
    part = leidenalg.find_partition(
        g, leidenalg.RBConfigurationVertexPartition, resolution_parameter=resolution, seed=42
    )
    print(f"nodes {g.vcount()} edges {g.ecount()} communities {len(part)} modularity {part.modularity:.3f}")
    groups = {}
    for ci, members in enumerate(part):
        if len(members) < 4:  # 고립·소형 묶음은 요약하지 않는다
            continue
        groups[ci] = [nodes[i] for i in members]
    return groups


def summarize(nodes, cache):
    ents = [n["key"] for n in nodes if n["label"] in ("Technique", "Tool")]
    finds = [n for n in nodes if n["label"] == "Finding"]
    pits = [n for n in nodes if n["label"] == "Pitfall"]
    prompt = SUMMARY_PROMPT.format(
        entities=", ".join(ents) or "(없음)",
        findings="\n".join(f"- {n['member']} · {n['claim']} · {n['metric'] or ''} {n['value'] or ''}" for n in finds[:60]) or "(없음)",
        pitfalls="\n".join(f"- {n['member']} · {n['key']} · {n['description']}" for n in pits[:60]) or "(없음)",
    )
    k = JsonCache.key(CHAT_MODEL, prompt)
    hit = cache.get(k)
    if hit:
        return hit
    resp = llm().chat.completions.create(
        model=CHAT_MODEL, messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}, temperature=0,
    )
    out = json.loads(resp.choices[0].message.content)
    cache.put(k, out)
    return out


def main(resolution):
    groups = detect(resolution)
    cache = JsonCache("community_summaries")
    with ThreadPoolExecutor(8) as pool:
        sums = dict(zip(groups, pool.map(lambda ns: summarize(ns, cache), groups.values())))
    rows = []
    for ci, ns in groups.items():
        sm = sums[ci]
        members = Counter(n["member"] for n in ns if n["member"])
        rows.append(
            {
                "id": f"C{ci}",
                "title": sm["title"],
                "summary": sm["summary"],
                "key_points": sm.get("key_points", []),
                "size": len(ns),
                "members": [m for m, _ in members.most_common()],
                "eids": [n["eid"] for n in ns],
                "entities": [n["key"] for n in ns if n["label"] in ("Technique", "Tool")],
            }
        )
    vecs = embed([f"{r['title']}\n{r['summary']}\n" + "\n".join(r["key_points"]) for r in rows])
    with neo4j_driver() as drv, drv.session() as s:
        s.run("MATCH (c:Community) DETACH DELETE c")
        s.run(
            """
            UNWIND $rows AS r
            CREATE (c:Community {id: r.id, title: r.title, summary: r.summary, key_points: r.key_points,
                                 size: r.size, members: r.members})
            WITH c, r
            CALL db.create.setNodeVectorProperty(c, 'embedding', r.v)
            WITH c, r
            UNWIND r.eids AS eid
            MATCH (n) WHERE elementId(n) = eid
            CREATE (n)-[:IN_COMMUNITY]->(c)
            """,
            rows=[dict(r, v=v) for r, v in zip(rows, vecs)],
        )
    (OUT / "communities.json").write_text(
        json.dumps([{k: v for k, v in r.items() if k != "eids"} for r in rows], ensure_ascii=False, indent=1)
    )
    for r in sorted(rows, key=lambda r: -r["size"]):
        print(f"{r['id']:>4} {r['size']:>4}  {r['title']}  | {', '.join(r['entities'][:6])} | {len(r['members'])}명")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolution", type=float, default=1.0)
    main(ap.parse_args().resolution)
