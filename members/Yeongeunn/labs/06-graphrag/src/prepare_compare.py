"""저장된 문서 검색 결과와 그래프 근거로 비교 입력을 만든다."""
import json
import sys

from preview import ROOT, QUESTION, retrieve

sys.path.insert(
    0,
    str(ROOT / "members/Yeongeunn/labs/03-notion-ingest/src"),
)
from rag import redact

folder = ROOT / "data/Yeongeunn/evaluation"
previous = json.loads(
    (folder / "answer-2220849f9420.json").read_text()
)
if previous["question"] != QUESTION:
    raise RuntimeError("저장된 검색 결과의 질문이 다릅니다.")

snapshot = json.loads((folder / "snapshot.json").read_text())
lookup = {row["id"]: row for row in snapshot["rows"]}

# v1: 지난번 하이브리드 검색에서 찾은 문서 5개
documents = [
    {
        "number": number,
        "content": redact(lookup[chunk_id]["content"]),
    }
    for number, chunk_id in enumerate(previous["chunk_ids"], 1)
]

# v2에 추가할 그래프 관계와 근거
rows = retrieve()
if not rows:
    raise RuntimeError("그래프 근거가 없습니다. Neo4j 데이터를 확인하세요.")

graph = [
    {
        "number": len(documents) + number,
        "content": redact(json.dumps({
            "relation": row["relation"],
            "quotes": [
                {"field": item["field"], "quote": item["quote"]}
                for item in row["evidence"]
            ],
        }, ensure_ascii=False)),
    }
    for number, row in enumerate(rows, 1)
]

# 두 방식에 같은 질문과 답변 지시를 사용한다.
question = QUESTION + """
호출 대상 서비스와 그 서비스가 제공하는 API를 구분하라.
이벤트 구독을 직접 API 호출과 혼동하지 마라.
제공 관계만으로 해당 API가 직접 호출된다고 단정하지 마라.
근거에 없는 호출 순서를 추정하지 마라.
문서에 기록된 경로를 임의로 수정하지 마라.
"""

payload = {
    "question": question,
    "model": "gemini-3.1-flash-lite",
    "v1": documents,
    "v2": documents + graph,
    "document_chunk_ids": previous["chunk_ids"],
    "graph_references": rows,
}

output = ROOT / "data/Yeongeunn/graphrag-v1"
output.mkdir(parents=True, exist_ok=True)
target = output / "comparison-input.json"
target.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"v1: 문서 근거 {len(documents)}개")
print(f"v2: 문서 근거 {len(documents)}개 + 그래프 근거 {len(graph)}개")
print("두 방식의 질문·답변 지시·생성 모델은 동일합니다.")
print("저장:", target)
print("Gemini 호출 없음")
