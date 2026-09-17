"""채팅 로그 청킹.

카톡 메시지 1건은 너무 짧아("ㅋㅋ", "ㅇㅇ") 그대로 임베딩하면 의미가 없다.
그래서 검색 단위(청크)는 "대화 조각"으로 만든다.

  1) 세션 분리: 앞 메시지와 SESSION_GAP_MIN 분 이상 떨어지면 새 세션
  2) 세션 안에서 슬라이딩 윈도우: 최대 CHUNK_MAX_MSGS 건 또는 CHUNK_MAX_CHARS 자
  3) 인접 청크는 CHUNK_OVERLAP_MSGS 건씩 겹침 (문맥이 경계에서 끊기는 것 완화)
  4) 사진/이모티콘/삭제/시스템 메시지는 청크 본문에서 제외 (DB의 messages 에는 그대로 남아 있음)

청크 텍스트 예:
  [여행모임] 2024-03-02(토) 19:12~19:40 · 참여: 김하람, 박서아
  김하람: 부산 언제 갈까
  박서아: 4월 첫주 어때
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

KO_WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"]
CHUNKABLE_TYPES = {"text", "link"}


def _fmt_header(room: str, start: datetime, end: datetime, participants: list[str]) -> str:
    day = f"{start:%Y-%m-%d}({KO_WEEKDAY[start.weekday()]})"
    span = f"{start:%H:%M}~{end:%H:%M}" if start.date() == end.date() else f"{start:%H:%M}~{end:%m-%d %H:%M}"
    return f"[{room}] {day} {span} · 참여: {', '.join(participants)}"


def split_sessions(msgs: list[dict], gap_min: int) -> list[list[dict]]:
    sessions: list[list[dict]] = []
    gap = timedelta(minutes=gap_min)
    for m in msgs:
        if sessions and m["sent_at"] - sessions[-1][-1]["sent_at"] <= gap:
            sessions[-1].append(m)
        else:
            sessions.append([m])
    return sessions


def build_chunks(messages: list[dict], room: str, gap_min: int = 30, max_msgs: int = 30,
                 max_chars: int = 700, overlap: int = 3) -> list[dict]:
    """messages: seq 순으로 정렬된 dict 목록. sent_at 은 datetime.

    반환: chunk_index, start_seq, end_seq, start_at, end_at, n_messages, participants, text, content_hash
    """
    usable = [m for m in messages
              if m.get("msg_type") in CHUNKABLE_TYPES and m.get("sender") and m.get("text", "").strip()]
    chunks: list[dict] = []
    for session in split_sessions(usable, gap_min):
        i, n = 0, len(session)
        while i < n:
            j, chars = i, 0
            while j < n and (j - i) < max_msgs:
                line_len = len(session[j]["text"]) + len(session[j]["sender"]) + 2
                if j > i and chars + line_len > max_chars:
                    break
                chars += line_len
                j += 1
            window = session[i:j]
            participants = sorted({m["sender"] for m in window})
            start, end = window[0]["sent_at"], window[-1]["sent_at"]
            lines = [_fmt_header(room, start, end, participants)]
            lines += [f"{m['sender']}: {' '.join(m['text'].split())}" for m in window]
            text = "\n".join(lines)
            chunks.append({
                "chunk_index": len(chunks),
                "start_seq": window[0]["seq"],
                "end_seq": window[-1]["seq"],
                "start_at": start,
                "end_at": end,
                "n_messages": len(window),
                "participants": participants,
                "text": text,
                "content_hash": hashlib.sha1(text.encode("utf-8")).hexdigest(),
            })
            if j >= n:
                break
            i = max(i + 1, j - overlap)
    return chunks
