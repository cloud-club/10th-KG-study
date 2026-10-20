"""의미 층 적재 — entities.yaml(사전) + outputs/extract.json(추출) → Neo4j.

  (Technique|Tool)-[:PART_OF]->(Technique)         사람이 정한 분류
  (Chunk)-[:MENTIONS]->(Technique|Tool)            사전 별칭 매칭 (결정적)
  (Finding)-[:EVIDENCED_BY]->(Chunk)               추출 + evidence 원문 검증
  (Finding)-[:ABOUT]->(Technique|Tool)
  (Finding)-[:COMPARED_WITH {outcome}]->(Technique|Tool)
  (Finding)-[:ON_DATA]->(Dataset)
  (Pitfall)-[:EVIDENCED_BY]->(Chunk)  (Pitfall)-[:OCCURS_IN]->(…)  (Pitfall)-[:MITIGATED_BY]->(Technique|Tool)
  (Member)-[:REPORTED]->(Finding), (Member)-[:HIT]->(Pitfall)   파생: Chunk→Document→Member 경로를 접은 것

실행: python load_semantic.py   (load_structure.py · extract.py 다음)
"""
import hashlib
import json
import re

import yaml

from common import CHAT_MODEL, LAB, OUT, JsonCache, llm, neo4j_driver

ENTS = yaml.safe_load((LAB / "src/entities.yaml").read_text())


def alias_patterns():
    pats = {}
    for d in ENTS.values():
        for name, v in d.items():
            al = sorted(set(v["aliases"] + [name.lower()]), key=len, reverse=True)
            pats[name] = re.compile(r"(?<![\w])(" + "|".join(map(re.escape, al)) + r")(?![a-z0-9])", re.I)
    return pats


