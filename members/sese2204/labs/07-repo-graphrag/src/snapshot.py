"""스냅샷 — 이 PC 밖에서 그래프를 보거나 재빌드할 수 있게 저장소에 남기는 파일들.

  snapshot/graph.json.gz   Neo4j 노드·관계 전체 (임베딩 제외). LLM 키 없이 load 로 불러와 demo.cypher 를 돌린다
  snapshot/cache/*.jsonl   추출·커뮤니티 요약·Dataset 매핑·답변/채점 LLM 캐시. outputs/ 로 복사하면 재빌드 때 LLM 을 다시 부르지 않는다
  snapshot/results/*.json  채점 결과 (1~4회차), 추출 정확도 비교, 커뮤니티 요약, Dataset 매핑

임베딩 캐시(outputs/embeddings.jsonl, 약 200MB)는 GitHub 파일 한도(100MB)를 넘어 넣지 않는다.

실행: python snapshot.py export   /   python snapshot.py load   (빈 Neo4j 에 불러온다 — 기존 데이터는 지운다)
"""
import gzip
import json
import shutil
import sys
from collections import defaultdict

from common import LAB, OUT, neo4j_driver

SNAP = LAB / "snapshot"
CACHES = ["extract.jsonl", "community_summaries.jsonl", "datasets.jsonl", "answers.jsonl"]
RESULTS = ["eval_run1.json", "eval_run2.json", "eval_run3_terra.json", "eval_run4_terra.json", "communities.json",
           "datasets.json", "judge_extract.json"]
DROP_PROPS = {"embedding"}
CONSTRAINTS = {  # 라벨 → 고유 키 (load_structure · load_semantic 과 같다)
    "Member": "id", "Document": "path", "Chunk": "id", "Tag": "name", "Week": "n", "WikiPage": "name",
    "Technique": "name", "Tool": "name", "Finding": "id", "Pitfall": "id", "Dataset": "name",
}


def export():
    with neo4j_driver() as drv, drv.session() as s:
        nodes = s.run("MATCH (n) RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props").data()
        rels = s.run(
            "MATCH (a)-[r]->(b) RETURN elementId(a) AS a, elementId(b) AS b, type(r) AS type, properties(r) AS props"
        ).data()
    sid = {n["eid"]: i for i, n in enumerate(nodes)}
    graph = {
        "nodes": [{"i": sid[n["eid"]], "labels": n["labels"],
                   "props": {k: v for k, v in n["props"].items() if k not in DROP_PROPS}} for n in nodes],
        "rels": [{"a": sid[r["a"]], "b": sid[r["b"]], "type": r["type"], "props": r["props"]} for r in rels],
    }
    SNAP.mkdir(exist_ok=True)
    with gzip.open(SNAP / "graph.json.gz", "wt", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False)
    for sub, names in (("cache", CACHES), ("results", RESULTS)):
        (SNAP / sub).mkdir(exist_ok=True)
        for name in names:
            shutil.copy(OUT / name, SNAP / sub / name)
    print(f"nodes {len(graph['nodes'])}, rels {len(graph['rels'])} → {SNAP}")


def load():
    with gzip.open(SNAP / "graph.json.gz", "rt", encoding="utf-8") as f:
        graph = json.load(f)
    by_labels, by_type = defaultdict(list), defaultdict(list)
    for n in graph["nodes"]:
        by_labels[tuple(n["labels"])].append({"i": n["i"], "props": n["props"]})
    for r in graph["rels"]:
        by_type[r["type"]].append(r)
    with neo4j_driver() as drv, drv.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
        for label, key in CONSTRAINTS.items():
            s.run(f"CREATE CONSTRAINT {label.lower()}_{key} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE")
        s.run("CREATE INDEX snap_sid IF NOT EXISTS FOR (n:_Snap) ON (n._sid)")
        for labels, rows in by_labels.items():  # 라벨은 스냅샷 파일에서 오므로 쿼리에 직접 넣는다
            lab = ":".join(f"`{l}`" for l in labels)
            for i in range(0, len(rows), 1000):
                s.run(f"UNWIND $rows AS r CREATE (n:_Snap:{lab}) SET n = r.props, n._sid = r.i", rows=rows[i : i + 1000])
        for rtype, rows in by_type.items():
            for i in range(0, len(rows), 2000):
                s.run(
                    f"UNWIND $rows AS r MATCH (a:_Snap {{_sid: r.a}}) MATCH (b:_Snap {{_sid: r.b}}) "
                    f"CREATE (a)-[x:`{rtype}`]->(b) SET x = r.props",
                    rows=rows[i : i + 2000],
                )
        s.run("MATCH (n:_Snap) REMOVE n:_Snap, n._sid")
        s.run("DROP INDEX snap_sid IF EXISTS")
        n = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
        r = s.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]
    print(f"loaded nodes {n}, rels {r}")


if __name__ == "__main__":
    {"export": export, "load": load}[sys.argv[1] if len(sys.argv) > 1 else "export"]()
