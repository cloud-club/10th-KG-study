"""kakao_parser 순수 함수 테스트. 실행: python3 -m unittest discover -s members/sese2204/labs/01-kakao-ingest/src"""
from __future__ import annotations

import unittest
from datetime import datetime

from kakao_parser import Chat, classify, classify_system, parse_lines, parse_timestamp_text, to_datetime

HEADER = ["﻿우리동네 카카오톡 대화", "저장한 날짜 : 2024년 8월 2일 오후 4:03", "", ""]


def chat(*body: str) -> Chat:
    return parse_lines([*HEADER, *body])


class HeaderTests(unittest.TestCase):
    def test_room_name_and_exported_at_are_read_from_first_two_lines(self):
        c = chat("2023년 8월 9일 오전 12:34", "2023년 8월 9일 오전 12:34, 홍길동 : 안녕")
        self.assertEqual(c.room_name, "우리동네")
        self.assertEqual(c.exported_at, datetime(2024, 8, 2, 16, 3))

    def test_file_without_header_still_parses_messages(self):
        c = parse_lines(["2023년 8월 9일 오전 12:34, 홍길동 : 안녕"])
        self.assertEqual(c.room_name, "")
        self.assertIsNone(c.exported_at)
        self.assertEqual(len(c.messages), 1)


class TimestampTests(unittest.TestCase):
    def test_am_12_is_midnight_and_pm_12_is_noon(self):
        self.assertEqual(to_datetime("2023", "8", "9", "오전", "12", "05"), datetime(2023, 8, 9, 0, 5))
        self.assertEqual(to_datetime("2023", "8", "9", "오후", "12", "05"), datetime(2023, 8, 9, 12, 5))
        self.assertEqual(to_datetime("2023", "8", "9", "오후", "3", "05"), datetime(2023, 8, 9, 15, 5))
        self.assertEqual(to_datetime("2023", "12", "31", "오전", "11", "59"), datetime(2023, 12, 31, 11, 59))

    def test_parse_timestamp_text_rejects_message_lines(self):
        self.assertEqual(parse_timestamp_text("2024년 8월 2일 오후 4:03"), datetime(2024, 8, 2, 16, 3))
        self.assertIsNone(parse_timestamp_text("2024년 8월 2일 오후 4:03, 홍길동 : 안녕"))
        self.assertIsNone(parse_timestamp_text("아무 말"))


class MessageTests(unittest.TestCase):
    def test_basic_message_fields(self):
        c = chat("2023년 8월 9일 오전 12:34", "2023년 8월 9일 오전 12:34, 홍길동 : 얘들아")
        (m,) = c.messages
        self.assertEqual((m.seq, m.line_no, m.sender, m.kind, m.content), (1, 6, "홍길동", "text", "얘들아"))
        self.assertEqual(m.sent_at, datetime(2023, 8, 9, 0, 34))

    def test_day_divider_lines_are_skipped_and_seq_counts_only_messages(self):
        c = chat(
            "2023년 8월 9일 오전 12:34",
            "2023년 8월 9일 오전 12:34, 홍길동 : 하나",
            "2023년 8월 10일 오전 12:35",
            "2023년 8월 10일 오전 12:35, 홍길동 : 둘",
        )
        self.assertEqual([m.seq for m in c.messages], [1, 2])
        self.assertEqual([m.content for m in c.messages], ["하나", "둘"])

    def test_multiline_message_keeps_inner_blank_lines_and_drops_trailing_ones(self):
        c = chat(
            "2023년 8월 9일 오후 6:47, 홍길동 : 동네닭갈비집",
            "",
            "서울 어딘가 1-2",
            "",
            "2023년 8월 10일 오전 12:35",
            "2023년 8월 10일 오전 12:35, 홍길동 : 다음",
        )
        self.assertEqual(c.messages[0].content, "동네닭갈비집\n\n서울 어딘가 1-2")
        self.assertEqual(c.messages[1].content, "다음")

    def test_content_containing_separator_splits_on_first_only(self):
        c = chat("2023년 8월 9일 오전 9:00, 홍길동 : 비율 3 : 1 : 2")
        self.assertEqual(c.messages[0].sender, "홍길동")
        self.assertEqual(c.messages[0].content, "비율 3 : 1 : 2")

    def test_crlf_lines_are_stripped(self):
        c = parse_lines(["우리동네 카카오톡 대화\r\n", "저장한 날짜 : 2024년 8월 2일 오후 4:03\r\n", "\r\n",
                         "2023년 8월 9일 오전 9:00, 홍길동 : 안녕\r\n", "둘째 줄\r\n"])
        self.assertEqual(c.messages[0].content, "안녕\n둘째 줄")

    def test_empty_content_is_allowed(self):
        c = chat("2023년 8월 9일 오전 9:00, 홍길동 : ")
        self.assertEqual(c.messages[0].content, "")
        self.assertEqual(c.messages[0].kind, "text")

    def test_senders_are_unique_in_first_seen_order(self):
        c = chat(
            "2023년 8월 9일 오전 9:00, 을 : a",
            "2023년 8월 9일 오전 9:00, 갑 : b",
            "2023년 8월 9일 오전 9:00, 을 : c",
            "2023년 8월 9일 오전 9:01, 병님이 나갔습니다.",
        )
        self.assertEqual(c.senders, ("을", "갑"))


