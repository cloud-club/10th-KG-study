"""카카오톡 대화 내보내기(txt, 모바일 형식) 파서. 순수 함수만 있고 DB 를 모릅니다.

지원 형식 (Android / iOS 에서 "대화 내보내기" 한 txt):

    우리동네 카카오톡 대화
    저장한 날짜 : 2024년 8월 2일 오후 4:03

    2023년 8월 9일 오전 12:34                          ← 날짜 구분선 (건너뜀)
    2023년 8월 9일 오전 12:34, 홍길동 : 안녕            ← 메시지
    이어지는 둘째 줄                                    ← 바로 앞 메시지에 붙임
    2023년 8월 9일 오후 3:39, 홍길동님이 나갔습니다.     ← 시스템 이벤트 (sender=None)

시각은 분 단위 KST 이고 초가 없어서, 같은 분 안의 순서는 `seq` 로 보존합니다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

_TIMESTAMP = re.compile(
    r"^(\d{4})년 (\d{1,2})월 (\d{1,2})일 (오전|오후) (\d{1,2}):(\d{2})(?:, (.*))?$"
)
_SENDER_SEP = " : "
_ROOM_SUFFIX = " 카카오톡 대화"
_EXPORTED_PREFIX = "저장한 날짜 : "
_BOM = "\ufeff"

KIND_TEXT = "text"
KIND_SYSTEM = "system"

# 첫 줄 기준으로 판정. 순서대로 먼저 맞는 것이 이깁니다.
_KIND_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("photo", re.compile(r"^(사진( \d+장)?|<사진 읽지 않음>)$")),
    ("video", re.compile(r"^(동영상|<동영상 읽지 않음>)$")),
    ("voice", re.compile(r"^(음성메시지|<음성메시지 읽지 않음>)$")),
    ("emoticon", re.compile(r"^이모티콘$")),
    ("file", re.compile(r"^파일: ")),
    ("deleted", re.compile(r"^삭제된 메시지입니다\.$")),
    ("shop", re.compile(r"^샵검색: ")),
)
_LINK_ONLY = re.compile(r"^https?://\S+$")
# 안드로이드 내보내기는 첨부를 "sha256해시.jpg" 파일명 줄로 남기기도 함 (여러 개면 여러 줄). 확장자로 종류 결정.
_HASH_MEDIA_LINE = re.compile(r"^[0-9a-f]{64}\.([A-Za-z0-9]+)$")
_EXT_KINDS = {
    "photo": {"jpg", "jpeg", "png", "gif", "webp", "heic", "bmp"},
    "video": {"mp4", "mov", "avi", "mkv", "webm"},
    "voice": {"m4a", "mp3", "aac", "wav", "ogg", "amr"},
}

_SYSTEM_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("system_leave", re.compile(r"님이 나갔습니다\.$")),
    ("system_invite", re.compile(r"님이 .+님을 초대했습니다\.$")),
    ("system_join", re.compile(r"님이 들어왔습니다\.$")),
)

KINDS = tuple(k for k, _ in _KIND_RULES) + ("link", KIND_TEXT) + tuple(
    k for k, _ in _SYSTEM_RULES
) + (KIND_SYSTEM,)


@dataclass(frozen=True)
class Message:
    seq: int  # 파일 안에서 몇 번째 메시지인지 (1부터, 구분선 제외)
    line_no: int  # 원본 txt 에서 타임스탬프가 있던 줄 번호 (1부터)
    sent_at: datetime  # KST, 분 단위
    sender: str | None  # 시스템 이벤트면 None
    kind: str
    content: str


@dataclass(frozen=True)
class Chat:
    room_name: str
    exported_at: datetime | None
    messages: tuple[Message, ...]

    @property
    def senders(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for m in self.messages:
            if m.sender is not None:
                seen.setdefault(m.sender, None)
        return tuple(seen)


def to_datetime(year: str, month: str, day: str, ampm: str, hour: str, minute: str) -> datetime:
    """'오전 12:05' → 00:05, '오후 12:05' → 12:05, '오후 3:05' → 15:05."""
    h = int(hour) % 12 + (12 if ampm == "오후" else 0)
    return datetime(int(year), int(month), int(day), h, int(minute))


def parse_timestamp_text(text: str) -> datetime | None:
    """'2024년 8월 2일 오후 4:03' 같은 문자열 하나를 datetime 으로. 형식이 다르면 None."""
    m = _TIMESTAMP.match(text.strip())
    if m is None or m.group(7) is not None:
        return None
    return to_datetime(*m.groups()[:6])


def classify(content: str) -> str:
    """일반 메시지의 종류. 첫 줄로 판정하고, 링크는 본문 전체가 URL 하나일 때만."""
    head = content.split("\n", 1)[0]
    for kind, pattern in _KIND_RULES:
        if pattern.match(head):
            return kind
    if _LINK_ONLY.match(content):
        return "link"
    return _classify_hashed_media(content) or KIND_TEXT


def _classify_hashed_media(content: str) -> str | None:
    """모든 줄이 해시 파일명이면 첫 줄 확장자로 photo/video/voice/file. 아니면 None."""
    matches = [_HASH_MEDIA_LINE.match(line) for line in content.split("\n")]
    if not matches or not all(matches):
        return None
    ext = matches[0].group(1).lower()
    for kind, exts in _EXT_KINDS.items():
        if ext in exts:
            return kind
    return "file"


def classify_system(content: str) -> str:
    for kind, pattern in _SYSTEM_RULES:
        if pattern.search(content):
            return kind
    return KIND_SYSTEM


def _split_sender(rest: str) -> tuple[str | None, str]:
    """'홍길동 : 안녕 : 하세요' → ('홍길동', '안녕 : 하세요'). 구분자가 없으면 시스템 줄."""
    if _SENDER_SEP not in rest:
        return None, rest
    sender, content = rest.split(_SENDER_SEP, 1)
    return sender, content


def _build(seq: int, line_no: int, sent_at: datetime, sender: str | None, lines: list[str]) -> Message:
    content = "\n".join(lines).rstrip()
    kind = classify(content) if sender is not None else classify_system(content)
    return Message(seq=seq, line_no=line_no, sent_at=sent_at, sender=sender, kind=kind, content=content)


def iter_messages(lines: Iterable[str]) -> Iterator[Message]:
    """줄을 순서대로 읽어 Message 를 하나씩 냅니다. 머리말 두 줄은 무시합니다."""
    seq = 0
    pending: tuple[int, datetime, str | None, list[str]] | None = None

    for line_no, raw in enumerate(lines, 1):
        line = raw.rstrip("\r\n")
        if line_no == 1:
            line = line.lstrip(_BOM)
            if line.endswith(_ROOM_SUFFIX):
                continue
        if line_no == 2 and line.startswith(_EXPORTED_PREFIX):
            continue

        m = _TIMESTAMP.match(line)
        if m is None:
            if pending is not None:  # 앞 메시지의 이어지는 줄 (빈 줄 포함)
                pending[3].append(line)
            continue  # 첫 메시지 전의 잡음 줄

        if pending is not None:
            yield _build(seq, *pending)
            pending = None
        rest = m.group(7)
        if rest is None:  # 날짜 구분선
            continue
        seq += 1
        sender, content = _split_sender(rest)
        pending = (line_no, to_datetime(*m.groups()[:6]), sender, [content])

    if pending is not None:
        yield _build(seq, *pending)


def parse_header(first_two_lines: Iterable[str]) -> tuple[str, datetime | None]:
    """(방 이름, 저장한 날짜). 머리말이 없으면 ('', None)."""
    lines = [l.rstrip("\r\n").lstrip(_BOM) for l in first_two_lines]
    room = lines[0][: -len(_ROOM_SUFFIX)] if lines and lines[0].endswith(_ROOM_SUFFIX) else ""
    exported = None
    if len(lines) > 1 and lines[1].startswith(_EXPORTED_PREFIX):
        exported = parse_timestamp_text(lines[1][len(_EXPORTED_PREFIX):])
    return room, exported


def parse_lines(lines: Iterable[str]) -> Chat:
    materialized = list(lines)
    room, exported = parse_header(materialized[:2])
    return Chat(room_name=room, exported_at=exported, messages=tuple(iter_messages(materialized)))


def parse_file(path: str | Path) -> Chat:
    """BOM 과 CRLF 는 open() 이 처리합니다."""
    with open(path, encoding="utf-8-sig", newline=None) as f:
        return parse_lines(f)
