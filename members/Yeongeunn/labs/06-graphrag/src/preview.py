"""고정된 2-hop 질의로 그래프 관계와 근거를 조회한다."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(
    0,
    str(ROOT / "members/Yeongeunn/labs/05-triple-extraction/src"),
)
from graph_lab import driver

QUESTION = "회원탈퇴 API가 호출하는 서비스와 그 서비스가 제공하는 API는 무엇인가?"

QUERY = """
MATCH (a:KGStudyYeongeunn {id: 'withdraw-api', run: $run})
      -[r1:CALLS_SERVICE]->
      (s:KGStudyYeongeunn {run: $run})
      -[r2:EXPOSES_API]->
      (b:KGStudyYeongeunn {run: $run})
RETURN a.label AS start_api,
       s.label AS service,
       b.label AS provided_api,
       r1.evidence_json AS call_evidence,
       r2.evidence_json AS api_evidence
ORDER BY service, provided_api
"""


def retrieve():
    metadata = json.loads(
        (ROOT / "data/Yeongeunn/kg-v0/graph-run.json").read_text()
    )
    with driver() as db, db.session() as session:
        rows = session.execute_read(
            lambda tx: tx.run(QUERY, run=metadata["run"]).data()
        )

    evidence = []
    for row in rows:
        relations = [
            (
                f'{row["start_api"]} → 호출한다 → {row["service"]}',
                row["call_evidence"],
            ),
            (
                f'{row["service"]} → 제공한다 → {row["provided_api"]}',
                row["api_evidence"],
            ),
        ]
        for relation, raw in relations:
            quotes = [
                {
                    "chunk_id": item["chunk_id"],
                    "field": item["field"],
                    "quote": item["quote"],
                }
                for item in json.loads(raw)
            ]
            evidence.append({
                "number": len(evidence) + 1,
                "relation": relation,
                "evidence": quotes,
            })
    return evidence


if __name__ == "__main__":
    evidence = retrieve()
    print("질문:", QUESTION)
    print("고정 Cypher 조회 — Gemini 호출 없음")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(f"\n조회한 관계: {len(evidence)}개")
