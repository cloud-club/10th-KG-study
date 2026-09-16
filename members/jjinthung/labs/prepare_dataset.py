#!/usr/bin/env python3
"""카카오톡 내보내기 TXT를 RAG용 대화 청크 JSONL로 변환합니다."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

MESSAGE_RE = re.compile(
    r"^(?P<date>\d{4}\. ?\d{1,2}\. ?\d{1,2}\.?) "
    r"(?P<time>(?:오전|오후) \d{1,2}:\d{2}), "
    r"(?P<sender>[^:]+) : (?P<message>.*)$"
)


@dataclass
class Message:
    timestamp: str
    sender: str
    text: str


def parse_timestamp(date: str, time: str) -> datetime:
    normalized_date = re.sub(r"\.$", "", date).replace(". ", "-").replace(".", "-").replace(" ", "")
    meridiem, parsed_time = time.split(" ", 1)
    hour, minute = map(int, parsed_time.split(":"))
    if meridiem == "오후" and hour != 12:
        hour += 12
    if meridiem == "오전" and hour == 12:
        hour = 0
    return datetime.strptime(
        f"{normalized_date} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M"
    )


def parse_kakao_file(path: Path) -> list[Message]:
    messages: list[Message] = []
    current: Message | None = None
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        match = MESSAGE_RE.match(raw_line)
        if match:
            if current is not None and current.text.strip():
                messages.append(current)
            current = Message(
                timestamp=parse_timestamp(match["date"], match["time"]).isoformat(),
                sender=match["sender"].strip(),
                text=match["message"].strip(),
            )
        elif current is not None:
            continuation = raw_line.strip()
            if continuation:
                current.text = f"{current.text}\n{continuation}".strip()
    if current is not None and current.text.strip():
        messages.append(current)
    return messages


def make_chunks(
    messages: list[Message],
    max_messages: int = 30,
    overlap: int = 5,
    gap_hours: int = 4,
) -> list[dict]:
    if max_messages <= 0 or overlap < 0 or overlap >= max_messages or gap_hours <= 0:
        raise ValueError("max_messages, overlap, gap_hours 값이 올바르지 않습니다.")

    chunks: list[dict] = []
    start = 0
    chunk_id = 0
    gap = timedelta(hours=gap_hours)
    while start < len(messages):
        end = start + 1
        split_by_gap = False
        while end < len(messages) and end - start < max_messages:
            previous = datetime.fromisoformat(messages[end - 1].timestamp)
            current = datetime.fromisoformat(messages[end].timestamp)
            if current - previous > gap:
                split_by_gap = True
                break
            end += 1
        selected = messages[start:end]
        chunks.append(
            {
                "id": f"chunk-{chunk_id:05d}",
                "start": selected[0].timestamp,
                "end": selected[-1].timestamp,
                "message_count": len(selected),
                "messages": [
                    {
                        "date": item.timestamp,
                        "user": item.sender,
                        "content": item.text,
                    }
                    for item in selected
                ],
                "text": "\n".join(
                    f"[{item.timestamp}] {item.sender}: {item.text}" for item in selected
                ),
            }
        )
        chunk_id += 1
        if end == len(messages):
            break
        start = end if split_by_gap else max(start + 1, end - overlap)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="카카오톡 원본을 RAG 청크로 변환")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "Data",
        help="Talk_*.txt 원본 폴더",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "Data" / "documents.jsonl",
    )
    parser.add_argument("--max-messages", type=int, default=12)
    parser.add_argument("--overlap", type=int, default=3)
    parser.add_argument("--gap-hours", type=int, default=2)
    args = parser.parse_args()

    source_paths = sorted(args.input_dir.glob("Talk_*.txt"))
    if not source_paths:
        raise FileNotFoundError(f"원본 파일을 찾지 못했습니다: {args.input_dir}\\Talk_*.txt")
    messages = [message for path in source_paths for message in parse_kakao_file(path)]
    messages.sort(key=lambda item: item.timestamp)
    chunks = make_chunks(messages, args.max_messages, args.overlap, args.gap_hours)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    print(f"메시지 {len(messages):,}개 -> 청크 {len(chunks):,}개: {args.output}")


if __name__ == "__main__":
    main()
