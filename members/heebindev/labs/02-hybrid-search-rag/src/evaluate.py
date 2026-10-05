"""골드셋을 기준으로 BM25, 벡터, RRF 검색의 Recall@k를 비교한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentence_transformers import SentenceTransformer

from hybrid_search import (
    DEFAULT_DSN,
    DEFAULT_MODEL,
    reciprocal_rank_fusion,
    search_bm25,
    search_vector,
)


LAB_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goldset", type=Path, default=LAB_ROOT / "goldset.json")
    parser.add_argument("--k", type=int, default=5, help="평가할 상위 결과 수")
    parser.add_argument("--candidate-limit", type=int, default=20)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--url", default="http://127.0.0.1:9200")
    parser.add_argument("--index", default="notion_chunks")
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    return parser.parse_args()


def recall_at_k(results: list[dict], relevant_ids: set[str], k: int) -> tuple[int, float]:
    found_ids = {result["id"] for result in results[:k]} & relevant_ids
    return len(found_ids), len(found_ids) / len(relevant_ids)


def load_goldset(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as input_file:
        cases = json.load(input_file)
    if not isinstance(cases, list) or not cases:
        raise ValueError("골드셋은 질문이 1개 이상인 JSON 배열이어야 합니다.")
    for number, case in enumerate(cases, start=1):
        if not isinstance(case.get("question"), str) or not case["question"].strip():
            raise ValueError(f"{number}번 질문이 비어 있습니다.")
        ids = case.get("relevant_chunk_ids")
        if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
            raise ValueError(f"{number}번 질문의 정답 청크 ID가 없거나 중복되었습니다.")
    return cases


def main() -> None:
    args = parse_args()
    if args.k <= 0 or args.candidate_limit < args.k:
        raise ValueError("--k는 1 이상이고 --candidate-limit 이하여야 합니다.")
    if args.rrf_k < 0:
        raise ValueError("--rrf-k는 0 이상이어야 합니다.")

    cases = load_goldset(args.goldset)
    print(f"평가 질문 {len(cases)}개, Recall@{args.k}, 후보 {args.candidate_limit}개씩")
    model = SentenceTransformer(args.model)
    method_names = ("BM25", "벡터", "RRF")
    scores: dict[str, list[float]] = {name: [] for name in method_names}

    for number, case in enumerate(cases, start=1):
        query = case["question"]
        relevant_ids = set(case["relevant_chunk_ids"])
        bm25_results = search_bm25(query, args.candidate_limit, args.url, args.index)
        vector_results = search_vector(
            query,
            args.candidate_limit,
            args.dsn,
            args.model,
            model=model,
        )
        fused_results = reciprocal_rank_fusion(bm25_results, vector_results, args.rrf_k)
        methods = {
            "BM25": bm25_results,
            "벡터": vector_results,
            "RRF": fused_results,
        }

        print(f"\n{number}. {query} (정답 {len(relevant_ids)}개)")
        for name, results in methods.items():
            found, recall = recall_at_k(results, relevant_ids, args.k)
            scores[name].append(recall)
            print(f"   {name:4s}: {found}/{len(relevant_ids)} = {recall:.2f}")

    print(f"\n평균 Recall@{args.k} (질문별 평균)")
    for name in method_names:
        print(f"   {name:4s}: {sum(scores[name]) / len(scores[name]):.2f}")
    print("참고: 현재 골드셋은 정답 후보 초안이므로 사람이 검토한 뒤 수치를 해석해야 합니다.")


if __name__ == "__main__":
    main()
