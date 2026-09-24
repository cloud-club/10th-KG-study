from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from rag_agent import answer_question, build_context, cited_numbers, invalid_citations  # noqa: E402


class FakeResponse:
    output_text = "인증서를 갱신한 뒤 서비스를 검증합니다 [C1]."


class FakeResponses:
    def __init__(self) -> None:
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return FakeResponse()


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


class RagAgentTest(unittest.TestCase):
    def test_context_uses_stable_citation_ids(self) -> None:
        context = build_context(
            [
                {
                    "source_path": "a.md",
                    "heading": "조치",
                    "date": "2026-01-01",
                    "content": "첫 번째 근거",
                },
                {
                    "source_path": "b.md",
                    "heading": None,
                    "date": None,
                    "content": "두 번째 근거",
                },
            ]
        )
        self.assertIn("[C1] a.md#조치", context)
        self.assertIn("[C2] b.md", context)

    def test_citation_validation(self) -> None:
        answer = "갱신 후 재시작한다 [C1]. 검증한다 [C3]."
        self.assertEqual({1, 3}, cited_numbers(answer))
        self.assertEqual({3}, invalid_citations(answer, evidence_count=2))

    def test_answer_uses_responses_api_and_keeps_valid_citation(self) -> None:
        client = FakeClient()
        answer = answer_question(
            "무엇을 확인했지?",
            [
                {
                    "source_path": "runbook.md",
                    "heading": "검증",
                    "date": "2026-01-01",
                    "content": "갱신 후 준비 상태를 확인한다.",
                }
            ],
            client=client,
        )
        self.assertIn("[C1]", answer)
        self.assertIn("질문:\n무엇을 확인했지?", client.responses.request["input"])


if __name__ == "__main__":
    unittest.main()