class SystemEventTests(unittest.TestCase):
    def test_leave_invite_join_have_no_sender(self):
        c = chat(
            "2024년 8월 2일 오후 3:39, 홍길동님이 나갔습니다.",
            "2024년 8월 2일 오후 3:40, 홍길동님이 김철수님을 초대했습니다.",
            "2024년 8월 2일 오후 3:41, 김철수님이 들어왔습니다.",
            "2024년 8월 2일 오후 3:42, 채팅방 관리자가 메시지를 가렸습니다.",
        )
        self.assertEqual([m.sender for m in c.messages], [None] * 4)
        self.assertEqual([m.kind for m in c.messages], ["system_leave", "system_invite", "system_join", "system"])
        self.assertEqual(c.messages[0].content, "홍길동님이 나갔습니다.")

    def test_classify_system_directly(self):
        self.assertEqual(classify_system("아무개님이 나갔습니다."), "system_leave")
        self.assertEqual(classify_system("뭔가 다른 안내"), "system")


class ClassifyTests(unittest.TestCase):
    def test_media_and_special_kinds(self):
        cases = {
            "사진": "photo", "사진 3장": "photo", "<사진 읽지 않음>": "photo",
            "<사진 읽지 않음>\n<사진 읽지 않음>": "photo",
            "동영상": "video", "<동영상 읽지 않음>": "video",
            "음성메시지": "voice", "<음성메시지 읽지 않음>": "voice",
            "이모티콘": "emoticon",
            "파일: 고산자 복사본 4.m4a": "file",
            "삭제된 메시지입니다.": "deleted",
            "샵검색: 날씨": "shop",
            "https://youtu.be/abc": "link",
        }
        for content, kind in cases.items():
            with self.subTest(content=content):
                self.assertEqual(classify(content), kind)

    def test_hashed_attachment_filenames_are_media_not_text(self):
        h = "d908ea8620193bc455c88b52e3683d554087f44cc90e083c83e5d56aec5db90d"
        cases = {
            f"{h}.jpg": "photo", f"{h}.PNG": "photo", f"{h}.webp": "photo",
            f"{h}.mp4": "video", f"{h}.m4a": "voice", f"{h}.pdf": "file",
            f"{h}.jpg\n{h}.jpg": "photo",
        }
        for content, kind in cases.items():
            with self.subTest(content=content[-12:]):
                self.assertEqual(classify(content), kind)

    def test_hash_mixed_with_words_stays_text(self):
        h = "d908ea8620193bc455c88b52e3683d554087f44cc90e083c83e5d56aec5db90d"
        for content in [f"{h}.jpg 이거 봐", f"봐 {h}.jpg", f"{h}.jpg\n웃기지", "deadbeef.jpg"]:
            with self.subTest(content=content[:20]):
                self.assertEqual(classify(content), "text")

    def test_plain_text_including_words_that_merely_start_with_keywords(self):
        for content in ["사진 ㄱㄱ", "사진은 어디", "이모티콘 좀 그만", "https://a.b 이거 봐", "봐 https://a.b", "안녕"]:
            with self.subTest(content=content):
                self.assertEqual(classify(content), "text")


if __name__ == "__main__":
    unittest.main()
