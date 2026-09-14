"""W3 질문 검토, pooled judging, Recall@5/10 평가.

순서:
    ./.venv/bin/python src/evaluate.py review
    # queries/questions.json에서 질문을 확정하고 status를 ready/exclude로 변경
    ./.venv/bin/python src/evaluate.py pool
    # data/week3/qrels.json을 사람이 라벨링
    ./.venv/bin/python src/evaluate.py run
"""
import argparse
import hashlib
import json
from pathlib import Path

from common import CHUNKS, WEEK3_DATA, load_chunks_by_id
from gen1_es import search_bm25
from gen2_pgvector import search_vector
from hybrid_search import reciprocal_rank_fusion

QUESTIONS_FILE = Path(__file__).resolve().parent.parent / "queries" / "questions.json"
POOL_FILE = WEEK3_DATA / "candidate_pool.json"
POOL_MD = WEEK3_DATA / "candidate_pool.md"
QRELS_FILE = WEEK3_DATA / "qrels.json"
POOL_DEPTH = 10
RETRIEVER_DEPTH = 50


def load_questions() -> list[dict]:
    return json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]


def review() -> None:
    questions = load_questions()
    print("기존 W2 질문의 W3 relevance 평가 적합성")
    print("| ID | 상태 | 기존 질문 | 제안 질문 | 판단 이유 |")
    print("|---|---|---|---|---|")
    for q in questions:
        values = [q["id"], q["status"], q["original_query"], q["query"], q["reason"]]
        print("| " + " | ".join(v.replace("|", "\\|") for v in values) + " |")
    counts = {state: sum(q["status"] == state for q in questions) for state in ("ready", "revise", "exclude")}
    print(f"\nready {counts['ready']} / revise {counts['revise']} / exclude {counts['exclude']}")
    print("pool은 revise 질문이 남아 있으면 실행되지 않습니다.")


def _require_review_complete(questions: list[dict]) -> list[dict]:
    pending = [q["id"] for q in questions if q["status"] == "revise"]
    unknown = [q["id"] for q in questions if q["status"] not in {"ready", "exclude"}]
    if pending or unknown:
        ids = pending + unknown
        raise SystemExit(f"질문 검토가 끝나지 않았습니다: {', '.join(dict.fromkeys(ids))}")
    ready = [q for q in questions if q["status"] == "ready"]
    if not ready:
        raise SystemExit("평가할 ready 질문이 없습니다.")
    return ready


