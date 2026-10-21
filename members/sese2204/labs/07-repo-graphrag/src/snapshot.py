"""스냅샷 — 이 PC 밖에서 그래프를 보거나 재빌드할 수 있게 저장소에 남기는 파일들.

  snapshot/graph.json.gz      Neo4j 노드·관계 전체 (임베딩 속성 제외). 키 없이 load 로 불러와 demo.cypher 를 돌린다
  snapshot/embeddings.npz     임베딩 캐시 (키 + float32 벡터). JSON 원본(233MB)과 값이 같다 (원래 float32 정밀도)
  snapshot/inputs/*.json.gz   코퍼스·위키 페이지·위키 청크. embed_index --snapshot 이 읽는다
  snapshot/cache/*.jsonl      추출·커뮤니티 요약·Dataset 매핑·답변/채점 LLM 캐시
  snapshot/results/*.json     채점 결과 (1~6회차), 추출 정확도 비교, 커뮤니티 요약, Dataset 매핑

load 는 그래프를 Neo4j 에 넣고 임베딩·입력·캐시를 outputs/ 로 되돌린다. 그다음 embed_index.py --snapshot 을 돌리면
ES·Neo4j 벡터 인덱스가 키 없이 만들어지고, 질문 12개는 ask.py·eval.py 가 캐시만으로 같은 결과를 낸다.

실행: python snapshot.py export   /   python snapshot.py load [--force]
      load 는 Neo4j 의 기존 데이터를 지운다. 데이터가 있으면 멈추고, --force 를 붙여야 지운다
"""
import gzip
import json
import shutil
import sys
from collections import defaultdict

import numpy as np

from common import LAB, OUT, neo4j_driver

SNAP = LAB / "snapshot"
CACHES = ["extract.jsonl", "community_summaries.jsonl", "datasets.jsonl", "answers.jsonl"]
RESULTS = ["eval_run1.json", "eval_run2.json", "eval_run3_terra.json", "eval_run4_terra.json", "eval_run5.json",
           "eval_run6.json", "communities.json",
           "datasets.json", "judge_extract.json"]
INPUTS = ["corpus.json", "wiki.json", "wiki_chunks.json"]
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
    (SNAP / "inputs").mkdir(exist_ok=True)
    for name in INPUTS:
        with gzip.open(SNAP / "inputs" / f"{name}.gz", "wt", encoding="utf-8") as f:
            f.write((OUT / name).read_text())
    recs = [json.loads(line) for line in (OUT / "embeddings.jsonl").read_text().splitlines()]
    vecs = np.array([r["v"] for r in recs], dtype=np.float32)
    assert (vecs.astype(np.float64) == np.array([r["v"] for r in recs])).all(), "float32 로 줄이면 값이 바뀐다"
    np.savez_compressed(SNAP / "embeddings.npz", keys=np.array([r["k"] for r in recs]), vecs=vecs)
    print(f"nodes {len(graph['nodes'])}, rels {len(graph['rels'])}, embeddings {len(recs)} → {SNAP}")


def merge_jsonl(src_lines, dst):
    """캐시 jsonl 을 outputs/ 에 합친다. 이미 있는 키는 건드리지 않는다."""
    have = {json.loads(line)["k"] for line in dst.read_text().splitlines()} if dst.exists() else set()
    new = [line for line in src_lines if json.loads(line)["k"] not in have]
    with dst.open("a") as f:
        f.writelines(line + "\n" for line in new)
    return len(new)


def restore_outputs():
    OUT.mkdir(exist_ok=True)
    for name in CACHES:
        n = merge_jsonl((SNAP / "cache" / name).read_text().splitlines(), OUT / name)
        print(f"  outputs/{name} +{n}")
    for name in INPUTS:
        with gzip.open(SNAP / "inputs" / f"{name}.gz", "rt", encoding="utf-8") as f:
            (OUT / name).write_text(f.read())
        print(f"  outputs/{name}")
    emb = np.load(SNAP / "embeddings.npz")
    lines = (json.dumps({"k": str(k), "v": v.astype(np.float64).tolist()}) for k, v in zip(emb["keys"], emb["vecs"]))
    print(f"  outputs/embeddings.jsonl +{merge_jsonl(list(lines), OUT / 'embeddings.jsonl')}")


def load():
    with gzip.open(SNAP / "graph.json.gz", "rt", encoding="utf-8") as f:
        graph = json.load(f)
    by_labels, by_type = defaultdict(list), defaultdict(list)
    for n in graph["nodes"]:
        by_labels[tuple(n["labels"])].append({"i": n["i"], "props": n["props"]})
    for r in graph["rels"]:
        by_type[r["type"]].append(r)
    with neo4j_driver() as drv, drv.session() as s:
        existing = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
        if existing and "--force" not in sys.argv:
            sys.exit(f"Neo4j 에 노드 {existing:,}개가 있다. load 는 전부 지우고 스냅샷으로 바꾼다.\n"
                     "다른 실습 그래프라면 먼저 백업하고, 지워도 되면 --force 를 붙여 다시 실행한다.")
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
    restore_outputs()
    print("다음: python embed_index.py --snapshot  (ES·Neo4j 벡터 인덱스. 캐시에서 나오므로 키가 필요 없다)")


if __name__ == "__main__":
    {"export": export, "load": load}[sys.argv[1] if len(sys.argv) > 1 else "export"]()
