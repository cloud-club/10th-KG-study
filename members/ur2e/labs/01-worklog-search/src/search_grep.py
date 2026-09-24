"""grep(0세대): chunks.jsonl 본문에서 정확한 부분 문자열만 찾는다.

형태소 분석도, 순위도 없다. `content`에 검색어가 그대로 들어있는 청크만
파일에 나온 순서대로 돌려준다. 자연어 질문을 그대로 넣으면 대부분 안 걸린다
— 이게 이 방식의 한계를 보여주는 것 자체가 목적이다.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from pathlib import Path

from parse_vault import chunks_path_for


def load_chunks(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or chunks_path_for("heading")
    if not path.exists():
        raise FileNotFoundError(f"청크 파일이 없습니다: {path}\n먼저 python3 parse_vault.py 를 실행하세요.")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def search_grep(
    query: str,
    limit: int | None = None,
    chunks: list[dict[str, Any]] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[dict[str, Any]], float]:
    chunks = chunks if chunks is not None else load_chunks()
    needle = query.lower()
    started = time.perf_counter()
    pool = chunks
    if date_from or date_to:
        # date가 없는 청크는 날짜 필터를 걸면 대상에서 빠진다(언제인지 모르는데
        # 시간 조건을 만족한다고 볼 수 없으므로).
        pool = [
            c
            for c in pool
            if c.get("date") and (not date_from or c["date"] >= date_from) and (not date_to or c["date"] <= date_to)
        ]
    matched = [chunk for chunk in pool if needle in chunk["content"].lower() or needle in chunk["title"].lower()]
    elapsed = (time.perf_counter() - started) * 1000
    return (matched[:limit] if limit else matched), elapsed


def one_line(text: str, width: int = 140) -> str:
    flat = " ".join(text.split())
    return flat[:width] + ("…" if len(flat) > width else "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--date-from", default=None, help="YYYY-MM-DD, 이 날짜 이후 문서만")
    parser.add_argument("--date-to", default=None, help="YYYY-MM-DD, 이 날짜 이전 문서만")
    args = parser.parse_args()

    rows, elapsed = search_grep(args.query, args.limit, date_from=args.date_from, date_to=args.date_to)
    print(f'[grep] "{args.query}" · {len(rows)}건 · {elapsed:.2f}ms · 순위 없음(문서 순서)')
    for rank, chunk in enumerate(rows, 1):
        heading = f"#{chunk['heading']}" if chunk["heading"] else ""
        print(f"{rank}. {chunk['source_path']}{heading}")
        print(f"   {one_line(chunk['content'])}")


if __name__ == "__main__":
    main()
