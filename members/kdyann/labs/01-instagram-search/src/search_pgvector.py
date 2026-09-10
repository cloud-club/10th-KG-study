"""pgvector 코사인 유사도로 Instagram 캡션을 검색한다."""

from __future__ import annotations

import argparse

from common import one_line, result_label
from search_all import search_vector


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    rows, elapsed = search_vector(args.query, args.limit)

    print(f'[pgvector/HNSW] "{args.query}" · {len(rows)}건 · {elapsed:.1f}ms')
    for rank, (document, score) in enumerate(rows, 1):
        print(f"{rank}. {result_label(document)} · 유사도 {score:.4f}")
        print(f"   {one_line(document['text'])[:140]}")
        print(f"   {document.get('permalink', '')}")


if __name__ == "__main__":
    main()
