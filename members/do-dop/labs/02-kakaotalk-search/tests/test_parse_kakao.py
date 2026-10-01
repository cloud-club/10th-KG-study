import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "src" / "parse_kakao.py"
SPEC = importlib.util.spec_from_file_location("parse_kakao", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
parse_kakao = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = parse_kakao
SPEC.loader.exec_module(parse_kakao)


class ParseKakaoTest(unittest.TestCase):
    def test_parses_and_anonymizes_messages(self):
        lines = [
            "저장한 날짜 : 2026. 9. 12. 오후 1:00\n",
            "2026년 9월 10일 목요일\n",
            "2026. 9. 10. 오전 12:05, 도연 : 첫 메시지\n",
            "2026. 9. 10. 오후 12:30, 친구 : 두 번째 메시지\n",
            "2026. 9. 10. 오후 1:01, 도연 : 세 번째 메시지\n",
        ]

        messages, stats = parse_kakao.parse_lines(lines)

        self.assertEqual(3, stats.messages)
        self.assertEqual(2, stats.senders)
        self.assertEqual("user-001", messages[0].sender_id)
        self.assertEqual("user-002", messages[1].sender_id)
        self.assertEqual("user-001", messages[2].sender_id)
        self.assertEqual("2026-09-10T00:05:00", messages[0].sent_at)
        self.assertEqual("2026-09-10T12:30:00", messages[1].sent_at)

    def test_preserves_multiline_message(self):
        lines = [
            "2026. 9. 10. 오후 7:32, 사용자 : 첫 줄\n",
            "두 번째 줄\n",
            "세 번째 줄\n",
            "2026. 9. 10. 오후 7:33, 사용자 : 다음 메시지\n",
        ]

        messages, stats = parse_kakao.parse_lines(lines)

        self.assertEqual("첫 줄\n두 번째 줄\n세 번째 줄", messages[0].text)
        self.assertEqual(1, stats.multiline_messages)
        self.assertEqual(2, stats.continuation_lines)
        self.assertEqual(1, messages[0].source_line_start)
        self.assertEqual(3, messages[0].source_line_end)

    def test_parses_24_hour_timestamp(self):
        lines = [
            "2026. 9. 10. 00:05, 사용자 : 자정 메시지\n",
            "2026. 9. 10. 23:54, 사용자 : 밤 메시지\n",
        ]

        messages, stats = parse_kakao.parse_lines(lines)

        self.assertEqual(2, stats.messages)
        self.assertEqual("2026-09-10T00:05:00", messages[0].sent_at)
        self.assertEqual("2026-09-10T23:54:00", messages[1].sent_at)

    def test_skips_timestamped_system_event(self):
        lines = [
            "2026. 9. 10. 오후 7:32, 사용자 : 검색할 메시지\n",
            "2026. 9. 10. 오후 7:33, 사용자가 들어왔습니다.\n",
            "2026. 9. 10. 오후 7:34, 사용자 : 다음 메시지\n",
        ]

        messages, stats = parse_kakao.parse_lines(lines)

        self.assertEqual(2, len(messages))
        self.assertEqual(1, stats.skipped_system_events)
        self.assertNotIn("들어왔습니다", messages[0].text)

    def test_skips_24_hour_system_event(self):
        lines = [
            "2026. 9. 10. 19:32, 사용자 : 검색할 메시지\n",
            "2026. 9. 10. 19:33: 사용자가 들어왔습니다.\n",
            "2026. 9. 10. 19:34, 사용자 : 다음 메시지\n",
        ]

        messages, stats = parse_kakao.parse_lines(lines)

        self.assertEqual(2, len(messages))
        self.assertEqual(1, stats.skipped_system_events)


if __name__ == "__main__":
    unittest.main()
