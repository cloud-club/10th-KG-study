"""Normal/Oracle RAG 증거를 기록해 실패 단계 판정을 돕는다.

실제 답의 정확성과 oracle 성공 여부는 사람이 확인해 기록한다.
"""
import argparse
import json
from datetime import datetime, timezone

from agent import answer_from_chunks, answer_with_chunks
from common import WEEK3_DATA
from hybrid_search import hybrid_search

CASES = WEEK3_DATA / "cases.json"
RUNS = WEEK3_DATA / "failure_runs.jsonl"


def make_template() -> None:
    WEEK3_DATA.mkdir(parents=True, exist_ok=True)
    if CASES.exists():
        print(f"기존 파일을 보존했습니다: {CASES}")
        return
    template = {
        "version": 1,
        "instructions": "실제 데이터에서 답과 gold_chunks를 확인한 질문만 추가한다.",
        "cases": [],
        "case_schema": {
            "id": "고유 ID", "kind": "single-hop|2-hop|aggregation|3-hop",
            "question": "질문", "expected": "사람이 확인한 기대 답",
            "gold_chunks": ["실제 chunk ID"], "note": "선택 사항"
        },
    }
    CASES.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"실패 실험 템플릿 생성: {CASES}")


def run(model: str | None) -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    if not cases:
        raise SystemExit("검증된 실험 질문이 없습니다. cases.json을 먼저 작성하세요.")
    WEEK3_DATA.mkdir(parents=True, exist_ok=True)
    with RUNS.open("a", encoding="utf-8") as output:
        for case in cases:
            retrieved = hybrid_search(case["question"], 5)
            retrieved_ids = [row["id"] for row in retrieved]
            normal = answer_from_chunks(case["question"], retrieved, model=model)
            oracle = answer_with_chunks(case["question"], case["gold_chunks"], model=model)
            missing = [chunk_id for chunk_id in case["gold_chunks"] if chunk_id not in retrieved_ids]
            record = {
                "run_at": datetime.now(timezone.utc).isoformat(),
                "case": case,
                "retrieved_top5": retrieved_ids,
                "missing_gold_chunks": missing,
                "normal": normal,
                "oracle": oracle,
                "human_judgment": {
                    "normal_correct": None, "oracle_correct": None,
                    "failure_type": None,
                    "allowed_failure_types": ["retrieval", "assembly", "composition", "citation", "no_data"],
                    "note": "정답 의미 비교 후 사람이 작성한다."
                },
            }
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f'{case["id"]}: missing gold {len(missing)}, normal citation {normal["citation_verified"]}, oracle citation {oracle["citation_verified"]}')
    print(f"실험 증거 저장: {RUNS}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=("template", "run"), default="template")
    parser.add_argument("--model")
    args = parser.parse_args()
    make_template() if args.command == "template" else run(args.model)


if __name__ == "__main__":
    main()
