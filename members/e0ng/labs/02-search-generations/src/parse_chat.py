#!/usr/bin/env python3
import argparse
import csv
import io
import json
from datetime import datetime
from pathlib import Path

from common import JSON_PATH, PROCESSED_DIR, TSV_PATH


CSV_COLUMNS = ("date", "user", "message")


def normalize_timestamp(raw: str) -> str:
    raw = " ".join(raw.split())
    return datetime.fromisoformat(raw.replace(" ", "T", 1)).isoformat()


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text, newline=""))
    field_map = {field.strip().lower(): field for field in (reader.fieldnames or [])}
    missing = [column for column in CSV_COLUMNS if column not in field_map]
    if missing:
        raise ValueError(f"CSV 필수 열이 없습니다: {', '.join(missing)}")

    messages: list[dict] = []
    for row_number, row in enumerate(reader, start=2):
        timestamp = (row.get(field_map["date"]) or "").strip()
        sender = (row.get(field_map["user"]) or "").strip()
        message = row.get(field_map["message"]) or ""
        if not timestamp and not sender and not message:
            continue
        if not timestamp and not sender and message:
            if not messages:
                raise ValueError(f"CSV {row_number}행을 이어 붙일 이전 메시지가 없습니다.")
            messages[-1]["message"] += "\n" + message
            continue
        if not timestamp or not sender:
            raise ValueError(f"CSV {row_number}행의 Date 또는 User 값이 비어 있습니다.")
        messages.append(
            {
                "timestamp": normalize_timestamp(timestamp),
                "sender": sender,
                "message": message,
            }
        )

    if not messages:
        raise ValueError("CSV에서 메시지를 찾지 못했습니다.")
    return messages


def write_outputs(messages: list[dict], json_path: Path, tsv_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(messages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with tsv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, delimiter="\t", lineterminator="\n")
        writer.writerow(["timestamp", "sender", "message"])
        for item in messages:
            writer.writerow(
                [item["timestamp"], item["sender"], item["message"].replace("\n", "\\n")]
            )


def previous_month(messages: list[dict]) -> tuple[list[dict], datetime, datetime]:
    latest = max(datetime.fromisoformat(item["timestamp"]) for item in messages)
    end = latest.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if end.month == 1:
        start = end.replace(year=end.year - 1, month=12)
    else:
        start = end.replace(month=end.month - 1)
    filtered = [
        item for item in messages if start <= datetime.fromisoformat(item["timestamp"]) < end
    ]
    return filtered, start, end


def main() -> None:
    parser = argparse.ArgumentParser(description="채팅 CSV를 JSON과 grep용 TSV로 변환합니다.")
    parser.add_argument("input", type=Path, help="Date/User/Message 열이 있는 CSV 파일")
    parser.add_argument("--last-month", action="store_true", help="데이터의 마지막 날짜 기준 직전 달만 추출")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--tsv", type=Path)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8-sig")
    messages = parse_csv(text)
    if args.last_month:
        messages, start, end = previous_month(messages)
        print(f"지난달 범위: {start.date()} 이상, {end.date()} 미만")
    json_path = args.json or (PROCESSED_DIR / "chat-last-month.json" if args.last_month else JSON_PATH)
    tsv_path = args.tsv or (PROCESSED_DIR / "chat-last-month.tsv" if args.last_month else TSV_PATH)
    write_outputs(messages, json_path, tsv_path)
    print(f"{len(messages):,}개 메시지 저장: {json_path}, {tsv_path}")


if __name__ == "__main__":
    main()
