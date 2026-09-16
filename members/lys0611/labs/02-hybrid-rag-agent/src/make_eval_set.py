#!/usr/bin/env python3
"""라벨링 결과(qid → 정답 chunk_id 묶음)를 content_hash 기반 평가 JSONL로 굳힌다.

라벨 명세 파일은 사람이 후보 풀(build_eval_pool.py)과 원문 주변 메시지를 읽고 작성한다.
chunk_id는 재적재 때 바뀔 수 있으므로 저장은 항상 content_hash로 한다.

  python src/make_eval_set.py data/private/labels.json --out data/private/eval.jsonl

labels.json 형식:
  [{"qid": "q001", "question": "...", "category": "exact|semantic|hard",
    "filters": {"room": null}, "answerable": true, "retrieval_evaluable": true,
    "gold": {"evidence_id": [chunk_id, ...], ...},   # 한 evidence_id 안의 chunk는 대체 가능(overlap)
    "reference_answer": "...", "failure_tags": ["..."]}]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import LAB_ROOT, get_pg
from dataset import load_eval_set


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labels", type=Path)
    parser.add_argument("--out", type=Path, default=LAB_ROOT / "data/private/eval.jsonl")
    args = parser.parse_args()
    if "private" not in args.out.parts:
        parser.error("평가셋은 질문 원문을 담으므로 private 경로 아래에 저장해야 합니다.")

    labels = json.loads(args.labels.read_text(encoding="utf-8"))
    wanted = sorted({cid for item in labels for ids in item.get("gold", {}).values() for cid in ids})
    hashes: dict[int, str] = {}
    if wanted:
        with get_pg() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, content_hash FROM chunks WHERE id = ANY(%s)", (wanted,))
            hashes = {int(cid): content_hash for cid, content_hash in cur.fetchall()}
    missing = sorted(set(wanted) - set(hashes))
    if missing:
        raise SystemExit(f"코퍼스에 없는 chunk_id: {missing}")

    lines = []
    for item in labels:
        record = {
            "schema_version": 1,
            "qid": item["qid"],
            "question": item["question"],
            "category": item["category"],
            "filters": item.get("filters") or {},
            "answerable": item.get("answerable", True),
            "retrieval_evaluable": item.get("retrieval_evaluable", True),
            "gold_evidence": [
                {
                    "evidence_id": evidence_id,
                    "gold_chunk_ids": ids,  # 참고용. 평가는 hash로만 한다.
                    "acceptable_content_hashes": [hashes[cid] for cid in ids],
                }
                for evidence_id, ids in (item.get("gold") or {}).items()
            ],
            "reference_answer": item.get("reference_answer"),
            "failure_tags": item.get("failure_tags") or [],
        }
        lines.append(json.dumps(record, ensure_ascii=False))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    questions = load_eval_set(args.out)  # 스키마 검증
    evaluable = sum(q.answerable and q.retrieval_evaluable for q in questions)
    print(f"{args.out}: {len(questions)} questions, {evaluable} retrieval-evaluable")


if __name__ == "__main__":
    main()
