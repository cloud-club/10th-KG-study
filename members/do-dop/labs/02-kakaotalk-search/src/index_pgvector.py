#!/usr/bin/env python3
"""익명화된 카카오톡 메시지 JSONL을 청킹·임베딩해 pgvector 테이블에 저장한다."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import psycopg

from chunking import chunk_messages
from embed_ollama import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, embed, to_pgvector_literal

DEFAULT_DSN = "postgresql://kg:kg@localhost:5432/kg"
TABLE_NAME = "do_dop_kakao_chunks"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def read_messages(input_path: Path) -> list[dict]:
    # 파싱된 JSONL을 읽어 메시지 목록으로 만든다.
    messages = []
    with input_path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"{input_path}:{line_number} JSON 파싱 실패") from error
    return messages


def ensure_table(conn: psycopg.Connection, recreate: bool) -> None:
    # --recreate이면 기존 실습 테이블을 지운 뒤 schema.sql을 실행한다.
    if recreate:
        conn.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def insert_chunks(
    conn: psycopg.Connection,
    chunks: list[dict],
    model: str,
    ollama_url: str,
) -> tuple[int, int]:
    # 청크마다 임베딩을 만들고 원문·메타데이터와 함께 PostgreSQL에 저장한다.
    inserted = 0
    errors = 0
    start = time.monotonic()

    with conn.cursor() as cursor:
        for index, chunk in enumerate(chunks, start=1):
            try:
                # 청크 본문 전체를 하나의 벡터로 변환한다.
                embedding = embed(chunk["content"], model=model, ollama_url=ollama_url)
                cursor.execute(
                    f"""
                    INSERT INTO {TABLE_NAME}
                        (chunk_id, sender_id, started_at, ended_at, message_count, content, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id) DO NOTHING
                    """,
                    (
                        chunk["chunk_id"],
                        chunk["sender_id"],
                        chunk["started_at"],
                        chunk["ended_at"],
                        chunk["message_count"],
                        chunk["content"],
                        to_pgvector_literal(embedding),
                    ),
                )
                inserted += 1
            except Exception as error:  # noqa: BLE001 - 배치 중 하나 실패해도 계속 진행
                errors += 1
                print(f"  경고: {chunk['chunk_id']} 임베딩/삽입 실패: {error}", file=sys.stderr)

            if index % 50 == 0 or index == len(chunks):
                elapsed = time.monotonic() - start
                rate = index / elapsed if elapsed > 0 else 0.0
                remaining = (len(chunks) - index) / rate if rate > 0 else 0.0
                print(
                    f"  진행률: {index}/{len(chunks)} "
                    f"({elapsed:.1f}s 경과, 예상 남은 시간 {remaining:.1f}s)"
                )

    conn.commit()
    return inserted, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="카카오톡 메시지 JSONL을 청킹·임베딩해 pgvector에 저장합니다."
    )
    parser.add_argument("--input", required=True, type=Path, help="messages.jsonl 경로")
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=1,
        help="같은 발신자의 메시지를 묶을 최대 간격(분). 0이면 청킹하지 않음 (기본 1)",
    )
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="PostgreSQL 연결 문자열")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama 임베딩 모델")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama base URL")
    parser.add_argument(
        "--recreate", action="store_true", help="기존 테이블을 삭제하고 새로 만든다"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = args.input.resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")

    # 메시지를 읽고 같은 발신자의 짧은 연속 메시지를 청크로 묶는다.
    messages = read_messages(input_path)
    if not messages:
        raise ValueError("색인할 메시지가 없습니다.")

    chunks = chunk_messages(messages, args.window_minutes)
    print(f"메시지: {len(messages)}개 -> 청크: {len(chunks)}개 (window={args.window_minutes}분)")

    # 테이블을 준비한 뒤 청크와 임베딩을 저장한다.
    with psycopg.connect(args.dsn) as conn:
        ensure_table(conn, args.recreate)
        inserted, errors = insert_chunks(conn, chunks, args.model, args.ollama_url)

    print(f"삽입 성공: {inserted}")
    print(f"삽입 실패: {errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
