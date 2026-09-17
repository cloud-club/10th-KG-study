#!/usr/bin/env python3
"""키워드·벡터·하이브리드 검색의 Recall@K·nDCG@K를 비교한다."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import psycopg
from elasticsearch import Elasticsearch


SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from common import LAB_ROOT, get_env, load_documents
from retrieval.hybrid.search import hybrid_search
from retrieval.keyword.search import search_documents as keyword_search
from retrieval.vector.search import search_documents as vector_search


QUESTIONS_PATH = LAB_ROOT / "data" / "evaluation" / "questions.jsonl"
METHOD_LABELS = {"keyword": "키워드(BM25)", "vector": "벡터", "hybrid": "하이브리드"}
METRICS = ("recall", "ndcg")


def recall_at_k(retrieved_ids: list[str], reference_ids: list[str], k: int) -> float:
    if not reference_ids:
        raise ValueError("reference_chunk_ids가 비어 있는 질문은 평가할 수 없습니다.")
    top_k = set(retrieved_ids[:k])
    found = sum(1 for reference_id in reference_ids if reference_id in top_k)
    return found / len(reference_ids)


def ndcg_at_k(retrieved_ids: list[str], relevance: dict[str, int], k: int) -> float:
    """graded relevance(0~3 등)로 nDCG@K를 계산한다. 등급이 없으면 정답 여부만(0/1) 반영한다."""
    if not relevance:
        raise ValueError("relevance 판정이 비어 있는 질문은 평가할 수 없습니다.")

    def dcg(gains: list[int]) -> float:
        return sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))

    gains = [relevance.get(chunk_id, 0) for chunk_id in retrieved_ids[:k]]
    ideal_gains = sorted(relevance.values(), reverse=True)[:k]
    idcg = dcg(ideal_gains)
    return dcg(gains) / idcg if idcg > 0 else 0.0


def question_relevance(question: dict) -> dict[str, int]:
    """graded_relevance(TREC pooling + LLM judge 결과)가 있으면 그대로, 없으면 reference_chunk_ids를
    이진(1점) relevance로 취급한다."""
    graded = question.get("graded_relevance")
    if graded:
        return graded
    return {chunk_id: 1 for chunk_id in question["reference_chunk_ids"]}


def evaluate(
    questions: list[dict],
    es_client: Elasticsearch,
    es_url: str,
    postgres,
    ks: list[int],
    rank_window: int,
    rank_constant: int,
) -> dict[str, dict[int, dict[str, float]]]:
    max_k = max(ks)
    effective_window = max(rank_window, max_k)
    scores: dict[str, dict[int, dict[str, list[float]]]] = {
        method: {k: {metric: [] for metric in METRICS} for k in ks} for method in METHOD_LABELS
    }

    for question in questions:
        reference_ids = question["reference_chunk_ids"]
        relevance = question_relevance(question)
        results_by_method = {
            "keyword": keyword_search(es_client, question["question"], max_k),
            "vector": vector_search(postgres, question["question"], max_k),
            "hybrid": hybrid_search(
                es_url,
                postgres,
                question["question"],
                limit=max_k,
                rank_window=effective_window,
                rank_constant=rank_constant,
            ),
        }
        for method, results in results_by_method.items():
            retrieved_ids = [result["id"] for result in results]
            for k in ks:
                scores[method][k]["recall"].append(recall_at_k(retrieved_ids, reference_ids, k))
                scores[method][k]["ndcg"].append(ndcg_at_k(retrieved_ids, relevance, k))

    return {
        method: {
            k: {metric: sum(values) / len(values) for metric, values in metric_scores.items()}
            for k, metric_scores in k_scores.items()
        }
        for method, k_scores in scores.items()
    }


def print_table(scores: dict[str, dict[int, dict[str, float]]], ks: list[int]) -> None:
    header = "방식".ljust(14) + "".join(
        f"recall@{k}".rjust(12) + f"ndcg@{k}".rjust(11) for k in ks
    )
    print(header)
    for method, label in METHOD_LABELS.items():
        row = label.ljust(14) + "".join(
            f"{scores[method][k]['recall']:.3f}".rjust(12) + f"{scores[method][k]['ndcg']:.3f}".rjust(11)
            for k in ks
        )
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ground Truth 질문으로 키워드·벡터·하이브리드 검색의 Recall@K·nDCG@K를 비교합니다."
    )
    parser.add_argument("--k", type=int, nargs="+", default=[1, 3, 5, 10], help="비교할 K 값 목록")
    parser.add_argument("--rank-window", type=int, default=20, help="하이브리드 RRF 후보 범위")
    parser.add_argument("--rank-constant", type=int, default=60, help="하이브리드 RRF 순위 상수")
    parser.add_argument("--questions", type=Path, default=QUESTIONS_PATH, help="평가 질문 JSONL 경로")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if any(k <= 0 for k in args.k):
        raise SystemExit("--k는 모두 1 이상이어야 합니다.")
    if args.rank_constant < 0:
        raise SystemExit("--rank-constant는 0 이상이어야 합니다.")

    questions = load_documents(args.questions)
    if not questions:
        raise SystemExit(f"평가 질문이 없습니다: {args.questions}")

    ks = sorted(set(args.k))
    es_url = get_env("ES_URL", "http://localhost:9200")
    dsn = get_env("POSTGRES_DSN", "postgresql://study:study@localhost:5432/personal_data")
    es_client = Elasticsearch(es_url)

    with psycopg.connect(dsn) as postgres:
        scores = evaluate(
            questions, es_client, es_url, postgres, ks, args.rank_window, args.rank_constant
        )

    if args.json:
        print(json.dumps(scores, ensure_ascii=False, indent=2))
    else:
        print_table(scores, ks)


if __name__ == "__main__":
    main()
