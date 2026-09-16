#!/usr/bin/env python3
"""JSONL 청크의 text 필드에서 고정 문자열을 찾는다."""

import argparse
from pathlib import Path

import common_path  # noqa: F401
from search_common.jsonl import read_jsonl


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_INPUT = ROOT / "data" / "do-dop" / "company-analysis-kg" / "processed" / "chunks.jsonl"


def search(chunks: list[dict], query: str, ignore_case: bool = True) -> list[dict]:
    needle = query.casefold() if ignore_case else query
    results = []
    for chunk in chunks:
        text = chunk["text"]
        haystack = text.casefold() if ignore_case else text
        if needle in haystack:
            results.append(chunk)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="기업분석 JSONL 청크를 고정 문자열로 검색합니다.")
    parser.add_argument("query")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--case-sensitive", action="store_true")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    results = search(read_jsonl(args.input), args.query, not args.case_sensitive)
    print(f"일치 청크: {len(results)}")
    for result in results:
        line = f"- {result['id']} ({result['title']})"
        if args.show:
            line += f" {result['text'][:120].replace(chr(10), ' ')!r}"
        print(line)


if __name__ == "__main__":
    main()

