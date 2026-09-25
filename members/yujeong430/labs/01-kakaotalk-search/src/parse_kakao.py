"""KakaoTalk TXT 내보내기를 메시지 단위 텍스트 청크 JSONL로 변환한다."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DATE_PATTERN = re.compile(r"^-+\s+(?P<date>\d{4}년\s+\d{1,2}월\s+\d{1,2}일).*?-+$")
MESSAGE_PATTERN = re.compile(r"^\[[^\]]+\]\s+\[[^\]]+\]\s+(?P<content>.+)$")
SYSTEM_MESSAGE_PATTERN = re.compile(r"^.+님이 (?:들어왔습니다|나갔습니다)\.?$")


def split_text(text: str, max_chars: int) -> list[str]:
    """긴 메시지는 줄바꿈이나 공백을 우선으로 max_chars 이하로 나눈다."""
    pieces, remaining = [], text.strip()
    while len(remaining) > max_chars:
        split_at = max(remaining.rfind("\n", 0, max_chars + 1), remaining.rfind(" ", 0, max_chars + 1))
        if split_at <= 0:
            split_at = max_chars
        pieces.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        pieces.append(remaining)
    return pieces


def flush(chunks: list[dict], date: str | None, message_lines: list[str], index: int, max_chars: int) -> int:
    if not date or not message_lines:
        return index
    for text in split_text("\n".join(message_lines), max_chars):
        chunks.append({"id": f"kakao-{index:05d}", "date": date, "source": "kakaotalk_group_export", "message_count": 1, "content": text, "char_count": len(text)})
        index += 1
    return index


def parse(path: Path, max_chars: int) -> list[dict]:
    chunks, current_date, message_lines, index = [], None, [], 1
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        date_match = DATE_PATTERN.match(line)
        if date_match:
            index = flush(chunks, current_date, message_lines, index, max_chars)
            current_date, message_lines = date_match.group("date"), []
            continue
        message_match = MESSAGE_PATTERN.match(line)
        if message_match and current_date:
            index = flush(chunks, current_date, message_lines, index, max_chars)
            message_lines = [message_match.group("content").strip()]
            continue
        if not current_date or not message_lines or not line or SYSTEM_MESSAGE_PATTERN.match(line):
            continue
        message_lines.append(line)
    flush(chunks, current_date, message_lines, index, max_chars)
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
