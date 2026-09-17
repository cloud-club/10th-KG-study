"""수동 정답 ID로 BM25·벡터·RRF Recall@k를 동일 조건에서 비교한다."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hybrid_search import HybridSearch, OUTPUT_DIR, RRF_C, corpus_manifest, load_corpus

DEFAULT_QUESTIONS = Path(__file__).resolve().parents[1] / "evaluation/questions.json"


def validate_questions(fixture: Any, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(fixture, dict) or not isinstance(fixture.get("questions"), list) or not fixture["questions"]:
        raise ValueError("평가 fixture에는 비어 있지 않은 questions 배열이 필요합니다.")
    by_id = {row["id"]: row for row in documents}
    seen: set[str] = set()
    for question in fixture["questions"]:
        if not isinstance(question, dict):
            raise ValueError("평가 질문은 객체여야 합니다.")
        identifier, query = question.get("id"), question.get("query")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            raise ValueError("평가 질문 ID는 비어 있지 않고 중복 없어야 합니다.")
        seen.add(identifier)
        if not isinstance(query, str) or not query.strip() or len(query) > 10000:
            raise ValueError("평가 질문 query가 올바르지 않습니다.")
        scope = question.get("scope")
        if scope not in {"own", "reference", "all"}:
            raise ValueError("평가 질문 scope가 올바르지 않습니다.")
        gold = question.get("relevant_ids")
        if not isinstance(gold, list) or not gold or any(not isinstance(value, str) or not value for value in gold) or len(set(gold)) != len(gold):
            raise ValueError("정답 문서 ID는 비어 있지 않은 중복 없는 문자열 배열이어야 합니다.")
        for source_id in gold:
            if source_id not in by_id or (scope != "all" and by_id[source_id]["corpus"] != scope):
                raise ValueError(f"정답 문서가 코퍼스 또는 질문 scope에 없습니다: {source_id}")
    return fixture["questions"]


def recall_at_k(ranked_ids: list[str], relevant_ids: list[str], k: int) -> float:
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("평가 k는 양의 정수여야 합니다.")
    gold = set(relevant_ids)
    if not gold or len(gold) != len(relevant_ids):
        raise ValueError("정답 문서 ID가 비었거나 중복됐습니다.")
    return len(set(ranked_ids[:k]) & gold) / len(gold)


def evaluate(fixture: dict[str, Any], documents: list[dict[str, Any]], search: HybridSearch,
             ks: list[int], candidates: int) -> dict[str, Any]:
    questions = validate_questions(fixture, documents)
    if not ks or any(isinstance(k, bool) or not isinstance(k, int) or k < 1 for k in ks) or len(set(ks)) != len(ks):
        raise ValueError("평가 ks는 중복 없는 양의 정수 목록이어야 합니다.")
    if isinstance(candidates, bool) or not isinstance(candidates, int) or not max(ks) <= candidates <= 1000:
        raise ValueError("후보 수는 최대 평가 k 이상, 1000 이하여야 합니다.")
    expected = corpus_manifest(documents)
    if search.manifest != expected:
        raise ValueError("평가 정답 검증 후 검색 코퍼스가 변경됐습니다.")
    per_query = []
    modes = ("bm25", "vector", "hybrid")
    for question in questions:
        entry = {"id": question["id"], "query": question["query"], "scope": question["scope"],
                 "relevant_ids": question["relevant_ids"], "results": {}}
        for mode in modes:
            rows = search.search(question["query"], mode=mode, limit=max(ks), candidates=candidates, scope=question["scope"])
            ids = [row["id"] for row in rows]
            entry["results"][mode] = {"ranking": [{key: row.get(key) for key in ("id", "score", "bm25_rank", "vector_rank")} for row in rows],
                                      "recall_at_k": {str(k): recall_at_k(ids, question["relevant_ids"], k) for k in sorted(ks)}}
        per_query.append(entry)
    macro = {mode: {str(k): sum(row["results"][mode]["recall_at_k"][str(k)] for row in per_query) / len(per_query)
                    for k in sorted(ks)} for mode in modes}
    return {"evaluated_at": datetime.now(timezone.utc).isoformat(), "description": fixture.get("description", ""),
            "manifest": expected, "corpus_ids": [row["id"] for row in documents], "question_count": len(questions),
            "ks": sorted(ks), "candidate_count_per_retriever": candidates, "rrf_constant": RRF_C,
            "vector_search": "pgvector cosine with HNSW index available (planner chooses); exact scoped scan own/reference", "macro_recall_at_k": macro,
            "per_query": per_query}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--ks", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--candidates", type=int, default=20)
    args = parser.parse_args()
    documents = load_corpus()
    fixture = json.loads(args.questions.read_text(encoding="utf-8"))
    # Reject every invalid gold label before constructing/querying a backend.
    validate_questions(fixture, documents)
    report = evaluate(fixture, documents, HybridSearch(), args.ks, args.candidates)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "evaluation.json"
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({"macro_recall_at_k": report["macro_recall_at_k"], "question_count": report["question_count"],
                      "output": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
