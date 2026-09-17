#!/usr/bin/env python3
"""사람이 채운 grading.csv를 집계해 공개 가능한 생성 평가 요약을 만든다.

  python src/summarize_grading.py                       # → results/generation-summary.md

채점 규칙(grading.csv):
  accuracy            0 / 0.5 / 1   — answerable=True 질문만. reference_answer와 비교
  citation_precision  0~1           — 붙인 [C#] 중 실제로 그 문장을 지지하는 비율
  citation_recall     0~1           — 사실 문장 중 인용으로 완전히 지지되는 비율
  refusal_ok          0 / 1         — answerable=False 질문에서 "확인할 수 없다"고 올바르게 거절했는가.
                                      answerable=True인데 거절했다면 accuracy=0으로 적는다.
빈 칸은 미채점으로 세고 평균에서 제외한다. 원문·답변은 요약에 싣지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from common import LAB_ROOT


def _num(value: str) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def _avg(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return mean(present) if present else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--grading", type=Path, default=LAB_ROOT / "results/private/grading.csv")
    parser.add_argument("--answers", type=Path, default=LAB_ROOT / "results/private/answers.jsonl")
    parser.add_argument("--md-out", type=Path, default=LAB_ROOT / "results/generation-summary.md")
    parser.add_argument("--grader", default="사람 1인", help="요약에 표기할 채점자")
    parser.add_argument("--graded-on", default=None, help="채점일(YYYY-MM-DD)")
    args = parser.parse_args()

    with args.grading.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    model = "?"
    latency: list[float] = []
    if args.answers.exists():
        for line in args.answers.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                model = record.get("model", model)
                latency.append(float(record.get("elapsed_ms", 0)))

    answerable = [r for r in rows if r["answerable"].lower() == "true"]
    unanswerable = [r for r in rows if r["answerable"].lower() != "true"]
    graded = [r for r in answerable if _num(r["accuracy"]) is not None]
    graded_refusal = [r for r in unanswerable if _num(r["refusal_ok"]) is not None]

    overall = {
        "accuracy": _avg([_num(r["accuracy"]) for r in answerable]),
        "citation_precision": _avg([_num(r["citation_precision"]) for r in rows]),
        "citation_recall": _avg([_num(r["citation_recall"]) for r in rows]),
        "refusal_rate": _avg([_num(r["refusal_ok"]) for r in unanswerable]),
        "structural_coverage": _avg([_num(r["coverage"]) for r in rows]),
    }
    unknown_citations = sum(1 for r in rows if (r["citation_unknown"] or "").strip())
    retrieval_ok_gen_fail = sum(
        1 for r in graded if r["retrieval_hit@k"] == "1" and (_num(r["accuracy"]) or 0) < 1
    )
    retrieval_fail = sum(1 for r in graded if r["retrieval_hit@k"] == "0")

    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_category[r["category"]].append(r)

    lines = [
        "# W3 생성(답변) 평가 결과",
        "",
        f"> 모델 `{model}` · 문항 {len(rows)}개 (답 있음 {len(answerable)} / 답 없음 {len(unanswerable)}) · "
        f"채점 완료 {len(graded)} + {len(graded_refusal)} · 채점자 {args.grader}"
        + (f" · {args.graded_on}" if args.graded_on else ""),
        "",
        "채점은 `grading.csv`에 문항별로 기록했다. 인용 precision/recall은 ALCE 방식대로 구조(`[C#]` 존재)가 아니라 실제 지지 여부를 본 값이다.",
        "",
        "| 지표 | 값 | 설명 |",
        "|---|---:|---|",
        f"| 답변 정확도 | {_fmt(overall['accuracy'])} | 답 있는 질문의 0/0.5/1 평균 |",
        f"| 인용 precision | {_fmt(overall['citation_precision'])} | 붙인 인용 중 실제 지지 비율 |",
        f"| 인용 recall | {_fmt(overall['citation_recall'])} | 사실 문장 중 지지되는 비율 |",
        f"| 답 없음 거절 성공률 | {_fmt(overall['refusal_rate'])} | 답 없는 질문에서 올바르게 거절 |",
        f"| 구조적 인용 커버리지 | {_fmt(overall['structural_coverage'])} | 코드가 센 값: 사실 문장 중 `[C#]`가 붙은 비율 |",
        f"| 미제공 인용 ID 발생 | {unknown_citations}건 | `[C9]`처럼 없는 근거를 인용한 답변 수 |",
        f"| 검색 성공·생성 실패 | {retrieval_ok_gen_fail}건 | gold가 컨텍스트에 있었는데 정확도 < 1 |",
        f"| 검색 실패 | {retrieval_fail}건 | gold가 top-k 컨텍스트에 없음 |",
    ]
    if latency:
        lines.append(f"| 질문당 지연 p50 | {sorted(latency)[len(latency) // 2]:.0f} ms | 검색 + 생성 |")
    lines.extend(["", "## 유형별", "", "| 유형 | n | 정확도 | 인용 precision | 인용 recall | 거절 성공률 |", "|---|---:|---:|---:|---:|---:|"])
    for category, items in sorted(by_category.items()):
        lines.append(
            f"| {category} | {len(items)} | "
            f"{_fmt(_avg([_num(r['accuracy']) for r in items if r['answerable'].lower() == 'true']))} | "
            f"{_fmt(_avg([_num(r['citation_precision']) for r in items]))} | "
            f"{_fmt(_avg([_num(r['citation_recall']) for r in items]))} | "
            f"{_fmt(_avg([_num(r['refusal_ok']) for r in items if r['answerable'].lower() != 'true']))} |"
        )
    lines.extend(
        [
            "",
            "## 읽을 때 주의",
            "",
            f"- {args.grader}의 소규모 수동 평가다. 절대 수치보다 유형 간 차이와 실패 유형 분포를 본다.",
            "- 답변·질문 원문은 비공개 CSV/JSONL에만 있다.",
            "",
        ]
    )
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text("\n".join(lines), encoding="utf-8")
    print(args.md_out)


if __name__ == "__main__":
    main()
