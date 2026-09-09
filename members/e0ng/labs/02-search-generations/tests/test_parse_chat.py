import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from parse_chat import parse_csv, previous_month


class ParseChatTest(unittest.TestCase):
    def test_csv_format_and_quoted_multiline(self):
        text = (
            "Date,User,Message\n"
            '2025-02-12 09:21:44,김연우,"수강신청하려고\n추가로 확인할 내용이 있어요"\n'
            "2025-02-12 09:22:01,이구름,어떤 과목인데?\n"
        )
        messages = parse_csv(text)
        self.assertEqual(2, len(messages))
        self.assertEqual("수강신청하려고\n추가로 확인할 내용이 있어요", messages[0]["message"])
        self.assertEqual("2025-02-12T09:21:44", messages[0]["timestamp"])

    def test_required_columns(self):
        with self.assertRaisesRegex(ValueError, "message"):
            parse_csv("Date,User\n2025-02-12 09:21:44,김연우\n")

    def test_blank_date_and_user_row_continues_previous_message(self):
        text = (
            "Date,User,Message\n"
            "2025-02-12 09:21:44,김연우,첫 줄\n"
            ",,둘째 줄\n"
            "2025-02-12 09:22:01,이구름,다음 메시지\n"
        )
        messages = parse_csv(text)
        self.assertEqual(2, len(messages))
        self.assertEqual("첫 줄\n둘째 줄", messages[0]["message"])

    def test_previous_month_uses_latest_message_date(self):
        messages = [
            {"timestamp": "2026-07-31T23:59:59", "sender": "A", "message": "이전"},
            {"timestamp": "2026-08-01T00:00:00", "sender": "A", "message": "포함"},
            {"timestamp": "2026-08-31T23:59:59", "sender": "A", "message": "포함"},
            {"timestamp": "2026-09-09T15:48:45", "sender": "A", "message": "최신"},
        ]
        filtered, start, end = previous_month(messages)
        self.assertEqual(["포함", "포함"], [item["message"] for item in filtered])
        self.assertEqual("2026-08-01", start.date().isoformat())
        self.assertEqual("2026-09-01", end.date().isoformat())


if __name__ == "__main__":
    unittest.main()
