#!/usr/bin/env python3
"""정규화 문서 JSONL을 검색용 텍스트 청크로 변환한다 (모델 호출 없음)."""
import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path


def block_text(block):
    kind = block.get("type")
    if kind in {"paragraph", "blockquote", "code"}:
        return block.get("text") or ""
    if kind == "list":
        return "\n".join(block.get("items", []))
    if kind == "table":
        return "\n".join(" | ".join(str(cell) for cell in row)
                         for row in block.get("rows", []))
    if kind in {"images", "separator"}:
        return ""
    raise ValueError(f"지원하지 않는 블록 유형: {kind}")


def split_text(text, target, maximum):
    """가능하면 문단/줄 경계에서 자르고 원문 내 문자 위치를 남긴다."""
    start = 0
    while start < len(text):
        end = len(text)
        if end - start > maximum:
            end = text.rfind("\n", start + target, start + maximum + 1)
            if end == -1:
                end = start + target
        left, right = start, end
        while left < right and text[left].isspace():
            left += 1
        while right > left and text[right - 1].isspace():
            right -= 1
        if left < right:
            yield text[left:right], left, right
        start = end


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-chars", type=int, default=1400)
    parser.add_argument("--max-chars", type=int, default=2000)
    args = parser.parse_args()
    if not 0 < args.target_chars <= args.max_chars:
        parser.error("0 < target-chars <= max-chars 이어야 합니다.")
    if args.output.exists():
        parser.error(f"출력 파일이 이미 있습니다. 덮어쓰지 않습니다: {args.output}")

    chunks, document_ids, populated = [], set(), set()
    with args.input.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            doc = json.loads(line)
            doc_id = doc["document_id"]
            if doc_id in document_ids:
                raise ValueError(f"중복 document_id (입력 {line_number}행)")
            document_ids.add(doc_id)
            for section_index, section in enumerate(doc.get("sections", [])):
                parts, spans, position = [], [], 0
                for block_index, block in enumerate(section.get("blocks", [])):
                    text = block_text(block)
                    if not text.strip():
                        continue
                    if parts:
                        position += 2
                    spans.append((position, position + len(text), block_index))
                    parts.append(text)
                    position += len(text)
                section_text = "\n\n".join(parts)
                for chunk_index, (raw, start, end) in enumerate(
                        split_text(section_text, args.target_chars, args.max_chars)):
                    identity = f"{doc_id}:{section_index}:{chunk_index}:{raw}"
                    context = [" / ".join(doc.get("document_path") or []),
                               " / ".join(section.get("section_path") or [])]
                    chunks.append({
                        "chunk_id": hashlib.sha256(identity.encode()).hexdigest(),
                        "document_id": doc_id,
                        "title": doc.get("title"),
                        "parent_document_id": doc.get("parent_document_id"),
                        "document_path": doc.get("document_path"),
                        "url_id": doc.get("url_id"),
                        "section_path": section.get("section_path"),
                        "section_heading": section.get("heading"),
                        "raw_text": raw,
                        "embedding_text": "\n\n".join(x for x in context + [raw] if x),
                        "source": {
                            "input_line": line_number,
                            "section_index": section_index,
                            "block_indices": [i for a, b, i in spans if a < end and b > start],
                            "section_char_start": start,
                            "section_char_end": end,
                        },
                    })
                    populated.add(doc_id)

    if len({c["chunk_id"] for c in chunks}) != len(chunks):
        raise ValueError("중복 chunk_id")
    if any(not c["raw_text"].strip() or len(c["raw_text"]) > args.max_chars for c in chunks):
        raise ValueError("빈 본문 또는 최대 길이 초과")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        for chunk in chunks:
            output.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    lengths = [len(c["raw_text"]) for c in chunks]
    print(f"입력 문서 수: {len(document_ids)}")
    print(f"텍스트 청크가 생성된 문서 수: {len(populated)}")
    print(f"텍스트 청크가 없는 문서 수: {len(document_ids - populated)}")
    print(f"생성된 청크 수: {len(chunks)}")
    print(f"본문 길이 중앙값: {statistics.median(lengths) if lengths else 0}자")
    print(f"본문 최대 길이: {max(lengths, default=0)}자")
    print("검증: 빈 본문·중복 chunk_id·최대 길이 검사 통과")
    print(f"저장 완료: {args.output.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        sys.exit(1)
