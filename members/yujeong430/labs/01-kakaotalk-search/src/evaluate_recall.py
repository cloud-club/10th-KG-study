"""같은 관련성 판단 목록으로 BM25·벡터·RRF의 Recall@k를 비교한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from retrieval import load_embedding_model, search_bm25, search_hybrid, search_vector


def recall_at_k(result_ids: list[str], relevant_ids: set[str]) -> float:
    """상위 k 결과에서 찾은 관련 청크의 비율을 계산한다."""
    if not relevant_ids:
        raise ValueError("각 평가 질문에는 relevant_ids가 하나 이상 필요합니다.")
    return len(set(result_ids) & relevant_ids) / len(relevant_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/evaluation/retrieval_gold.json"))
    parser.add_argument("--k", type=int, help="한 개의 k만 평가할 때 사용")
    parser.add_argument("--ks", type=int, nargs="+", default=[1, 3, 5], help="평가할 k 목록 (기본: 1 3 5)")
    parser.add_argument("--rank-window", type=int, default=20)
    parser.add_argument("--rank-constant", type=int, default=60)
    parser.add_argument("--output", type=Path, help="선택: 상세 결과 JSON 파일")
    args = parser.parse_args()
    ks = [args.k] if args.k is not None else args.ks
    if any(k < 1 for k in ks):
        raise ValueError("k는 모두 1 이상이어야 합니다.")
    max_k = max(ks)
    gold = json.loads(args.input.read_text(encoding="utf-8"))
    queries = gold["queries"]
    model = load_embedding_model()
    methods: dict[str, Callable[[str], list[dict]]] = {
        "bm25": lambda query: search_bm25(query, max_k),
        "vector": lambda query: search_vector(query, max_k, model),
        "hybrid_rrf": lambda query: search_hybrid(query, max_k, args.rank_window, model, args.rank_constant),
    }
    all_results: list[dict] = []
    totals = {k: {name: 0.0 for name in methods} for k in ks}
    type_totals: dict[str, dict[int, dict[str, float]]] = {}
    type_counts: dict[str, int] = {}
    for case in queries:
        case_type = case.get("type", "unclassified")
        relevant_ids = set(case["relevant_ids"])
        row: dict = {"id": case["id"], "type": case_type, "query": case["query"], "relevant_ids": sorted(relevant_ids), "methods": {}}
        print(f"\n[{case['id']}] ({case_type}) {case['query']}")
        if case_type not in type_totals:
            type_totals[case_type] = {k: {name: 0.0 for name in methods} for k in ks}
            type_counts[case_type] = 0
        type_counts[case_type] += 1
        for name, search in methods.items():
            result_ids = [item["id"] for item in search(case["query"])]
            scores = {f"recall_at_{k}": recall_at_k(result_ids[:k], relevant_ids) for k in ks}
            for k in ks:
                totals[k][name] += scores[f"recall_at_{k}"]
                type_totals[case_type][k][name] += scores[f"recall_at_{k}"]
            row["methods"][name] = {**scores, "result_ids": result_ids}
            score_text = ", ".join(f"R@{k}={scores[f'recall_at_{k}']:.3f}" for k in ks)
            print(f"  {name:10} {score_text}  results={', '.join(result_ids)}")
        all_results.append(row)
    count = len(queries)
    averages = {str(k): {name: total / count for name, total in totals[k].items()} for k in ks}
    averages_by_type = {
        case_type: {
            str(k): {name: total / type_counts[case_type] for name, total in type_totals[case_type][k].items()}
            for k in ks
        }
        for case_type in type_totals
    }
    print("\n평균 Recall@k")
    for k in ks:
        print(f"  Recall@{k}: " + ", ".join(f"{name}={score:.3f}" for name, score in averages[str(k)].items()))
    print("\n유형별 평균 Recall@k")
    for case_type, scores_by_k in averages_by_type.items():
        print(f"  [{case_type}] (n={type_counts[case_type]})")
        for k in ks:
            print(f"    Recall@{k}: " + ", ".join(f"{name}={score:.3f}" for name, score in scores_by_k[str(k)].items()))
    if args.output:
        payload = {
            "ks": ks,
            "input": str(args.input),
            "query_count": count,
            "average_recall_at_k": averages,
            "average_recall_at_k_by_type": averages_by_type,
            "queries": all_results,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n상세 결과: {args.output}")


if __name__ == "__main__":
    main()