def _corpus_fingerprint() -> str:
    digest = hashlib.sha256()
    with CHUNKS.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def make_pool() -> None:
    questions = _require_review_complete(load_questions())
    WEEK3_DATA.mkdir(parents=True, exist_ok=True)
    pool_rows = []
    qrels_rows = []
    md = ["# W3 relevance 후보 풀", "", "각 청크를 읽고 relevant 여부를 판단한 뒤 `qrels.json`에 기록한다.", ""]

    for q in questions:
        bm25 = search_bm25(q["query"], RETRIEVER_DEPTH)
        vector = search_vector(q["query"], RETRIEVER_DEPTH)
        hybrid = reciprocal_rank_fusion([bm25, vector], limit=POOL_DEPTH)
        rankings = {"bm25": bm25[:POOL_DEPTH], "vector": vector[:POOL_DEPTH], "hybrid": hybrid}
        by_id: dict[str, dict] = {}
        for method, rows in rankings.items():
            for row in rows:
                item = by_id.setdefault(row["id"], {k: row.get(k, "") for k in ("id", "title", "source", "heading", "text")})
                item[f"{method}_rank"] = row["rank"]
        candidates = sorted(
            by_id.values(),
            key=lambda r: (min(r.get(f"{m}_rank", 10**9) for m in rankings), r["id"]),
        )
        pool_rows.append({"question": q, "candidates": candidates})
        qrels_rows.append({
            "id": q["id"], "query": q["query"], "status": "unlabeled",
            "labeling_rule": q["labeling_rule"], "relevant": [],
            "judged_pool_ids": [row["id"] for row in candidates],
            "notes": "후보 풀 밖에서 찾은 정답 청크도 relevant에 추가할 수 있다.",
        })
        md.extend([f'## {q["id"]} — {q["query"]}', "", q["labeling_rule"], ""])
        for row in candidates:
            ranks = ", ".join(f"{m}={row.get(f'{m}_rank', '-')}" for m in rankings)
            md.extend([f'### `{row["id"]}` ({ranks})', "", f'title: {row["title"]}', f'source: {row["source"]}', "", row["text"], ""])

    metadata = {"version": 1, "corpus": _corpus_fingerprint(), "pool_depth": POOL_DEPTH, "queries": pool_rows}
    POOL_FILE.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    POOL_MD.write_text("\n".join(md), encoding="utf-8")
    qrels = {"version": 1, "corpus": metadata["corpus"], "assessment": "binary", "queries": qrels_rows}
    if QRELS_FILE.exists():
        print(f"기존 qrels를 보존했습니다: {QRELS_FILE}")
    else:
        QRELS_FILE.write_text(json.dumps(qrels, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"후보 풀 저장: {POOL_MD}")
    print(f"골드셋 템플릿: {QRELS_FILE}")


def _recall(ids: list[str], gold: set[str], k: int) -> float:
    return len(set(ids[:k]) & gold) / len(gold)


def run_evaluation() -> None:
    qrels = json.loads(QRELS_FILE.read_text(encoding="utf-8"))
    if qrels.get("corpus") != _corpus_fingerprint():
        raise SystemExit("청크 파일이 라벨링 때와 달라졌습니다. 후보 풀과 qrels를 다시 확인하세요.")
    corpus_ids = set(load_chunks_by_id())
    complete = [q for q in qrels["queries"] if q["status"] == "complete"]
    skipped = [q["id"] for q in qrels["queries"] if q["status"] != "complete"]
    if not complete:
        raise SystemExit("status=complete인 라벨링 질문이 없습니다.")

    print("| Query | BM25@5 | Vector@5 | Hybrid@5 | BM25@10 | Vector@10 | Hybrid@10 |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    totals = {m: {5: 0.0, 10: 0.0} for m in ("bm25", "vector", "hybrid")}
    for q in complete:
        gold = {item["id"] if isinstance(item, dict) else item for item in q["relevant"]}
        missing = gold - corpus_ids
        if not gold:
            raise SystemExit(f'{q["id"]}: relevant가 비어 있습니다. no-answer 질문은 검색 Recall 평가에서 제외하세요.')
        if missing:
            raise SystemExit(f'{q["id"]}: 존재하지 않는 chunk ID: {sorted(missing)}')
        bm25 = search_bm25(q["query"], RETRIEVER_DEPTH)
        vector = search_vector(q["query"], RETRIEVER_DEPTH)
        hybrid = reciprocal_rank_fusion([bm25, vector], limit=10)
        ids = {"bm25": [r["id"] for r in bm25], "vector": [r["id"] for r in vector], "hybrid": [r["id"] for r in hybrid]}
        values = []
        for k in (5, 10):
            for method in ("bm25", "vector", "hybrid"):
                value = _recall(ids[method], gold, k)
                totals[method][k] += value
                values.append(value)
        # 표 열 순서에 맞게 @5 세 개, @10 세 개를 출력한다.
        print(f'| {q["id"]} {q["query"]} | ' + " | ".join(f"{v:.3f}" for v in values) + " |")
    n = len(complete)
    averages = [totals[m][k] / n for k in (5, 10) for m in ("bm25", "vector", "hybrid")]
    print("| **Macro average** | " + " | ".join(f"**{v:.3f}**" for v in averages) + " |")
    print(f"\n평가 질문 {n}개; 미완료 제외 {len(skipped)}개" + (f" ({', '.join(skipped)})" if skipped else ""))
    print("Recall 분모는 각 질문에서 사람이 complete로 확정한 relevant 청크 집합입니다.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=("review", "pool", "run"), default="review")
    args = parser.parse_args()
    {"review": review, "pool": make_pool, "run": run_evaluation}[args.command]()


if __name__ == "__main__":
    main()
