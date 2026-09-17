import importlib.util
import sys
import unittest
from pathlib import Path


def _load(module_name: str):
    module_path = Path(__file__).parents[1] / "src" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


chunking = _load("chunking")


class ChunkMessagesTest(unittest.TestCase):
    def test_merges_same_sender_within_window(self):
        # 같은 사람이 1분 안에 연속으로 보낸 두 메시지는 하나로 묶인다.
        messages = [
            {"chunk_id": "msg-000001", "sender_id": "user-001", "sent_at": "2026-09-10T19:30:00", "text": "저녁 먹었어?"},
            {"chunk_id": "msg-000002", "sender_id": "user-001", "sent_at": "2026-09-10T19:30:30", "text": "아직"},
            {"chunk_id": "msg-000003", "sender_id": "user-002", "sent_at": "2026-09-10T19:33:00", "text": "같이 먹을래"},
        ]

        chunks = chunking.chunk_messages(messages, window_minutes=1)

        self.assertEqual(2, len(chunks))
        self.assertEqual("user-001", chunks[0]["sender_id"])
        self.assertEqual(2, chunks[0]["message_count"])
        self.assertEqual("저녁 먹었어?\n아직", chunks[0]["content"])
        self.assertEqual("user-002", chunks[1]["sender_id"])

    def test_splits_when_gap_exceeds_window(self):
        # 같은 사람이라도 시간 차이가 크면 서로 다른 청크가 된다.
        messages = [
            {"chunk_id": "msg-000001", "sender_id": "user-001", "sent_at": "2026-09-10T09:00:00", "text": "아침"},
            {"chunk_id": "msg-000002", "sender_id": "user-001", "sent_at": "2026-09-10T19:00:00", "text": "저녁"},
        ]

        chunks = chunking.chunk_messages(messages, window_minutes=1)

        self.assertEqual(2, len(chunks))
        self.assertEqual(1, chunks[0]["message_count"])
        self.assertEqual(1, chunks[1]["message_count"])

    def test_window_zero_means_one_message_per_chunk(self):
        # 윈도우 0은 청킹 없이 메시지 하나를 청크 하나로 사용한다.
        messages = [
            {"chunk_id": "msg-000001", "sender_id": "user-001", "sent_at": "2026-09-10T19:30:00", "text": "하나"},
            {"chunk_id": "msg-000002", "sender_id": "user-001", "sent_at": "2026-09-10T19:30:10", "text": "둘"},
        ]

        chunks = chunking.chunk_messages(messages, window_minutes=0)

        self.assertEqual(2, len(chunks))

    def test_chunk_id_is_deterministic_from_first_message(self):
        # 청크 ID는 첫 메시지 ID로부터 일정하게 만들어진다.
        messages = [
            {"chunk_id": "msg-000007", "sender_id": "user-001", "sent_at": "2026-09-10T19:30:00", "text": "안녕"},
        ]

        chunks = chunking.chunk_messages(messages, window_minutes=1)

        self.assertEqual("chunk-msg-000007", chunks[0]["chunk_id"])


if __name__ == "__main__":
    unittest.main()
