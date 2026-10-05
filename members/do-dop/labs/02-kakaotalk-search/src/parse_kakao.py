#!/usr/bin/env python3
"""카카오톡 대화 내보내기 TXT를 익명화된 JSONL로 변환한다."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


# 작성자가 보낸 일반 메시지 한 줄을 찾는다.
MESSAGE_PATTERN = re.compile(
    r"^\ufeff?"
    r"(?P<year>\d{4})\.\s*"
    r"(?P<month>\d{1,2})\.\s*"
    r"(?P<day>\d{1,2})\.\s*"
    r"(?:(?P<ampm>오전|오후)\s*)?"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2}))?,\s*"
    r"(?P<sender>.+?)\s+:\s*"
    r"(?P<text>.*)$"
)

# 메시지가 아닌 입장·퇴장 등의 시스템 이벤트를 찾는다.
TIMESTAMP_PATTERN = re.compile(
    r"^\ufeff?\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*"
    r"(?:(?:오전|오후)\s*)?\d{1,2}:\d{2}(?::\d{2})?(?:,|:)"
)

# 카카오톡 내보내기 파일의 날짜 구분선을 찾는다.
DATE_SEPARATOR_PATTERN = re.compile(
    r"^-*\s*\d{4}년\s+\d{1,2}월\s+\d{1,2}일(?:\s+\S요일)?\s*-*$"
)


@dataclass
class Message:
    """JSONL에 저장할 메시지 한 건."""

    chunk_id: str
    sender_id: str
    sent_at: str
    text: str
    source_line_start: int
    source_line_end: int


@dataclass
class ParseStats:
    """파싱 결과를 확인하기 위한 집계값."""

    input_lines: int = 0
    messages: int = 0
    senders: int = 0
    multiline_messages: int = 0
    continuation_lines: int = 0
    skipped_headers: int = 0
    skipped_date_separators: int = 0
    skipped_system_events: int = 0
    empty_messages: int = 0


def parse_timestamp(match: re.Match[str]) -> datetime:
    """정규식에서 꺼낸 오전·오후 또는 24시간제 시각을 datetime으로 바꾼다."""

    hour = int(match.group("hour"))
    ampm = match.group("ampm")
    if ampm:
        if not 1 <= hour <= 12:
            raise ValueError(f"12시간제 시각 범위를 벗어났습니다: {hour}")
        if ampm == "오전":
            hour = 0 if hour == 12 else hour
        elif hour != 12:
            hour += 12
    elif not 0 <= hour <= 23:
        raise ValueError(f"24시간제 시각 범위를 벗어났습니다: {hour}")

    return datetime(
        year=int(match.group("year")),
        month=int(match.group("month")),
        day=int(match.group("day")),
        hour=hour,
        minute=int(match.group("minute")),
        second=int(match.group("second") or 0),
    )


def anonymized_sender(sender: str, sender_ids: dict[str, str]) -> str:
    """작성자명을 등장 순서에 따른 익명 ID로 바꾼다."""

    normalized = sender.strip()
    if normalized not in sender_ids:
        sender_ids[normalized] = f"user-{len(sender_ids) + 1:03d}"
    return sender_ids[normalized]


def parse_lines(lines: list[str]) -> tuple[list[Message], ParseStats]:
    """원본 줄을 메시지 목록으로 변환하고 파싱 통계를 만든다."""

    messages: list[Message] = []
    sender_ids: dict[str, str] = {}
    stats = ParseStats(input_lines=len(lines))
    current: dict[str, object] | None = None

    def flush_current(end_line: int) -> None:
        """현재까지 모은 여러 줄을 하나의 메시지로 확정한다."""

        nonlocal current
        if current is None:
            return

        parts = current.pop("text_parts")
        assert isinstance(parts, list)
        text = "\n".join(str(part) for part in parts).strip()
        if not text:
            stats.empty_messages += 1

        messages.append(
            Message(
                chunk_id=f"msg-{len(messages) + 1:06d}",
                sender_id=str(current["sender_id"]),
                sent_at=str(current["sent_at"]),
                text=text,
                source_line_start=int(current["source_line_start"]),
                source_line_end=end_line,
            )
        )
        current = None

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n")
        message_match = MESSAGE_PATTERN.match(line)

        # 새 메시지가 시작되면 이전 메시지를 먼저 저장한다.
        if message_match:
            flush_current(line_number - 1)
            timestamp = parse_timestamp(message_match)
            current = {
                "sender_id": anonymized_sender(
                    message_match.group("sender"), sender_ids
                ),
                "sent_at": timestamp.isoformat(),
                "text_parts": [message_match.group("text")],
                "source_line_start": line_number,
            }
            continue

        # 날짜 구분선은 메시지 내용에 포함하지 않는다.
        if DATE_SEPARATOR_PATTERN.match(line):
            flush_current(line_number - 1)
            stats.skipped_date_separators += 1
            continue

        # 작성자와 본문이 없는 시스템 이벤트도 제외한다.
        if TIMESTAMP_PATTERN.match(line):
            flush_current(line_number - 1)
            stats.skipped_system_events += 1
            continue

        # 첫 메시지보다 앞에 있는 헤더와 빈 줄은 건너뛴다.
        if current is None:
            stats.skipped_headers += 1
            continue

        # 나머지 줄은 직전 메시지의 이어지는 본문으로 처리한다.
        parts = current["text_parts"]
        assert isinstance(parts, list)
        parts.append(line)
        stats.continuation_lines += 1

    flush_current(len(lines))

    stats.messages = len(messages)
    stats.senders = len(sender_ids)
    stats.multiline_messages = sum("\n" in message.text for message in messages)
    return messages, stats


def write_jsonl(messages: list[Message], output_path: Path) -> None:
    """메시지를 임시 파일에 쓴 뒤 완성된 JSONL로 교체한다."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.is_symlink():
        raise ValueError(f"심볼릭 링크에는 출력하지 않습니다: {output_path}")

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        try:
            for message in messages:
                json.dump(asdict(message), temp_file, ensure_ascii=False)
                temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    os.replace(temp_path, output_path)


