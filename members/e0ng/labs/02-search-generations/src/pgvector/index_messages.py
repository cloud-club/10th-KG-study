#!/usr/bin/env python3
import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import embed, get_env, load_messages


def chunk_messages(messages: list[dict], window_minutes: int) -> list[dict]:
    chunks: list[dict] = []
    window = timedelta(minutes=window_minutes)

    for item in messages:
        timestamp = datetime.fromisoformat(item["timestamp"])
        previous = chunks[-1] if chunks else None
        can_merge = (
            previous
            and previous["sender"] == item["sender"]
            and timestamp - previous["end_timestamp"] <= window
        )
        if can_merge:
            previous["message"] += "\n" + item["message"]
            previous["end_timestamp"] = timestamp
            previous["source_message_count"] += 1
        else:
            chunks.append(
                {
                    "sender": item["sender"],
                    "message": item["message"],
                    "timestamp": timestamp,
                    "end_timestamp": timestamp,
                    "source_message_count": 1,
                }
            )
    return chunks


def format_duration(seconds: float) -> str:
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(description="채팅을 청킹하고 pgvector에 저장합니다.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--window-minutes", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    messages = load_messages(args.input) if args.input else load_messages()
    chunks = chunk_messages(messages, args.window_minutes)
    print(
        f"원본 {len(messages):,}개 → 청크 {len(chunks):,}개, "
        f"배치 크기 {args.batch_size}로 임베딩을 시작합니다.",
        flush=True,
    )

    dsn = get_env("POSTGRES_DSN", "postgresql://study:study@localhost:5432/chat_search")
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute("TRUNCATE chat_chunks RESTART IDENTITY")
        connection.commit()
        started_at = time.monotonic()

        for start in range(0, len(chunks), args.batch_size):
            batch = chunks[start : start + args.batch_size]
            vectors = embed([chunk["message"] for chunk in batch])
            cursor.executemany(
                """
                INSERT INTO chat_chunks
                    (sender, message, timestamp, end_timestamp, source_message_count, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                """,
                [
                    (
                        chunk["sender"],
                        chunk["message"],
                        chunk["timestamp"],
                        chunk["end_timestamp"],
                        chunk["source_message_count"],
                        str(vector),
                    )
                    for chunk, vector in zip(batch, vectors)
                ],
            )
            connection.commit()

            completed = start + len(batch)
            elapsed = time.monotonic() - started_at
            eta = elapsed / completed * (len(chunks) - completed)
            print(
                f"[{completed:,}/{len(chunks):,}] {completed / len(chunks):.1%} "
                f"경과 {format_duration(elapsed)} / 예상 남은 시간 {format_duration(eta)}",
                flush=True,
            )

    print(f"pgvector 저장 완료: 원본 {len(messages):,}개 → 청크 {len(chunks):,}개")


if __name__ == "__main__":
    main()
