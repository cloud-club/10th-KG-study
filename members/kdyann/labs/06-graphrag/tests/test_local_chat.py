import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import local_chat


class FakeGraph:
    def __init__(self, candidate_rows, topic_rows=None, exploration_rows=None, fallback_rows=None):
        self.candidate_rows = candidate_rows
        self.topic_rows = topic_rows or []
        self.exploration_rows = exploration_rows or []
        self.fallback_rows = fallback_rows or []
        self.queries = []

    def query(self, cypher, **params):
        self.queries.append((cypher, params))
        if cypher == local_chat.CANDIDATE_QUERY:
            return self.candidate_rows
        if cypher == local_chat.EXPLORATION_QUERY:
            return self.exploration_rows
        if cypher == local_chat.FALLBACK_QUERY:
            return self.fallback_rows
        return self.topic_rows


class FakeDocuments:
    def __init__(self):
        self.rows = {
            "own-1": {"corpus": "own", "text": "내 글은 AI를 다룹니다. 저는 실험 과정을 공유합니다."},
            "ref-1": {"corpus": "reference", "text": "AI 활용 팁을 소개합니다. 따라 해보세요."},
            "ref-2": {"corpus": "reference", "text": "NextJS 개발 도구를 소개합니다."},
        }

    def get_many(self, source_ids):
        return {key: self.rows[key] for key in source_ids if key in self.rows}


def row():
    own = "내 글은 AI를 다룹니다."
    reference = "AI 활용 팁을 소개합니다."
    return {"own_post_id": "own-1", "reference_post_id": "ref-1", "topic": "AI",
            "reference_url": "https://www.instagram.com/p/abc123/",
            "published_at": "2026-09-30T12:00:00+00:00", "like_count": 120,
            "own_quote": own, "own_start": 0, "own_end": len(own),
            "ref_quote": reference, "ref_start": 0, "ref_end": len(reference)}


