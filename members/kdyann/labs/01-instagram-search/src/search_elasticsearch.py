"""Elasticsearch BM25로 Instagram 캡션을 검색한다."""

from __future__ import annotations

import argparse

from common import one_line, result_label
from search_all import search_bm25


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--ngram", action="store_true")
    args = parser.parse_args()
    field = "text.ngram" if args.ngram else "text"
    rows, elapsed = search_bm25(args.query, args.limit, field)
    analyzer = "n-gram" if args.ngram else "Nori"

    print(f'[Elasticsearch BM25/{analyzer}] "{args.query}" · {len(rows)}건 · {elapsed:.1f}ms')
    for rank, (document, score) in enumerate(rows, 1):
        print(f"{rank}. {result_label(document)} · 점수 {score:.4f}")
        print(f"   {one_line(document['text'])[:140]}")
        print(f"   {document.get('permalink', '')}")


if __name__ == "__main__":
    main()
