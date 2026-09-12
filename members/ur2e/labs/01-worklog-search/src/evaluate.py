"""grep / BM25 / pgvector 를 evaluation/queries.jsonl 전체로 돌려 Hit@3, MRR을 비교한다.

세 방식 모두 같은 청크 집합을 검색하지만 순위가 매겨지는 방식이 다르다.
grep 은 순위가 없어서(파일에 나온 순서) Hit@k, MRR 자체가 다른 두 방식과
공정하게 비교되지 않는다는 점을 그대로 드러내려고 결과에 남겨둔다.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from common import EVAL_RESULTS_PATH, ES_INDEX, PG_TABLE, QUERIES_PATH
from search_elasticsearch import search_bm25
from search_grep import search_grep
from search_pgvector import search_vector

POOL = 10  # MRR 계산을 위해 각 방식에서 넉넉히 가져올 개수
K = 3  # Hit@K


def load_queries() -> list[dict[str, Any]]:
    return [json.loads(line) for line in QUERIES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def ranked_source_paths(chunks: list[dict[str, Any]]) -> list[str]:
    """청크 리스트를 문서(source_path) 순위로 접는다. 같은 문서의 여러 청크가
    나오면 가장 먼저(가장 순위가 높은) 나온 것만 남긴다."""
    seen: list[str] = []
    for chunk in chunks:
        if chunk["source_path"] not in seen:
            seen.append(chunk["source_path"])
    return seen


def hit_at_k(ranked: list[str], expected: set[str], k: int) -> int:
    return int(any(path in expected for path in ranked[:k]))


def mrr(ranked: list[str], expected: set[str]) -> float:
    for i, path in enumerate(ranked, start=1):
        if path in expected:
            return 1 / i
    return 0.0


def run_method(
    name: str,
    query: str,
    chunks: list[dict[str, Any]] | None = None,
    index_name: str = ES_INDEX,
    table_name: str = PG_TABLE,
) -> list[str]:
    if name == "grep":
        rows, _ = search_grep(query, limit=POOL, chunks=chunks)
        return ranked_source_paths(rows)
    if name == "bm25":
        rows, _ = search_bm25(query, limit=POOL, index_name=index_name)
        return ranked_source_paths([doc for doc, _ in rows])
    if name == "vector":
        rows, _ = search_vector(query, limit=POOL, table_name=table_name)
        return ranked_source_paths([doc for doc, _ in rows])
    raise ValueError(name)


def evaluate(
    chunks: list[dict[str, Any]] | None = None,
    index_name: str = ES_INDEX,
    table_name: str = PG_TABLE,
    methods: tuple[str, ...] = ("grep", "bm25", "vector"),
    on_progress=None,
) -> list[dict[str, Any]]:
    queries = load_queries()
    results: list[dict[str, Any]] = []
    for q in queries:
        expected = set(q["expected_primary"])
        row: dict[str, Any] = {"id": q["id"], "type": q["type"]}
        for method in methods:
            ranked = run_method(method, q["query"], chunks, index_name, table_name)
            row[f"{method}_hit@{K}"] = hit_at_k(ranked, expected, K)
            row[f"{method}_mrr"] = mrr(ranked, expected)
            row[f"{method}_top1"] = ranked[0] if ranked else None
        results.append(row)
        if on_progress:
            on_progress(q)
        else:
            print(f"  {q['id']} ({q['type']}) 처리 완료")
    return results


def summarize(results: list[dict[str, Any]], methods: tuple[str, ...] = ("grep", "bm25", "vector")) -> None:
    def block(rows: list[dict[str, Any]], label: str) -> None:
        n = len(rows)
        print(f"\n{label} (n={n})")
        print(f"{'':14} " + "".join(f"{m:>16}" for m in methods))
        print(f"{'Hit@' + str(K):14} " + "".join(f"{sum(r[f'{m}_hit@{K}'] for r in rows) / n:>16.2f}" for m in methods))
        print(f"{'MRR':14} " + "".join(f"{sum(r[f'{m}_mrr'] for r in rows) / n:>16.2f}" for m in methods))

    block(results, "전체")

    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        by_type[r["type"]].append(r)
    for type_name in sorted(by_type):
        block(by_type[type_name], type_name)


def main() -> None:
    print(f"질문 {len(load_queries())}건을 grep / BM25 / pgvector 로 실행합니다 (pgvector는 OpenAI 호출)...")
    results = evaluate()
    summarize(results)

    EVAL_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVAL_RESULTS_PATH.open("w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\n원본 결과 저장: {EVAL_RESULTS_PATH}")


if __name__ == "__main__":
    main()
