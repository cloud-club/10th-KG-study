#!/usr/bin/env python3
"""뉴스룸과 DART 문서를 검색에 사용할 비슷한 크기의 청크로 나눈다."""

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_INPUT = ROOT / "data" / "do-dop" / "company-analysis-kg" / "processed" / "documents.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "do-dop" / "company-analysis-kg" / "processed" / "chunks.jsonl"


def split_paragraphs(text: str) -> list[str]:
    """줄바꿈을 우선 사용하고, 너무 긴 문단은 문장 경계에서 나눈다."""
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in text.splitlines() if part.strip()]
    result = []
    for paragraph in paragraphs:
        if len(paragraph) <= 800:
            result.append(paragraph)
            continue
        sentences = re.split(r"(?<=[.!?。])\s+", paragraph)
        result.extend(sentence.strip() for sentence in sentences if sentence.strip())
    return result


def chunk_text(text: str, max_chars: int, overlap_paragraphs: int) -> list[str]:
    """문단을 최대 글자 수까지 묶고 이전 문단 일부를 다음 청크에 겹친다."""
    paragraphs = split_paragraphs(text)
    chunks: list[str] = []
    current: list[str] = []

    for paragraph in paragraphs:
        candidate = "\n".join(current + [paragraph])
        if current and len(candidate) > max_chars:
            chunks.append("\n".join(current))
            current = current[-overlap_paragraphs:] if overlap_paragraphs else []
        current.append(paragraph)
    if current:
        chunks.append("\n".join(current))
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-chars", type=int, default=800)
    parser.add_argument("--overlap-paragraphs", type=int, default=1)
    args = parser.parse_args()

    documents = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    chunks = []
    for document in documents:
        for index, text in enumerate(chunk_text(document["text"], args.max_chars, args.overlap_paragraphs)):
            chunk = {key: value for key, value in document.items() if key != "text"}
            chunk.update(
                {
                    "id": f"{document['id']}_chunk_{index + 1:02d}",
                    "document_id": document["id"],
                    "chunk_index": index,
                    "text": text,
                }
            )
            chunks.append(chunk)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    print(f"문서 {len(documents)}건을 청크 {len(chunks)}건으로 저장: {args.output}")


if __name__ == "__main__":
    main()
