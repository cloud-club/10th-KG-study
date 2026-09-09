"""카카오톡 텍스트 메시지를 대화 청크로 묶는 순수 함수. DB 와 모델을 모릅니다.

메시지 하나는 중앙값 6자라 그대로 임베딩하면 검색이 안 됩니다. 연속된 메시지를
"한 대화" 로 묶습니다. 경계는 세 가지 중 하나라도 걸리면 생깁니다.

  1. 앞 메시지와의 시간 간격 > gap_minutes   (대화가 끊겼다가 다시 시작)
  2. 글자 수가 max_chars 를 넘음               (임베딩 모델 입력 길이 안에 들어오게)
  3. 메시지 수가 max_messages 를 넘음

청크 본문은 "이름: 내용" 줄을 \n 으로 이은 것입니다. min_chars 미만인 청크는 버립니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Iterator, NamedTuple


class MessageRow(NamedTuple):
    """kakao.messages 에서 필요한 컬럼만. seq 오름차순으로 넘겨야 합니다."""

    seq: int
    sent_at: datetime
    sender: str
    content: str


@dataclass(frozen=True)
class Chunk:
    chunk_idx: int  # 방 안에서 0부터
    start_seq: int
    end_seq: int
    started_at: datetime
    ended_at: datetime
    message_count: int
    text: str


@dataclass(frozen=True)
class ChunkParams:
    gap_minutes: float = 30
    max_chars: int = 800
    max_messages: int = 60
    min_chars: int = 10


def format_line(row: MessageRow) -> str:
    return f"{row.sender}: {row.content}"


def _finish(idx: int, rows: list[MessageRow], lines: list[str]) -> Chunk:
    return Chunk(
        chunk_idx=idx,
        start_seq=rows[0].seq,
        end_seq=rows[-1].seq,
        started_at=rows[0].sent_at,
        ended_at=rows[-1].sent_at,
        message_count=len(rows),
        text="\n".join(lines),
    )


def _is_boundary(rows: list[MessageRow], chars: int, next_row: MessageRow, next_line: str, p: ChunkParams) -> bool:
    if not rows:
        return False
    gap = (next_row.sent_at - rows[-1].sent_at).total_seconds() / 60
    if gap > p.gap_minutes:
        return True
    if chars + len(next_line) + 1 > p.max_chars:
        return True
    return len(rows) >= p.max_messages


def iter_chunks(rows: Iterable[MessageRow], params: ChunkParams = ChunkParams()) -> Iterator[Chunk]:
    """min_chars 미만 청크는 건너뛰지만 chunk_idx 는 살아남은 것만 셉니다."""
    idx = 0
    cur_rows: list[MessageRow] = []
    cur_lines: list[str] = []
    chars = 0

    def flush() -> Iterator[Chunk]:
        nonlocal idx, cur_rows, cur_lines, chars
        if cur_rows and sum(len(r.content) for r in cur_rows) >= params.min_chars:
            yield _finish(idx, cur_rows, cur_lines)
            idx += 1
        cur_rows, cur_lines, chars = [], [], 0

    for row in rows:
        line = format_line(row)
        if _is_boundary(cur_rows, chars, row, line, params):
            yield from flush()
        cur_rows.append(row)
        cur_lines.append(line)
        chars += len(line) + 1
    yield from flush()


def chunk_messages(rows: Iterable[MessageRow], params: ChunkParams = ChunkParams()) -> tuple[Chunk, ...]:
    return tuple(iter_chunks(rows, params))
