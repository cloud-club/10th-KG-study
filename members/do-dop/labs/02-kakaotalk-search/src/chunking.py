"""벡터 검색용 청킹: 같은 발신자가 짧은 간격으로 보낸 메시지를 하나로 묶는다.

노트("벡터 검색 파이프라인")에서 정리한 것처럼, 너무 잘게 나누면 문맥이 부족하고
너무 크게 묶으면 여러 주제가 섞인다. window_minutes로 그 크기를 조절한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def chunk_messages(messages: list[dict], window_minutes: int) -> list[dict]:
    """timestamp 순으로 정렬된 messages를 같은 sender_id・간격 이내끼리 묶는다.

    window_minutes가 0이면 메시지 하나가 곧 청크 하나가 된다(청킹 없음).
    """
    # 이 시간 안에 같은 사람이 연속으로 보낸 메시지를 하나로 묶는다.
    window = timedelta(minutes=window_minutes)
    chunks: list[dict] = []
    current: dict | None = None

    for message in messages:
        sent_at = datetime.fromisoformat(message["sent_at"])
        sender_id = message["sender_id"]

        # 기존 청크와 발신자가 같고 시간 간격도 짧으면 본문을 이어 붙인다.
        if (
            current is not None
            and current["sender_id"] == sender_id
            and window_minutes > 0
            and sent_at - datetime.fromisoformat(current["ended_at"]) <= window
        ):
            current["texts"].append(message["text"])
            current["message_ids"].append(message["chunk_id"])
            current["ended_at"] = message["sent_at"]
            current["message_count"] += 1
            continue

        # 조건이 달라지면 기존 청크를 끝내고 새 청크를 시작한다.
        if current is not None:
            chunks.append(_finalize(current))

        current = {
            "sender_id": sender_id,
            "started_at": message["sent_at"],
            "ended_at": message["sent_at"],
            "message_count": 1,
            "texts": [message["text"]],
            "message_ids": [message["chunk_id"]],
        }

    if current is not None:
        chunks.append(_finalize(current))

    return chunks


def _finalize(current: dict) -> dict:
    # 첫 메시지 ID를 이용해 다시 실행해도 같은 청크 ID가 나오게 한다.
    first_message_id = current["message_ids"][0]
    return {
        "chunk_id": f"chunk-{first_message_id}",
        "sender_id": current["sender_id"],
        "started_at": current["started_at"],
        "ended_at": current["ended_at"],
        "message_count": current["message_count"],
        "content": "\n".join(current["texts"]),
    }
