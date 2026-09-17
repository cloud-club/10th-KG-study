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
import re
from datetime import datetime, timezone
from pathlib import Path

from common import CHUNKS, WEEK3_DATA, load_chunks_by_id
from gen1_es import search_bm25
from gen2_pgvector import search_vector
from hybrid_search import reciprocal_rank_fusion

QUESTIONS_FILE = Path(__file__).resolve().parent.parent / "queries" / "questions.json"
POOL_FILE = WEEK3_DATA / "candidate_pool.json"
POOL_MD = WEEK3_DATA / "candidate_pool.md"
QRELS_FILE = WEEK3_DATA / "qrels.json"
EVALUATION_JSON = WEEK3_DATA / "evaluation.json"
EVALUATION_MD = WEEK3_DATA / "evaluation.md"
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


def build_pool(questions: list[dict], corpus: dict[str, dict]) -> tuple[list, dict]:
    """실제 검색 순위를 보존하고, 같은 정보 요구의 후보만 ID로 합친다."""
    pool_rows = []
    groups = {}
    for q in questions:
        bm25 = search_bm25(q["query"], RETRIEVER_DEPTH)
        vector = search_vector(q["query"], RETRIEVER_DEPTH)
        hybrid = reciprocal_rank_fusion([bm25, vector], limit=POOL_DEPTH)
        rankings = {"bm25": bm25[:POOL_DEPTH], "vector": vector[:POOL_DEPTH], "hybrid": hybrid}
        by_id: dict[str, dict] = {}
        for method, rows in rankings.items():
            for row in rows:
                local = corpus.get(row["id"])
                if local is None or any(local.get(k, "") != row.get(k, "") for k in ("title", "source", "heading", "text")):
                    raise ValueError(f'{q["id"]}: DB 결과와 로컬 청크가 다릅니다. 재색인 없이 먼저 상태를 확인하세요.')
                item = by_id.setdefault(row["id"], {k: row.get(k, "") for k in ("id", "title", "source", "heading", "text")})
                item[f"{method}_rank"] = row["rank"]
        pool_rows.append({
            "question": q, "candidates": list(by_id.values()),
            "retrieval": {m: [{"id": r["id"], "rank": r["rank"], "score": r["score"]} for r in rows]
                          for m, rows in (("bm25", bm25), ("vector", vector))},
        })
        group_id = q.get("gold_group", q["id"])
        group = groups.setdefault(group_id, {
            "question_ids": [], "labeling_rule": q["labeling_rule"], "candidates": {},
        })
        if group["labeling_rule"] != q["labeling_rule"]:
            raise ValueError("같은 판정 묶음의 기준이 일치하지 않습니다.")
        group["question_ids"].append(q["id"])
        for chunk_id, item in by_id.items():
            candidate = group["candidates"].setdefault(chunk_id, {**{k: item[k] for k in ("id", "title", "source", "heading", "text")}, "ranks": {}})
            candidate["ranks"][q["id"]] = {m: item.get(f"{m}_rank") for m in rankings}
    for group in groups.values():
        # 검색기 순위로 판단을 유도하지 않도록 ID 순으로 보여준다.
        group["candidates"] = [dict(item, label_id=f'C{i:03d}') for i, (_, item) in enumerate(sorted(group["candidates"].items()), 1)]
    return pool_rows, groups


def render_pool(questions: list[dict], groups: dict) -> str:
    by_id = {q["id"]: q for q in questions}
    md = ["# W3 라벨링 후보", "", "모든 후보는 미판정입니다. 순위는 relevance 정답이 아닙니다.",
          "`R01 C001 관련 — 이유`처럼 번호로 답하거나 qrels.json의 label/note를 작성하세요.",
          "label: null(미판정), relevant(관련), irrelevant(무관), unsure(보류).", "",
          "표기 비교 쌍은 후보를 합쳐 한 번만 판정합니다. 다른 질문의 같은 청크는 별도로 판정합니다.", ""]
    for group_id, group in groups.items():
        md.extend([f'## {group_id} ({len(group["candidates"])}개)', ""])
        for qid in group["question_ids"]:
            md.append(f'- {qid}: {by_id[qid]["query"]}')
        md.extend(["", f'판정 기준: {group["labeling_rule"]}', ""])
        for row in group["candidates"]:
            md.extend([f'### {group_id} {row["label_id"]}', "", f'청크 ID: `{row["id"]}`',
                       f'제목: {row["title"]}', f'경로: {row["source"]}', f'헤딩: {row["heading"]}',
                       "", "판정: 미판정 / 이유: 미작성", "", "| 질문 | BM25 | Vector | Hybrid |", "|---|---:|---:|---:|"])
            for qid in group["question_ids"]:
                ranks = row["ranks"].get(qid, {})
                md.append(f'| {qid} | ' + ' | '.join(str(ranks.get(m) or '—') for m in ('bm25', 'vector', 'hybrid')) + ' |')
            # 원문 Markdown을 실행하거나 외부 이미지를 불러오지 않도록 코드 블록으로 표시한다.
            fence = '`' * max(3, max((len(s) for s in re.findall(r'`+', row['text'])), default=0) + 1)
            md.extend(["", "—: 해당 질문·검색기의 top-10에 없음", "", fence + 'text', row['text'], fence, ""])
    return '\n'.join(md)


