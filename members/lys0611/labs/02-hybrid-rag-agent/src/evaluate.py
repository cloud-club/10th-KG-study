#!/usr/bin/env python3
"""BM25·벡터·RRF를 같은 gold evidence와 K 값으로 평가한다."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

from common import HNSW_EF_SEARCH, LAB_ROOT, RRF_CANDIDATE_K, RRF_RANK_CONSTANT
from dataset import assert_gold_exists, corpus_manifest, load_eval_set
from hybrid import HybridSearchEngine
from metrics import all_evidence_at_k, ann_recall_at_k, evidence_recall_at_k, macro, reciprocal_rank
from retrieval import vector_search


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def _aggregate(rows: list[dict], methods: list[str], ks: list[int]) -> dict:
    summary: dict = {"overall": {}, "by_category": {}}
    categories = sorted({row["category"] for row in rows if row["evaluated"]})
    for label, selected in [("overall", rows)] + [
        (category, [row for row in rows if row["category"] == category])
        for category in categories
    ]:
        target = summary["overall"] if label == "overall" else summary["by_category"].setdefault(label, {})
        for method in methods:
            target[method] = {
                f"evidence_recall@{k}": macro(
                    row["methods"][method][f"evidence_recall@{k}"]
                    for row in selected
                    if row["evaluated"]
                )
                for k in ks
            }
            target[method].update(
                {
                    f"all_evidence@{k}": macro(
                        row["methods"][method][f"all_evidence@{k}"]
                        for row in selected
                        if row["evaluated"]
                    )
                    for k in ks
                }
            )
            target[method][f"mrr@{max(ks)}"] = macro(
                row["methods"][method][f"mrr@{max(ks)}"]
                for row in selected
                if row["evaluated"]
            )
    return summary


def _render_markdown(result: dict, ks: list[int]) -> str:
    metrics = [f"evidence_recall@{k}" for k in ks] + [f"all_evidence@{k}" for k in ks]
    metrics.append(f"mrr@{max(ks)}")
    lines = [
        "# W3 검색 평가 결과",
        "",
        f"> 코퍼스 {result['corpus']['chunk_count']:,}개 청크 · 평가 가능 질문 {result['evaluated_questions']}개 · candidate_k={result['settings']['candidate_k']} · RRF c={result['settings']['rank_constant']}",
        "",
        "`Evidence Recall@k`의 관련성 단위는 물리 청크가 아니라 대체 가능한 overlap 청크를 묶은 evidence group이다.",
        "",
        "| 방식 | " + " | ".join(metrics) + " |",
        "|---|" + "---:|" * len(metrics),
    ]
    for method in ("bm25", "vector", "rrf"):
        values = result["summary"]["overall"][method]
        lines.append("| " + method + " | " + " | ".join(_fmt(values[name]) for name in metrics) + " |")
    lines.extend(["", "## 유형별 Evidence Recall@5 (평가 질문 수)", "", "| 유형 | n | BM25 | 벡터 | RRF |", "|---|---:|---:|---:|---:|"])
    for category, methods in result["summary"]["by_category"].items():
        n = sum(1 for row in result["per_query"] if row["evaluated"] and row["category"] == category)
        lines.append(
            f"| {category} | {n} | {_fmt(methods['bm25'].get('evidence_recall@5'))} | "
            f"{_fmt(methods['vector'].get('evidence_recall@5'))} | "
            f"{_fmt(methods['rrf'].get('evidence_recall@5'))} |"
        )
    lines.extend(["", "## 지연 시간 (ms, 질문당)", "", "| 단계 | p50 | 평균 |", "|---|---:|---:|"])
    for method, values in result["latency_ms"].items():
        lines.append(f"| {method} | {values['p50']:.1f} | {values['mean']:.1f} |")
    if result.get("ann_recall@10") is not None:
        lines.extend(
            [
                "",
                "## HNSW 근사 손실",
                "",
                f"HNSW top-10과 정확 검색(`enable_indexscan=off`) top-10의 겹침 비율 평균: **{result['ann_recall@10']:.3f}** "
                f"(ef_search={result['settings']['hnsw_ef_search']}, iterative_scan=strict_order)",
            ]
        )
    lines.extend(
        [
            "",
            "## 해석할 때 주의할 점",
            "",
            "- 답이 없는 질문과 완전한 qrels를 만들기 어려운 집계 질문은 Recall 평균에서 제외했다.",
            "- 이 결과는 개인 카톡의 작은 수동 평가셋에 대한 기술 통계이며 일반 성능을 뜻하지 않는다.",
            "- 원문·질문별 검색 결과·content hash는 비공개 JSON에만 저장한다.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval", type=Path, default=LAB_ROOT / "data/private/eval.jsonl")
    parser.add_argument("--k", default="1,3,5,10")
    parser.add_argument("--candidate-k", type=int, default=RRF_CANDIDATE_K)
    parser.add_argument("--rank-constant", type=int, default=RRF_RANK_CONSTANT)
    parser.add_argument("--exact-vector", action="store_true")
    parser.add_argument("--json-out", type=Path, default=LAB_ROOT / "results/private/evaluation.json")
    parser.add_argument("--md-out", type=Path, default=LAB_ROOT / "results/retrieval-summary.md")
    args = parser.parse_args()

    ks = sorted({int(value) for value in args.k.split(",")})
    if not ks or min(ks) < 1 or args.candidate_k < max(ks):
        parser.error("K는 1 이상이고 candidate-k는 가장 큰 K 이상이어야 합니다.")
    questions = load_eval_set(args.eval)
    methods = ["bm25", "vector", "rrf"]
    rows: list[dict] = []
    latency: dict[str, list[float]] = defaultdict(list)
    ann_recalls: list[float] = []

    with HybridSearchEngine() as engine:
        counts = engine.preflight()
        assert_gold_exists(engine.conn, questions)
        manifest = corpus_manifest(engine.conn)
        manifest.update(counts)
        for index, question in enumerate(questions, start=1):
            run = engine.search(
                question.question,
                filters=question.filters,
                candidate_k=args.candidate_k,
                rank_constant=args.rank_constant,
                exact_vector=args.exact_vector,
            )
            latency["bm25"].append(run.timings_ms["bm25"])
            latency["embedding"].append(run.timings_ms["embedding"])
            latency["vector"].append(run.timings_ms["vector"])
            latency["rrf"].append(run.timings_ms["rrf"])
            latency["total"].append(run.timings_ms["total"])
            if not args.exact_vector:
                # 같은 질문 벡터로 HNSW를 끈 정확 검색을 한 번 더 돌려 근사 손실을 분리한다.
                query_vector = engine.embedder.embed_one(run.masked_query)
                exact_hits = vector_search(
                    engine.conn, query_vector, args.candidate_k, question.filters, exact=True
                )
                ann_recalls.append(
                    ann_recall_at_k(
                        [hit.content_hash for hit in run.vector],
                        [hit.content_hash for hit in exact_hits],
                        10,
                    )
                )
            ranked = {
                "bm25": [hit.content_hash for hit in run.bm25],
                "vector": [hit.content_hash for hit in run.vector],
                "rrf": [hit.content_hash for hit in run.hybrid],
            }
            evaluated = question.answerable and question.retrieval_evaluable
            method_rows: dict[str, dict] = {}
            for method in methods:
                values: dict[str, float | int | None] = {}
                for k in ks:
                    values[f"evidence_recall@{k}"] = (
                        evidence_recall_at_k(ranked[method], question.evidence_groups, k)
                        if evaluated
                        else None
                    )
                    values[f"all_evidence@{k}"] = (
                        all_evidence_at_k(ranked[method], question.evidence_groups, k)
                        if evaluated
                        else None
                    )
                values[f"mrr@{max(ks)}"] = (
                    reciprocal_rank(ranked[method], question.all_gold_hashes, max(ks))
                    if evaluated
                    else None
                )
                values["top_hashes"] = ranked[method][: max(ks)]
                method_rows[method] = values
            rows.append(
                {
                    "qid": question.qid,
                    "category": question.category,
                    "answerable": question.answerable,
                    "evaluated": evaluated,
                    "methods": method_rows,
                }
            )
            print(f"[{index:02d}/{len(questions):02d}] {question.qid}")

    summary = _aggregate(rows, methods, ks)
    result = {
        "corpus": manifest,
        "settings": {
            "candidate_k": args.candidate_k,
            "rank_constant": args.rank_constant,
            "ks": ks,
            "vector_mode": "exact" if args.exact_vector else "hnsw",
            "hnsw_ef_search": HNSW_EF_SEARCH,
        },
        "questions": len(questions),
        "evaluated_questions": sum(row["evaluated"] for row in rows),
        "summary": summary,
        "latency_ms": {
            method: {"mean": sum(values) / len(values), "p50": median(values)}
            for method, values in latency.items()
        },
        "ann_recall@10": macro(ann_recalls) if ann_recalls else None,
        "per_query": rows,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    args.md_out.write_text(_render_markdown(result, ks), encoding="utf-8")
    print(f"private result: {args.json_out}")
    print(f"public summary: {args.md_out}")


if __name__ == "__main__":
    main()
