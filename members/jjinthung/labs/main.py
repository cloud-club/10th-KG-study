#!/usr/bin/env python3
"""BM25(Nori) + Vector 검색 및 GPT 답변 생성의 단일 진입점."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LABS = Path(__file__).resolve().parent
sys.path.insert(0, str(LABS / "03-compare"))
from search import search
sys.path.insert(0, str(LABS / "04-generate"))
from generate import generate_answer


def main() -> None:
    parser = argparse.ArgumentParser(description="BM25 + Vector 검색 후 GPT 답변 생성")
    parser.add_argument("query")
    parser.add_argument("--top-k", "--topk", type=int, default=5)
    parser.add_argument("--candidate-k", "--candidatek", type=int, default=30)
    parser.add_argument(
        "--model",
        default=None,
        help="OpenAI 모델명 (기본값: OPENAI_MODEL 또는 gpt-4o-mini)",
    )
    parser.add_argument(
        "--retrieve-only",
        action="store_true",
        help="GPT를 호출하지 않고 검색 결과만 JSON으로 출력",
    )
    parser.add_argument("--index-dir", type=Path, default=LABS.parent / "Data" / "index")
    parser.add_argument("--es-url", default="http://localhost:9200")
    parser.add_argument("--es-index", default="jjinthung-talk-chunks")
    args = parser.parse_args()

    required = [args.index_dir / name for name in ("bm25.json", "vectors.npy", "metadata.json")]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"검색 인덱스가 없습니다: {', '.join(missing)}")

    results = search(
        args.query,
        args.index_dir,
        args.top_k,
        args.candidate_k,
        args.es_url,
        args.es_index,
    )
    if args.retrieve_only:
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
        return

    print(generate_answer(args.query, results, args.model))


if __name__ == "__main__":
    main()
