"""KakaoTalk TXT 내보내기를 날짜별 텍스트 청크 JSONL로 변환한다."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DATE_PATTERN = re.compile(r"^-+\s+(?P<date>\d{4}년\s+\d{1,2}월\s+\d{1,2}일).*?-+$")
MESSAGE_PATTERN = re.compile(r"^\[[^\]]+\]\s+\[[^\]]+\]\s+(?P<content>.+)$")


def flush(chunks: list[dict], date: str | None, messages: list[str], index: int) -> int:
    if not date or not messages:
        return index
    text = "\n".join(messages)
    chunks.append({"id": f"kakao-{index:05d}", "date": date, "source": "kakaotalk_group_export", "message_count": len(messages), "content": text, "char_count": len(text)})
    return index + 1


def parse(path: Path, max_chars: int) -> list[dict]:
    chunks, current_date, messages, index = [], None, [], 1
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        date_match = DATE_PATTERN.match(line)
        if date_match:
            index = flush(chunks, current_date, messages, index)
            current_date, messages = date_match.group("date"), []
            continue
        message_match = MESSAGE_PATTERN.match(line)
        if not message_match or not current_date:
            continue
        content = message_match.group("content").strip()
        if not content or content.startswith(("사진", "동영상")):
            continue
        if messages and len("\n".join(messages)) + len(content) + 1 > max_chars:
            index, messages = flush(chunks, current_date, messages, index), []
        messages.append(content)
    flush(chunks, current_date, messages, index)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-chars", type=int, default=1000)
    args = parser.parse_args()
    chunks = parse(args.input, args.max_chars)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks), encoding="utf-8")
    print(f"청크 수: {len(chunks)}")
    print(f"출력: {args.output}")


if __name__ == "__main__":
    main()