def exploration_row():
    quote = "NextJS 개발 도구를 소개합니다."
    return {"own_post_id": None, "reference_post_id": "ref-2", "topic": "NextJS",
            "interest_area": "개발", "reference_url": "https://www.instagram.com/p/nextjs/",
            "published_at": "2026-09-30T12:00:00+00:00", "like_count": 125,
            "own_quote": None, "own_start": None, "own_end": None,
            "ref_quote": quote, "ref_start": 0, "ref_end": len(quote)}


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.graph = FakeGraph([row()])
        self.documents = FakeDocuments()
        self.generated_contexts = []

        def generate(context):
            self.generated_contexts.append(context)
            return {"title": "내 AI 실험 노트", "body": "AI 활용법을 내 실험 관점에서 정리해 볼게요.",
                    "evidence": [{"source_id": "own-1", "quote": "내 글은 AI를 다룹니다."},
                                 {"source_id": "ref-1", "quote": "AI 활용 팁을 소개합니다."}]}

        self.service = local_chat.ChatService(self.graph, self.documents, generator=generate,
            now=lambda: datetime(2026, 10, 1, 12, tzinfo=timezone.utc))

    def test_recommendation_is_read_only_graph_match_with_exact_evidence(self):
        answer = self.service.chat({"message": "최근 주제 추천해줘"})
        self.assertEqual(answer["intent"], "recommend")
        self.assertEqual(answer["candidates"][0]["status"], "graph_match")
        self.assertEqual(answer["candidates"][0]["like_count"], 120)
        self.assertIn("최종 추천 판정은 아닙니다", answer["reply"])
        self.assertEqual(self.generated_contexts, [])
        self.assertEqual(self.graph.queries[0][0], local_chat.CANDIDATE_QUERY)

    def test_invalid_graph_evidence_or_old_post_is_not_recommended(self):
        broken = row()
        broken["ref_quote"] = "없는 문장"
        self.graph.candidate_rows = [broken]
        self.assertEqual(self.service.chat({"action": "recommend"})["candidates"], [])
        old = row()
        old["published_at"] = "2026-09-20T12:00:00Z"
        self.graph.candidate_rows = [old]
        self.assertEqual(self.service.chat({"action": "recommend"})["candidates"], [])

    def test_topics_need_exact_own_evidence(self):
        self.graph.topic_rows = [
            {"topic": "AI", "own_post_id": "own-1", "quote": "내 글은 AI를 다룹니다.",
             "start_offset": 0, "end_offset": len("내 글은 AI를 다룹니다.")},
            {"topic": "가짜", "own_post_id": "own-1", "quote": "없는 문장",
             "start_offset": 0, "end_offset": 5},
        ]
        answer = self.service.chat({"action": "topics"})
        self.assertEqual(answer["topics"], [{"topic": "AI", "own_post_ids": ["own-1"]}])

    def test_script_requires_current_selected_candidate(self):
        with self.assertRaises(local_chat.ChatError):
            self.service.chat({"action": "script", "candidate_id": "other"})
        self.assertEqual(self.generated_contexts, [])
        candidate_id = self.service.chat({"action": "recommend"})["candidates"][0]["candidate_id"]
        answer = self.service.chat({"action": "script", "candidate_id": candidate_id})
        self.assertEqual(answer["intent"], "script")
        self.assertEqual(answer["script"]["title"], "내 AI 실험 노트")
        self.assertEqual(len(self.generated_contexts), 1)

    def test_new_topic_exploration_is_selectable_and_uses_reference_only(self):
        self.graph.exploration_rows = [exploration_row()]
        cards = self.service.chat({"action": "recommend"})["candidates"]
        exploring = next(card for card in cards if card["status"] == "interest_exploration")
        self.assertEqual(exploring["interest_area"], "개발")
        self.assertEqual(exploring["own_evidence"], [])
        self.assertNotEqual(exploring["candidate_id"], cards[0]["candidate_id"])

        def generate(context):
            self.generated_contexts.append(context)
            return {"title": "NextJS 소개", "body": "NextJS 개발 도구에 관해 살펴봅니다.",
                    "evidence": [{"source_id": "ref-2", "quote": "NextJS 개발 도구를 소개합니다."}]}

        self.service.generator = generate
        answer = self.service.chat({"action": "script", "candidate_id": exploring["candidate_id"]})
        self.assertEqual(answer["script"]["title"], "NextJS 소개")
        self.assertIsNone(self.generated_contexts[-1]["shared_topic"])
        self.assertEqual([source["source_id"] for source in self.generated_contexts[-1]["sources"]], ["ref-2"])

    def test_exploration_requires_reference_evidence(self):
        broken = exploration_row()
        broken["ref_quote"] = "없는 문장"
        self.graph.exploration_rows = [broken]
        self.assertEqual(len(self.service.chat({"action": "recommend"})["candidates"]), 1)

    def test_unclassified_topic_needs_broad_topic_evidence(self):
        candidate = exploration_row()
        candidate.update({"match_type": "broad_interest_fallback", "broad_quote": "NextJS 개발 도구를 소개합니다.",
                          "broad_start": 0, "broad_end": len("NextJS 개발 도구를 소개합니다.")})
        self.graph.fallback_rows = [candidate]
        result = self.service.chat({"action": "recommend"})["candidates"]
        self.assertEqual(result[-1]["status"], "broad_interest_fallback")
        candidate["broad_quote"] = "근거 없는 개발"
        self.assertEqual(len(self.service.chat({"action": "recommend"})["candidates"]), 1)

    def test_same_reference_on_distinct_paths_uses_selected_card(self):
        second = row()
        second["own_post_id"] = "own-2"
        second["topic"] = "디자인"
        second["own_quote"] = "디자인을 다룹니다."
        second["own_start"] = 0
        second["own_end"] = len(second["own_quote"])
        self.documents.rows["own-2"] = {"corpus": "own", "text": "디자인을 다룹니다. 제 작업을 공유합니다."}
        self.graph.candidate_rows = [row(), second]
        cards = self.service.chat({"action": "recommend"})["candidates"]
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["reference_post_id"], cards[1]["reference_post_id"])
        self.assertNotEqual(cards[0]["candidate_id"], cards[1]["candidate_id"])
        self.assertEqual(cards[0]["candidate_id"], self.service.chat({"action": "recommend"})["candidates"][0]["candidate_id"])
        def generate_selected(context):
            self.generated_contexts.append(context)
            return {"title": "디자인 대본", "body": "내 작업 관점에서 디자인을 이야기합니다.",
                    "evidence": [{"source_id": "own-2", "quote": "디자인을 다룹니다."},
                                 {"source_id": "ref-1", "quote": "AI 활용 팁을 소개합니다."}]}
        self.service.generator = generate_selected
        self.service.chat({"action": "script", "candidate_id": cards[1]["candidate_id"]})
        self.assertEqual(self.generated_contexts[-1]["shared_topic"], "디자인")
        self.assertEqual(self.generated_contexts[-1]["sources"][0]["source_id"], "own-2")

    def test_natural_script_without_selection_only_shows_help(self):
        answer = self.service.chat({"message": "대본 써줘"})
        self.assertEqual(answer["intent"], "help")
        self.assertEqual(self.generated_contexts, [])

    def test_requested_natural_phrases_route_to_supported_intents(self):
        self.graph.topic_rows = [{"topic": "AI", "own_post_id": "own-1",
                                  "quote": "내 글은 AI를 다룹니다.", "start_offset": 0,
                                  "end_offset": len("내 글은 AI를 다룹니다.")}]
        self.assertEqual(self.service.chat({"message": "내 게시물의 주제는 뭐야?"})["intent"], "topics")
        self.assertEqual(self.service.chat({"message": "이번에 유행한 것 중에 내 게시물에 참고할만한거 있어?"})["intent"], "recommend")

    def test_request_and_generated_script_reject_untrusted_inputs(self):
        for payload in ({"action": "script"}, {"action": "recommend", "candidate_id": "ref-1"},
                        {"message": "x" * 501}, {"message": "추천", "cypher": "MATCH (n) DETACH DELETE n"}):
            with self.subTest(payload=payload), self.assertRaises(local_chat.ChatError):
                local_chat.validate_request(payload)
        with self.assertRaises(local_chat.ChatError):
            local_chat.validate_script({"title": "제목", "body": "본문", "evidence": [
                {"source_id": "own-1", "quote": "없는 근거"},
                {"source_id": "ref-1", "quote": "AI 활용 팁을 소개합니다."}]}, self.documents.rows)
        excerpted = {"own-1": {"corpus": "own", "text": "내 글은 AI를 다룹니다."},
                     "ref-1": {"corpus": "reference", "text": "AI 활용 팁을 소개합니다."}}
        with self.assertRaises(local_chat.ChatError):
            local_chat.validate_script({"title": "제목", "body": "본문", "evidence": [
                {"source_id": "own-1", "quote": "저는 실험 과정을 공유합니다."},
                {"source_id": "ref-1", "quote": "AI 활용 팁을 소개합니다."}]}, excerpted)

    def test_local_host_and_origin_must_match_server_port(self):
        self.assertTrue(local_chat.allowed_host_origin("127.0.0.1:8765", "http://localhost:8765", 8765))
        self.assertTrue(local_chat.allowed_host_origin("localhost:8765", None, 8765))
        self.assertFalse(local_chat.allowed_host_origin("localhost:9999", None, 8765))
        self.assertFalse(local_chat.allowed_host_origin("evil.example:8765", "http://localhost:8765", 8765))
        self.assertFalse(local_chat.allowed_host_origin("localhost:8765", "https://evil.example", 8765))


if __name__ == "__main__":
    unittest.main()