def make_pool() -> None:
    questions = _require_review_complete(load_questions())
    if any(p.exists() for p in (POOL_FILE, POOL_MD, QRELS_FILE)):
        raise SystemExit("기존 후보 풀 또는 qrels가 있습니다. 사용자 라벨을 보존하기 위해 덮어쓰지 않습니다.")
    fingerprint = _corpus_fingerprint()
    pool_rows, groups = build_pool(questions, load_chunks_by_id())
    if fingerprint != _corpus_fingerprint():
        raise SystemExit("검색 도중 청크 파일이 변경되었습니다. 산출물을 저장하지 않습니다.")
    metadata = {"version": 2, "created_at": datetime.now(timezone.utc).isoformat(),
                "corpus": fingerprint, "pool_depth": POOL_DEPTH, "retriever_depth": RETRIEVER_DEPTH,
                "rrf_k": 60, "queries": pool_rows, "groups": groups}
    qrels = {"version": 2, "corpus": fingerprint, "assessment": "binary",
             "label_values": {"null": "미판정", "relevant": "관련", "irrelevant": "무관", "unsure": "판단 보류"},
             "queries": [{"id": q["id"], "query": q["query"], "kind": q["kind"], "judgment_group": q.get("gold_group", q["id"])} for q in questions],
             "judgment_groups": {gid: {
                 "status": "unlabeled", "labeling_rule": group["labeling_rule"],
                 "judgments": [{"id": r["id"], "label_id": r["label_id"], "label": None, "note": ""} for r in group["candidates"]],
                 "notes": "후보 밖 청크도 같은 형식으로 추가할 수 있습니다.",
             } for gid, group in groups.items()}}
    WEEK3_DATA.mkdir(parents=True, exist_ok=True)
    POOL_FILE.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    POOL_MD.write_text(render_pool(questions, groups), encoding="utf-8")
    QRELS_FILE.write_text(json.dumps(qrels, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in pool_rows:
        print(f'{row["question"]["id"]}: top-10 합집합 {len(row["candidates"])}개')
    print(f'라벨링 묶음 {len(groups)}개, 판정 항목 {sum(len(g["candidates"]) for g in groups.values())}개 (모두 미판정)')
    print(f"후보 풀 저장: {POOL_MD}")
    print(f"골드셋 템플릿: {QRELS_FILE}")


def _recall(ids: list[str], gold: set[str], k: int) -> float:
    return len(set(ids[:k]) & gold) / len(gold)


def _evaluation_queries(qrels: dict, corpus_ids: set[str]) -> tuple[list[dict], list[str]]:
    """qrels v2의 공유 판정 묶음을 질문별 gold 집합으로 연결한다."""
    if qrels.get("version") != 2:
        raise SystemExit(f"지원하지 않는 qrels version입니다: {qrels.get('version')}")

    groups = qrels.get("judgment_groups", {})
    complete, skipped = [], []
    for query in qrels.get("queries", []):
        group_id = query.get("judgment_group")
        group = groups.get(group_id)
        if group is None:
            raise SystemExit(f'{query.get("id")}: 판정 묶음 {group_id!r}이 없습니다.')
        if group.get("status") != "complete":
            skipped.append(query["id"])
            continue

        judgments = group.get("judgments", [])
        ids = [item.get("id") for item in judgments]
        duplicates = sorted({chunk_id for chunk_id in ids if ids.count(chunk_id) > 1})
        if duplicates:
            raise SystemExit(f'{group_id}: 중복 chunk ID: {duplicates}')
        invalid = [item for item in judgments if item.get("label") not in {"relevant", "irrelevant"}]
        if invalid:
            raise SystemExit(f'{group_id}: complete 묶음에 미판정 또는 보류 항목이 {len(invalid)}개 있습니다.')

        gold = {item["id"] for item in judgments if item["label"] == "relevant"}
        if not gold:
            raise SystemExit(f'{group_id}: relevant가 비어 있습니다. 이 묶음은 Recall 평가에서 complete로 둘 수 없습니다.')
        missing = gold - corpus_ids
        if missing:
            raise SystemExit(f'{group_id}: 존재하지 않는 chunk ID: {sorted(missing)}')
        complete.append({**query, "gold": gold})
    return complete, skipped


def _render_evaluation(result: dict) -> str:
    methods = ("bm25", "vector", "hybrid")
    lines = [
        "# W3 검색 Recall 평가", "",
        "동일한 qrels를 사용해 BM25, Vector, Hybrid를 비교했다.", "",
        "| Query | Gold | BM25@5 | Vector@5 | Hybrid@5 | BM25@10 | Vector@10 | Hybrid@10 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["queries"]:
        values = [row["recall"][method][str(k)] for k in (5, 10) for method in methods]
        lines.append(
            f'| {row["id"]} {row["query"]} | {row["gold_count"]} | '
            + " | ".join(f"{value:.3f}" for value in values) + " |"
        )
    averages = [result["macro_average"][method][str(k)] for k in (5, 10) for method in methods]
    lines.append("| **Macro average** |  | " + " | ".join(f"**{value:.3f}**" for value in averages) + " |")
    lines.extend(["", f'평가 질문: {result["evaluated_count"]}개', f'미완료 제외: {result["skipped_count"]}개'])
    if result["skipped_queries"]:
        lines.append("제외된 질문: " + ", ".join(result["skipped_queries"]))

    if result["spelling_pairs"]:
        lines.extend(["", "## 표기 비교", "",
                      "아래 값은 두 번째 질문의 Recall에서 첫 번째 질문의 Recall을 뺀 값이다.", "",
                      "| 비교 | BM25@5 | Vector@5 | Hybrid@5 | BM25@10 | Vector@10 | Hybrid@10 |",
                      "|---|---:|---:|---:|---:|---:|---:|"])
        for pair in result["spelling_pairs"]:
            deltas = [pair["delta"][method][str(k)] for k in (5, 10) for method in methods]
            lines.append(f'| {pair["second"]} - {pair["first"]} | ' + " | ".join(f"{value:+.3f}" for value in deltas) + " |")

    lines.extend(["", "Recall의 분모는 각 질문에 연결된 라벨링 완료 relevant 청크 집합이다.",
                  "이 정답표는 세 검색 방식의 top-10 합집합을 판정해 만들었으므로, 전체 코퍼스의 모든 정답을 포함한다고 보장하지 않는다.", ""])
    return "\n".join(lines)


def run_evaluation() -> None:
    qrels = json.loads(QRELS_FILE.read_text(encoding="utf-8"))
    if qrels.get("corpus") != _corpus_fingerprint():
        raise SystemExit("청크 파일이 라벨링 때와 달라졌습니다. 후보 풀과 qrels를 다시 확인하세요.")
    corpus_ids = set(load_chunks_by_id())
    complete, skipped = _evaluation_queries(qrels, corpus_ids)
    if not complete:
        raise SystemExit("status=complete인 라벨링 질문이 없습니다.")

    methods = ("bm25", "vector", "hybrid")
    totals = {m: {5: 0.0, 10: 0.0} for m in ("bm25", "vector", "hybrid")}
    rows = []
    for q in complete:
        gold = q["gold"]
        bm25 = search_bm25(q["query"], RETRIEVER_DEPTH)
        vector = search_vector(q["query"], RETRIEVER_DEPTH)
        hybrid = reciprocal_rank_fusion([bm25, vector], limit=10)
        ids = {"bm25": [r["id"] for r in bm25], "vector": [r["id"] for r in vector], "hybrid": [r["id"] for r in hybrid]}
        recall = {method: {} for method in methods}
        for k in (5, 10):
            for method in methods:
                value = _recall(ids[method], gold, k)
                totals[method][k] += value
                recall[method][str(k)] = value
        rows.append({"id": q["id"], "query": q["query"], "judgment_group": q["judgment_group"],
                     "gold_count": len(gold), "recall": recall,
                     "retrieved_ids": {method: ids[method][:10] for method in methods}})

    n = len(complete)
    averages = {method: {str(k): totals[method][k] / n for k in (5, 10)} for method in methods}
    by_id = {row["id"]: row for row in rows}
    pairs = []
    for first, second in (("R07", "R08"), ("R09", "R10")):
        if first in by_id and second in by_id:
            pairs.append({"first": first, "second": second,
                          "delta": {method: {str(k): by_id[second]["recall"][method][str(k)] - by_id[first]["recall"][method][str(k)]
                                             for k in (5, 10)} for method in methods}})
    result = {
        "version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "corpus": qrels["corpus"],
        "qrels_version": qrels["version"], "pool_limited_gold": True,
        "evaluated_count": n, "skipped_count": len(skipped), "skipped_queries": skipped,
        "queries": rows, "macro_average": averages, "spelling_pairs": pairs,
    }
    WEEK3_DATA.mkdir(parents=True, exist_ok=True)
    EVALUATION_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report = _render_evaluation(result)
    EVALUATION_MD.write_text(report, encoding="utf-8")
    print(report)
    print(f"상세 결과: {EVALUATION_JSON}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=("review", "pool", "run"), default="review")
    args = parser.parse_args()
    {"review": review, "pool": make_pool, "run": run_evaluation}[args.command]()


if __name__ == "__main__":
    main()
