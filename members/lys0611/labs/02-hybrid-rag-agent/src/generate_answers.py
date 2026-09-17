#!/usr/bin/env python3
"""평가셋 전체 질문에 에이전트 답변을 생성하고, 사람이 채점할 표(CSV)를 만든다.

  python src/generate_answers.py                 # .env의 LLM_PROVIDER로 34문항 생성
  python src/generate_answers.py --dry-run       # LLM 없이 stub 답변으로 파이프라인만 점검
  python src/generate_answers.py --qid q014      # 한 문항만

산출물(모두 비공개, results/private/):
  answers.jsonl   질문·답변·인용·컨텍스트 청크·지연
  grading.csv     사람이 채울 채점표. accuracy(0/0.5/1) · citation_precision · citation_recall · refusal_ok(0/1) · note
채점을 마친 뒤 summarize_grading.py 로 공개용 집계를 만든다.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from time import perf_counter

from agent import PersonalDataAgent
from common import LAB_ROOT, LLM_MODEL, LLM_PROVIDER, RAG_TOP_K
from dataset import load_eval_set
from hybrid import HybridSearchEngine
from llm import create_generator

GRADING_COLUMNS = [
    "qid", "category", "answerable", "retrieval_hit@k", "citation_unknown", "question",
    "reference_answer", "answer", "cited", "coverage",
    "accuracy", "citation_precision", "citation_recall", "refusal_ok", "note",
]


class StubGenerator:
    """LLM 없이 경로만 점검할 때 쓴다. 항상 첫 근거를 인용한 한 문장을 낸다."""

    def generate(self, *, system: str, user: str) -> str:
        return "[dry-run] 근거 확인용 stub 답변입니다. [C1]" if "<EVIDENCE" in user else "제공된 근거로는 확인할 수 없습니다."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--eval", type=Path, default=LAB_ROOT / "data/private/eval.jsonl")
    parser.add_argument("--out", type=Path, default=LAB_ROOT / "results/private/answers.jsonl")
    parser.add_argument("--grading", type=Path, default=LAB_ROOT / "results/private/grading.csv")
    parser.add_argument("--top-k", type=int, default=RAG_TOP_K)
    parser.add_argument("--qid", help="이 qid만 실행")
    parser.add_argument("--dry-run", action="store_true", help="LLM 대신 stub 답변")
    args = parser.parse_args()
    for path in (args.out, args.grading):
        if "private" not in path.parts:
            parser.error(f"{path}: 답변 원문은 private 경로 아래에만 저장합니다.")

    if args.dry_run:
        generator = StubGenerator()
        model_label = "stub"
    else:
        generator = create_generator()
        if generator is None:
            parser.error(".env에 LLM_PROVIDER/LLM_MODEL을 설정하거나 --dry-run을 쓰세요.")
        model_label = f"{LLM_PROVIDER}:{LLM_MODEL}"

    questions = load_eval_set(args.eval)
    if args.qid:
        questions = [q for q in questions if q.qid == args.qid] or parser.error(f"qid 없음: {args.qid}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with HybridSearchEngine() as engine, args.out.open("w", encoding="utf-8") as out:
        counts = engine.preflight()
        agent = PersonalDataAgent(engine, generator)
        for index, question in enumerate(questions, start=1):
            started = perf_counter()
            try:
                result = agent.ask(
                    question.question, filters=question.filters, top_k=args.top_k, strict_citations=False
                )
            except Exception as exc:  # 연결 실패 등은 여기서 멈추는 편이 낫다
                raise SystemExit(f"{question.qid} 생성 실패: {type(exc).__name__}: {exc}") from exc
            elapsed = (perf_counter() - started) * 1000
            context_hashes = {item.chunk.content_hash for item in result.context_items}
            gold = question.all_gold_hashes
            hit = int(bool(context_hashes & gold)) if gold else None
            check = result.citation_check
            record = {
                "qid": question.qid,
                "category": question.category,
                "answerable": question.answerable,
                "model": model_label,
                "question": result.run.masked_query,
                "reference_answer": question.reference_answer,
                "answer": result.answer,
                "cited": list(check.cited),
                "citation_unknown": list(check.unknown),
                "coverage": round(check.coverage, 3),
                "retrieval_hit@k": hit,
                "context": [
                    {"citation_id": item.citation_id, "chunk_id": item.chunk.chunk_id,
                     "content_hash": item.chunk.content_hash, "ranks": item.hit.ranks}
                    for item in result.context_items
                ],
                "elapsed_ms": round(elapsed, 1),
                "timings_ms": {k: round(v, 1) for k, v in result.run.timings_ms.items()},
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            rows.append(record)
            flag = "" if not check.unknown else f"  ⚠ 미제공 인용 {list(check.unknown)}"
            print(f"[{index:02d}/{len(questions):02d}] {question.qid} {elapsed:7.0f} ms cited={list(check.cited)}{flag}")

    with args.grading.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GRADING_COLUMNS)
        writer.writeheader()
        for record in rows:
            writer.writerow(
                {
                    "qid": record["qid"], "category": record["category"], "answerable": record["answerable"],
                    "retrieval_hit@k": "" if record["retrieval_hit@k"] is None else record["retrieval_hit@k"],
                    "citation_unknown": ";".join(record["citation_unknown"]),
                    "question": record["question"], "reference_answer": record["reference_answer"] or "",
                    "answer": record["answer"], "cited": ";".join(record["cited"]), "coverage": record["coverage"],
                    "accuracy": "", "citation_precision": "", "citation_recall": "", "refusal_ok": "", "note": "",
                }
            )
    print(f"\ncorpus: {counts} · model: {model_label}")
    print(f"answers (private): {args.out}")
    print(f"grading sheet (private, 채점 후 summarize_grading.py): {args.grading}")


if __name__ == "__main__":
    main()
