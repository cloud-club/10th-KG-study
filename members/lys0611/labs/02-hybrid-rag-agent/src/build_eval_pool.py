#!/usr/bin/env python3
"""질문별 BM25·벡터·RRF 후보를 비공개 JSONL로 모아 수동 라벨링을 돕는다."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from common import LAB_ROOT, RRF_CANDIDATE_K
from hybrid import HybridSearchEngine
from models import SearchFilters


def _parse_filters(data: dict) -> SearchFilters:
    raw = data.get("filters") or {}
    return SearchFilters(
        room=raw.get("room") or None,
        date_from=datetime.fromisoformat(raw["date_from"]) if raw.get("date_from") else None,
        date_to=datetime.fromisoformat(raw["date_to"]) if raw.get("date_to") else None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("questions", type=Path, help="qid/question/category/filters JSONL")
    parser.add_argument("--out", type=Path, default=LAB_ROOT / "data/private/eval-pool.jsonl")
    parser.add_argument("--candidate-k", type=int, default=RRF_CANDIDATE_K)
    parser.add_argument("--exact-vector", action="store_true")
    args = parser.parse_args()
    if "private" not in args.out.parts:
        parser.error("원문 후보 파일은 반드시 private 경로 아래에 저장해야 합니다.")

    questions = [json.loads(line) for line in args.questions.read_text(encoding="utf-8").splitlines() if line.strip()]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with HybridSearchEngine() as engine, args.out.open("w", encoding="utf-8") as handle:
        engine.preflight()
        for index, question in enumerate(questions, start=1):
            run = engine.search(
                question["question"],
                filters=_parse_filters(question),
                candidate_k=args.candidate_k,
                exact_vector=args.exact_vector,
            )
            candidates = []
            for hit in run.hybrid:
                chunk = run.chunks[hit.chunk_id]
                candidates.append(
                    {
                        "content_hash": hit.content_hash,
                        "chunk_id": hit.chunk_id,
                        "room": chunk.room,
                        "start_at": chunk.start_at.isoformat(),
                        "start_seq": chunk.start_seq,
                        "end_seq": chunk.end_seq,
                        "ranks": hit.ranks,
                        "text": chunk.text,
                    }
                )
            handle.write(
                json.dumps(
                    {
                        "qid": question["qid"],
                        "question": run.masked_query,
                        "category": question.get("category"),
                        "candidates": candidates,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            print(f"[{index:02d}/{len(questions):02d}] {question['qid']}")
    print(args.out)


if __name__ == "__main__":
    main()