def build_parser() -> argparse.ArgumentParser:
    """명령행에서 입력 파일과 출력 파일을 받는다."""

    parser = argparse.ArgumentParser(
        description="카카오톡 TXT를 작성자명이 제거된 JSONL로 변환합니다."
    )
    parser.add_argument("--input", required=True, type=Path, help="카카오톡 TXT 경로")
    parser.add_argument("--output", required=True, type=Path, help="JSONL 출력 경로")
    return parser


def main() -> int:
    """카카오톡 파일을 읽고 파싱한 뒤 JSONL로 저장한다."""

    args = build_parser().parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()

    if input_path == output_path:
        raise ValueError("입력 파일과 출력 파일은 달라야 합니다.")
    if not input_path.is_file():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")

    with input_path.open("r", encoding="utf-8-sig", newline=None) as input_file:
        lines = input_file.readlines()

    messages, stats = parse_lines(lines)
    if not messages:
        raise ValueError("메시지를 찾지 못했습니다. 카카오톡 내보내기 형식을 확인하세요.")

    write_jsonl(messages, output_path)

    print(f"읽은 줄: {stats.input_lines}")
    print(f"변환한 메시지: {stats.messages}")
    print(f"익명 작성자: {stats.senders}")
    print(f"여러 줄 메시지: {stats.multiline_messages}")
    print(f"이어 붙인 줄: {stats.continuation_lines}")
    print(f"건너뛴 날짜 구분선: {stats.skipped_date_separators}")
    print(f"건너뛴 시스템 이벤트: {stats.skipped_system_events}")
    print(f"건너뛴 헤더/빈 줄: {stats.skipped_headers}")
    print(f"빈 메시지: {stats.empty_messages}")
    print(f"출력 파일: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
