#!/usr/bin/env python3
"""Notion Markdown/CSV export를 검색용 JSONL 청크로 변환한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


NOTION_ID_RE = re.compile(r"\s+([0-9a-f]{32})$")
MARKDOWN_LINK_RE = re.compile(r"!?\[([^]]*)\]\([^)]+\)")


def page_info(path: Path, source: str) -> tuple[str, str]:
    """파일명 끝의 Notion ID를 분리해 페이지 ID와 제목을 반환한다."""
    match = NOTION_ID_RE.search(path.stem)
    if match:
        return match.group(1), path.stem[: match.start()].strip()
    return hashlib.sha256(source.encode()).hexdigest()[:32], path.stem


def clean_markdown(text: str) -> str:
    """검색에 불필요한 Markdown 표식은 줄이고 본문과 코드 내용은 보존한다."""
    cleaned: list[str] = []
    in_code_block = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if line.startswith("!["):
            continue
        if not in_code_block:
            line = re.sub(r"^#{1,6}\s+", "", line)
            line = re.sub(r"^[-*+]\s+", "", line)
            line = re.sub(r"^>\s?", "", line)
            line = MARKDOWN_LINK_RE.sub(r"\1", line)
        cleaned.append(line)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned)).strip()


def split_paragraphs(text: str, chunk_size: int) -> list[str]:
    """Notion의 문단·줄 경계를 우선 유지하면서 최대 문자 수에 맞춰 청킹한다."""
    units = [line.strip() for line in text.splitlines() if line.strip()]
    chunks: list[str] = []
    current = ""

    for unit in units:
        if len(unit) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                unit[start : start + chunk_size]
                for start in range(0, len(unit), chunk_size)
            )
        elif not current:
            current = unit
        elif len(current) + 1 + len(unit) <= chunk_size:
            current = f"{current}\n{unit}"
        else:
            chunks.append(current)
            current = unit

    if current:
        chunks.append(current)
    return chunks


def stable_chunk_id(source: str, chunk_index: int) -> str:
    value = f"{source}:{chunk_index}".encode()
    return hashlib.sha256(value).hexdigest()[:20]


def markdown_documents(path: Path, root: Path, chunk_size: int) -> list[dict]:
    source = path.relative_to(root).as_posix()
    page_id, title = page_info(path, source)
    text = clean_markdown(path.read_text(encoding="utf-8-sig"))
    lines = text.splitlines()
    if lines and lines[0].strip() == title:
        text = "\n".join(lines[1:]).strip()
    return [
        {
            "id": stable_chunk_id(source, index),
            "page_id": page_id,
            "title": title,
            "content": chunk,
            "source": source,
            "chunk_index": index,
        }
        for index, chunk in enumerate(split_paragraphs(text, chunk_size))
        if chunk
    ]


def csv_documents(path: Path, root: Path) -> list[dict]:
    source = path.relative_to(root).as_posix()
    page_id, title = page_info(path, source)
    documents: list[dict] = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for index, row in enumerate(csv.DictReader(stream)):
            fields = [f"{key}: {value.strip()}" for key, value in row.items() if value and value.strip()]
            if not fields:
                continue
            documents.append(
                {
                    "id": stable_chunk_id(source, index),
                    "page_id": page_id,
                    "title": title,
                    "content": "\n".join(fields),
                    "source": source,
                    "chunk_index": index,
                }
            )
    return documents


def parse_export(input_dir: Path, chunk_size: int, include_csv: bool) -> list[dict]:
    documents: list[dict] = []
    for path in sorted(input_dir.rglob("*.md")):
        documents.extend(markdown_documents(path, input_dir, chunk_size))
    if include_csv:
        for path in sorted(input_dir.rglob("*.csv")):
            documents.extend(csv_documents(path, input_dir))
    return documents


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="압축을 푼 Notion export 폴더")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/documents.jsonl"),
    )
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--include-csv", action="store_true")
    args = parser.parse_args()

    if not args.input.is_dir():
        raise SystemExit(f"Notion export 폴더를 찾을 수 없습니다: {args.input}")
    if args.chunk_size <= 0:
        raise SystemExit("--chunk-size는 1 이상이어야 합니다.")

    documents = parse_export(args.input, args.chunk_size, args.include_csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for document in documents:
            stream.write(json.dumps(document, ensure_ascii=False) + "\n")

    print(f"문서 청크 {len(documents)}개 저장: {args.output}")


if __name__ == "__main__":
    main()
