#!/usr/bin/env python3
"""카톡에 한 번 질문하고 RRF 검색 trace·근거·답변을 확인한다."""
from __future__ import annotations

import argparse
from datetime import datetime

from agent import PersonalDataAgent
from common import RAG_TOP_K, RRF_CANDIDATE_K, RRF_RANK_CONSTANT
from hybrid import HybridSearchEngine
from llm import create_generator
from models import SearchFilters


def _date(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--room")
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--candidate-k", type=int, default=RRF_CANDIDATE_K)
    parser.add_argument("--rank-constant", type=int, default=RRF_RANK_CONSTANT)
    parser.add_argument("--top-k", type=int, default=RAG_TOP_K)
    parser.add_argument("--exact-vector", action="store_true")
    parser.add_argument("--retrieve-only", action="store_true")
    parser.add_argument("--show-context", action="store_true")
    args = parser.parse_args()

    filters = SearchFilters(
        room=args.room,
        date_from=_date(args.from_date),
        date_to=_date(args.to_date),
    )
    if filters.date_from and filters.date_to and filters.date_from >= filters.date_to:
        parser.error("--from-date는 --to-date보다 앞서야 합니다.")
    generator = None if args.retrieve_only else create_generator()
    if generator is None and not args.retrieve_only:
        parser.error("답변 생성에는 .env의 LLM_PROVIDER/LLM_MODEL이 필요합니다. 검색만 보려면 --retrieve-only")

    with HybridSearchEngine() as engine:
        counts = engine.preflight()
        result = PersonalDataAgent(engine, generator).ask(
            args.question,
            filters=filters,
            candidate_k=args.candidate_k,
            rank_constant=args.rank_constant,
            top_k=args.top_k,
            exact_vector=args.exact_vector,
        )

    print(f"corpus: {counts}")
    print(f"query: {result.run.masked_query}")
    print("\n[RRF trace]")
    for index, item in enumerate(result.context_items, start=1):
        print(
            f"{index}. [{item.citation_id}] chunk={item.chunk.chunk_id} "
            f"room={item.chunk.room} time={item.chunk.start_at:%Y-%m-%d %H:%M} "
            f"ranks={item.hit.ranks} rrf={item.hit.score:.6f}"
        )
    if args.show_context:
        print("\n[context — private]\n" + result.rendered_context)
    if result.answer is not None:
        print("\n[answer]\n" + result.answer)
        print(
            f"\n[citation check] cited={list(result.citation_check.cited)} "
            f"coverage={result.citation_check.coverage:.2f}"
        )


if __name__ == "__main__":
    main()
