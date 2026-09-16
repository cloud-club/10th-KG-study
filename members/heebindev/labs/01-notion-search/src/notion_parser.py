"""Notion에서 내보낸 Markdown 문서를 검색용 청크로 변환한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


NOTION_ID_PATTERN = re.compile(r"\s+[0-9a-f]{32}$", re.IGNORECASE)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")


def clean_document_title(path: Path) -> str:
    """파일명 뒤에 붙은 Notion 페이지 ID를 제거한다."""
    return NOTION_ID_PATTERN.sub("", path.stem).strip()


def split_by_heading(text: str) -> list[tuple[str, str]]:
    """Markdown을 제목 단위의 (제목, 본문) 목록으로 나눈다."""
    sections: list[tuple[str, str]] = []
    heading = "본문"
    body: list[str] = []

    for line in text.splitlines():
        match = HEADING_PATTERN.match(line.strip())
        if match:
            content = "\n".join(body).strip()
            if content:
                sections.append((heading, content))
            heading = match.group(2).strip()
            body = []
        else:
            body.append(line)

    content = "\n".join(body).strip()
    if content:
        sections.append((heading, content))

    return sections


def split_long_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """긴 본문을 문단 경계를 우선해 자르고 일부 내용을 겹친다."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    remaining = text

    while len(remaining) > max_chars:
        split_at = remaining.rfind("\n\n", 0, max_chars + 1)
        if split_at < max_chars // 2:
            split_at = remaining.rfind("\n", 0, max_chars + 1)
        if split_at < max_chars // 2:
            split_at = max_chars

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)

        next_start = max(0, split_at - overlap)
        remaining = remaining[next_start:].lstrip()

    if remaining.strip():
        chunks.append(remaining.strip())

    return chunks


def make_chunks(path: Path, raw_root: Path, max_chars: int, overlap: int) -> list[dict]:
    """문서 한 개를 JSON으로 저장할 수 있는 청크 목록으로 변환한다."""
    text = path.read_text(encoding="utf-8")
    source = path.relative_to(raw_root).as_posix()
    document_title = clean_document_title(path)
    results: list[dict] = []

    for section_index, (heading, content) in enumerate(split_by_heading(text)):
        for part_index, chunk_text in enumerate(
            split_long_text(content, max_chars=max_chars, overlap=overlap)
        ):
            chunk_key = f"{source}:{section_index}:{part_index}"
            chunk_id = hashlib.sha256(chunk_key.encode("utf-8")).hexdigest()[:16]
            results.append(
                {
                    "id": chunk_id,
                    "source": source,
                    "document_title": document_title,
                    "heading": heading,
                    "content": chunk_text,
                    "char_count": len(chunk_text),
                }
            )

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Notion Markdown 폴더")
    parser.add_argument("--output", type=Path, required=True, help="출력 JSONL 파일")
    parser.add_argument("--max-chars", type=int, default=1000, help="청크 최대 글자 수")
    parser.add_argument("--overlap", type=int, default=150, help="청크 사이 중복 글자 수")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_chars <= 0:
        raise ValueError("--max-chars는 1 이상이어야 합니다.")
    if args.overlap < 0 or args.overlap >= args.max_chars:
        raise ValueError("--overlap은 0 이상이고 --max-chars보다 작아야 합니다.")

    markdown_files = sorted(args.input.rglob("*.md"))
    if not markdown_files:
        raise FileNotFoundError(f"Markdown 파일을 찾지 못했습니다: {args.input}")

    chunks: list[dict] = []
    for path in markdown_files:
        chunks.extend(make_chunks(path, args.input, args.max_chars, args.overlap))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_file:
        for chunk in chunks:
            output_file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"문서 {len(markdown_files)}개를 청크 {len(chunks)}개로 변환했습니다.")
    print(f"결과: {args.output}")


if __name__ == "__main__":
    main()
