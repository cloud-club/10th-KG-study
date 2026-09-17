"""Normal/Oracle RAG 증거를 기록해 실패 단계 판정을 돕는다.

실제 답의 정확성과 oracle 성공 여부는 사람이 확인해 기록한다.
"""
import argparse
import json
from datetime import datetime, timezone

from agent import answer_from_chunks, answer_with_chunks
from common import WEEK3_DATA, load_chunks_by_id
from hybrid_search import hybrid_search

CASES = WEEK3_DATA / "cases.json"
RETRIEVAL_CHECK = WEEK3_DATA / "retrieval_check.json"
RUNS = WEEK3_DATA / "failure_runs.jsonl"
KINDS = {"single-hop", "2-hop", "aggregation", "3-hop"}
FAILURE_TYPES = ["retrieval", "assembly", "composition", "citation", "no_data"]


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


def load_cases() -> list[dict]:
    if not CASES.exists():
        raise SystemExit("cases.json이 없습니다. template 명령으로 먼저 생성하세요.")

    cases = json.loads(CASES.read_text(encoding="utf-8")).get("cases", [])
    if not cases:
        raise SystemExit("검증된 실험 질문이 없습니다. cases.json을 먼저 작성하세요.")

    corpus = load_chunks_by_id()
    seen: set[str] = set()
    for case in cases:
        missing_fields = [field for field in ("id", "kind", "question", "expected", "gold_chunks") if not case.get(field)]
        if missing_fields:
            raise SystemExit(f"{case.get('id', '<unknown>')}: 필수 필드 누락 - {', '.join(missing_fields)}")
        if case["id"] in seen:
            raise SystemExit(f"중복 case id: {case['id']}")
        if case["kind"] not in KINDS:
            raise SystemExit(f"{case['id']}: 지원하지 않는 kind: {case['kind']}")
        if len(case["gold_chunks"]) > 5:
            raise SystemExit(f"{case['id']}: Oracle Context는 최대 5개 청크만 사용합니다.")
        unknown = [chunk_id for chunk_id in case["gold_chunks"] if chunk_id not in corpus]
        if unknown:
            raise SystemExit(f"{case['id']}: 존재하지 않는 gold chunk: {', '.join(unknown)}")
        seen.add(case["id"])
    return cases


def check_retrieval() -> list[dict]:
    records = []
    for case in load_cases():
        retrieved = hybrid_search(case["question"], 5)
        retrieved_ids = [row["id"] for row in retrieved]
        missing = [chunk_id for chunk_id in case["gold_chunks"] if chunk_id not in retrieved_ids]
        record = {
            "case_id": case["id"],
            "kind": case["kind"],
            "question": case["question"],
            "retrieved_top5": retrieved_ids,
            "gold_chunks": case["gold_chunks"],
            "missing_gold_chunks": missing,
            "retrieval_coverage": (len(case["gold_chunks"]) - len(missing)) / len(case["gold_chunks"]),
        }
        records.append(record)
        print(f'{case["id"]}: gold {len(case["gold_chunks"]) - len(missing)}/{len(case["gold_chunks"])} 포함, 누락 {len(missing)}')

    payload = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "top_k": 5,
        "note": "검색 누락만 확인한 결과이며 답변의 정답 여부나 실패 유형 판정이 아니다.",
        "cases": records,
    }
    WEEK3_DATA.mkdir(parents=True, exist_ok=True)
    RETRIEVAL_CHECK.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"검색 점검 저장: {RETRIEVAL_CHECK}")
    return records


def run(model: str | None) -> None:
    cases = load_cases()
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
                    "allowed_failure_types": FAILURE_TYPES,
                    "note": "정답 의미 비교 후 사람이 작성한다."
                },
            }
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f'{case["id"]}: missing gold {len(missing)}, normal citation {normal["citation_verified"]}, oracle citation {oracle["citation_verified"]}')
    print(f"실험 증거 저장: {RUNS}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=("template", "check", "run"), default="template")
    parser.add_argument("--model")
    args = parser.parse_args()
    if args.command == "template":
        make_template()
    elif args.command == "check":
        check_retrieval()
    else:
        run(args.model)


if __name__ == "__main__":
    main()