def normalize_datasets(raw_names):
    """자유 텍스트 데이터 이름 → 정규 유형. LLM 한 번, 캐시됨. 매핑 결과는 outputs/datasets.json 에 남겨 사람이 본다."""
    names = sorted({n for n in raw_names if n})
    cache = JsonCache("datasets")
    prompt = (
        "아래는 스터디 노트에서 뽑은 '실험 데이터' 표현들이다. 같은 종류끼리 묶어 15개 이하의 정규 유형으로 매핑하라. "
        "정규 유형은 짧은 한국어 명사구(예: 카카오톡 대화, 인스타그램 캡션, Notion 문서, 옵시디언 노트, 회사 기술 문서, "
        "공개 판례, 기업 공시·뉴스, 공개 벤치마크, 자체 평가 질문셋, 강의 노트, 코드 저장소, 합성·예시 데이터). "
        "멤버가 직접 만든 질문·골드셋은 '자체 평가 질문셋'이고, BEIR·HotpotQA 처럼 외부에서 받은 것만 '공개 벤치마크'다. "
        "사람·회사·서비스 고유명사는 유형 이름에 넣지 않는다. 데이터가 아니라 설정·환경을 말하는 표현은 null.\n"
        "'노트'·'문서'·'청크'·'실습 기록'처럼 **데이터 종류를 특정할 수 없는 표현은 null** 이다. 출처가 명시된 경우만 유형을 붙인다 "
        "(옵시디언·Obsidian·vault 가 있어야 옵시디언 노트, Notion 이 있어야 Notion 문서, 카톡·카카오톡이 있어야 카카오톡 대화, "
        "운영체제·강의가 있으면 강의 노트, 회사·사내가 있으면 회사 기술 문서).\n"
        'JSON 으로만: {"mapping": {"<원래 표현>": "<정규 유형 또는 null>"}}\n\n' + "\n".join(names)
    )
    k = JsonCache.key(CHAT_MODEL, prompt)
    mapping = cache.get(k)
    if mapping is None:
        resp = llm().chat.completions.create(
            model=CHAT_MODEL, messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, temperature=0,
        )
        mapping = json.loads(resp.choices[0].message.content)["mapping"]
        cache.put(k, mapping)
    mapping = {k: (None if v in (None, "null", "") else v) for k, v in mapping.items()}
    (OUT / "datasets.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1))
    return mapping


def fid(prefix, item):
    return prefix + hashlib.sha1(json.dumps(item, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]


def main():
    docs = json.loads((OUT / "corpus.json").read_text())
    ext = json.loads((OUT / "extract.json").read_text())
    pats = alias_patterns()
    mentions = [
        {"chunk": c["id"], "entity": name}
        for d in docs for c in d["chunks"] for name, p in pats.items() if p.search(c["text"])
    ]
    ds_map = normalize_datasets(f.get("dataset") for f in ext["findings"])
    findings = []
    for f in ext["findings"]:
        f = dict(f, id=fid("F", f), dataset_type=ds_map.get(f.get("dataset")) if f.get("dataset") else None)
        findings.append(f)
    pitfalls = [dict(p, id=fid("P", p)) for p in ext["pitfalls"]]

    with neo4j_driver() as drv, drv.session() as s:
        s.run("MATCH (n) WHERE n:Technique OR n:Tool OR n:Finding OR n:Pitfall OR n:Dataset DETACH DELETE n")
        for label in ("Technique", "Tool", "Finding", "Pitfall", "Dataset"):
            key = "id" if label in ("Finding", "Pitfall") else "name"
            s.run(f"CREATE CONSTRAINT {label.lower()}_{key} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE")
        for label, d in ENTS.items():
            s.run(
                f"UNWIND $rows AS r MERGE (e:{label} {{name: r.name}}) SET e.aliases = r.aliases",
                rows=[{"name": n, "aliases": v["aliases"]} for n, v in d.items()],
            )
        s.run(
            "UNWIND $rows AS r MATCH (a {name: r.a}) WHERE a:Technique OR a:Tool "
            "MATCH (b:Technique {name: r.b}) MERGE (a)-[:PART_OF]->(b)",
            rows=[{"a": n, "b": v["part_of"]} for d in ENTS.values() for n, v in d.items() if v.get("part_of")],
        )
        for i in range(0, len(mentions), 2000):
            s.run(
                "UNWIND $rows AS r MATCH (c:Chunk {id: r.chunk}) MATCH (e {name: r.entity}) "
                "WHERE e:Technique OR e:Tool MERGE (c)-[:MENTIONS]->(e)",
                rows=mentions[i : i + 2000],
            )
        s.run(
            """
            UNWIND $rows AS f
            MATCH (c:Chunk {id: f.chunk})<-[:HAS_CHUNK]-(:Document)<-[:WROTE]-(m:Member)
            CREATE (x:Finding {id: f.id, kind: f.kind, metric: f.metric, value: f.value, condition: f.condition,
                               claim: f.claim, evidence: f.evidence, dataset_raw: f.dataset})
            CREATE (x)-[:EVIDENCED_BY]->(c)
            CREATE (m)-[:REPORTED]->(x)
            FOREACH (e IN f.about | MERGE (t {name: e}) MERGE (x)-[:ABOUT]->(t))
            FOREACH (cw IN f.compared_with | MERGE (t {name: cw.entity}) MERGE (x)-[:COMPARED_WITH {outcome: cw.outcome}]->(t))
            FOREACH (_ IN CASE WHEN f.dataset_type IS NULL THEN [] ELSE [1] END |
                MERGE (ds:Dataset {name: f.dataset_type}) MERGE (x)-[:ON_DATA]->(ds))
            """,
            rows=findings,
        )
        s.run(
            """
            UNWIND $rows AS p
            MATCH (c:Chunk {id: p.chunk})<-[:HAS_CHUNK]-(:Document)<-[:WROTE]-(m:Member)
            CREATE (x:Pitfall {id: p.id, name: p.name, description: p.description, mitigation: p.mitigation,
                               evidence: p.evidence})
            CREATE (x)-[:EVIDENCED_BY]->(c)
            CREATE (m)-[:HIT]->(x)
            FOREACH (e IN p.occurs_in | MERGE (t {name: e}) MERGE (x)-[:OCCURS_IN]->(t))
            FOREACH (e IN coalesce(p.mitigated_by, []) | MERGE (t {name: e}) MERGE (x)-[:MITIGATED_BY]->(t))
            """,
            rows=pitfalls,
        )
        # MERGE (t {name: e}) 가 라벨 없는 노드를 만들었다면 사전 밖 이름이 새어 들어온 것 — 0 이어야 한다
        leaked = s.run("MATCH (n) WHERE size(labels(n)) = 0 RETURN count(n) AS n").single()["n"]
        counts = s.run(
            "MATCH (n) WHERE n:Technique OR n:Tool OR n:Finding OR n:Pitfall OR n:Dataset "
            "RETURN labels(n)[0] AS k, count(*) AS c ORDER BY k"
        ).data()
        rels = s.run(
            "MATCH ()-[r]->() WHERE type(r) IN ['PART_OF','MENTIONS','EVIDENCED_BY','ABOUT','COMPARED_WITH','ON_DATA',"
            "'OCCURS_IN','MITIGATED_BY','REPORTED','HIT'] RETURN type(r) AS k, count(*) AS c ORDER BY k"
        ).data()
    for row in counts + rels:
        print(f"{row['k']:>14} {row['c']}")
    print("unlabeled (사전 밖 누수):", leaked)


if __name__ == "__main__":
    main()
