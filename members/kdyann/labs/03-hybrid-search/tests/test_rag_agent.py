"""근거 없는 답변 차단·발췌 경계·백엔드 실패를 네트워크 없이 검증한다."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import rag_agent as rag


def source(identifier="one", text="Pen.dev + Claude Code 디자인 시스템 만드는 방법입니다."):
    return {"id": identifier, "text": text, "permalink": f"https://www.instagram.com/p/{identifier}/",
            "corpus": "own", "score": 1}


def answer(quote="Claude Code", identifier="one"):
    return {"claims": [{"text": "내 글은 Claude Code를 소개한다.",
                        "evidence": [{"source_id": identifier, "quote": quote}]}], "unresolved": []}


def api_result(value=None):
    return {"status": "completed", "output": [{"type": "message", "role": "assistant",
             "status": "completed", "content": [{"type": "output_text", "text": json.dumps(value or answer())}]}]}


def supported_review(context):
    return {"claims": [{"index": row["index"], "supported": True, "reason": "근거로 확인됨"}
                       for row in context["claims"]],
            "unresolved": [{"index": row["index"], "relevant": True, "reason": "질문에 필요한 미확인 사항"}
                           for row in context["unresolved"]],
            "question_complete": not bool(context["unresolved"]),
            "missing_reason": "아직 확인하지 못한 요구가 있다" if context["unresolved"] else ""}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.context = rag.prepare_context("내가 사용한 도구?", [source()])

    def test_binds_trusted_source_url_to_each_claim(self):
        result = rag.validate_answer(answer(), self.context)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["claims"][0]["evidence"][0]["permalink"], source()["permalink"])

    def test_every_claim_requires_evidence(self):
        value = answer()
        value["claims"].append({"text": "근거 없는 두 번째 주장", "evidence": []})
        with self.assertRaises(rag.EvidenceError):
            rag.validate_answer(value, self.context)

    def test_rejects_out_of_context_ids_empty_or_invented_quotes(self):
        for value in (answer(identifier="missing"), answer(quote=""), answer(quote="   "),
                      answer(quote="Claude Code로 배포했다")):
            with self.subTest(value=value), self.assertRaises(rag.EvidenceError):
                rag.validate_answer(value, self.context)

    def test_quote_must_be_in_provided_excerpt_not_full_source(self):
        context = rag.prepare_context("도구?", [source(text="앞부분 뒤에숨긴도구")], per_document=3)
        self.assertTrue(context["sources"][0]["truncated"])
        with self.assertRaises(rag.EvidenceError):
            rag.validate_answer(answer(quote="뒤에숨긴도구"), context)

    def test_whitespace_normalization_allows_contiguous_excerpt(self):
        context = rag.prepare_context("도구?", [source(text="Claude\n Code를 활용한다")])
        self.assertEqual(rag.validate_answer(answer(quote="Claude Code"), context)["status"], "answered")
        with self.assertRaises(rag.EvidenceError):
            rag.validate_answer(answer(quote="Claude 활용한다"), context)

    def test_strict_shape_rejects_model_urls_uncited_answer_and_empty_response(self):
        wrong = answer()
        wrong["claims"][0]["evidence"][0]["permalink"] = "https://evil.example"
        for value in (wrong, {"answer": "아무말"}, {"claims": [], "unresolved": []},
                      {"claims": [], "unresolved": [1]}):
            with self.subTest(value=value), self.assertRaises(rag.EvidenceError):
                rag.validate_answer(value, self.context)

    def test_context_dedup_total_cap_and_unsafe_urls_filtered(self):
        invalid = source("bad")
        invalid["permalink"] = "https://www.instagram.com@evil.example/p/bad/"
        rows = [invalid, source(text="abcdef"), source(text="duplicate"), source("two", "ghijkl")]
        context = rag.prepare_context("질문", rows, per_document=5, total_chars=8)
        self.assertEqual([row["excerpt"] for row in context["sources"]], ["abcde", "ghi"])
        self.assertEqual([row["source_id"] for row in context["sources"]], ["one", "two"])

    def test_partial_answer_retains_unresolved_reason(self):
        value = answer()
        value["unresolved"] = ["참고 글 작성자의 실제 사용은 확인할 수 없다."]
        self.assertEqual(rag.validate_answer(value, self.context)["status"], "partial")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = {"runs_path": Path(self.temp.name) / "runs.jsonl",
                      "unresolved_path": Path(self.temp.name) / "unresolved.jsonl"}

    def ask(self, rows=None, generator=None, **kwargs):
        searcher = Mock()
        searcher.search.return_value = [source()] if rows is None else rows
        kwargs.setdefault("reviewer", supported_review)
        return rag.answer_question(searcher, "내 도구?", generator=generator or Mock(return_value=answer()),
                                   **self.paths, **kwargs)

    def test_empty_search_abstains_without_model_and_records_question(self):
        generator = Mock()
        result = self.ask([], generator)
        generator.assert_not_called()
        self.assertEqual(result["status"], "unanswered")
        self.assertFalse(result["generated"])
        self.assertEqual(json.loads(self.paths["unresolved_path"].read_text())["question"], "내 도구?")

    def test_prepare_only_records_prepared_not_generated_or_answered(self):
        generator = Mock()
        result = self.ask(generator=generator, prepare_only=True)
        generator.assert_not_called()
        self.assertEqual(result["status"], "prepared")
        self.assertFalse(result["generated"])
        self.assertFalse(self.paths["unresolved_path"].exists())

    def test_invalid_model_evidence_never_stored_as_success(self):
        result = self.ask(generator=Mock(return_value=answer(quote="없는 근거")))
        self.assertEqual(result["status"], "generation_error")
        self.assertEqual(result["claims"], [])
        self.assertEqual(json.loads(self.paths["runs_path"].read_text())["status"], "generation_error")

    def test_retrieval_failure_does_not_become_data_unanswered_or_leak_exception(self):
        searcher, generator = Mock(), Mock()
        searcher.search.side_effect = RuntimeError("secret-provider-details")
        result = rag.answer_question(searcher, "질문", generator=generator, **self.paths)
        generator.assert_not_called()
        self.assertEqual(result["status"], "retrieval_error")
        self.assertNotIn("secret-provider-details", json.dumps(result))

    def test_unexpected_generation_failure_keeps_category_and_hides_details(self):
        result = self.ask(generator=Mock(side_effect=RuntimeError("secret-key")))
        self.assertEqual(result["status"], "generation_error")
        self.assertNotIn("secret-key", json.dumps(result))

    def test_partial_response_saved_to_unresolved_with_source_ids(self):
        value = answer()
        value["unresolved"] = ["참고 글의 실제 사용 여부는 근거가 없다."]
        result = self.ask(generator=Mock(return_value=value))
        self.assertEqual(result["status"], "partial")
        row = json.loads(self.paths["unresolved_path"].read_text())
        self.assertEqual(row["source_ids"], ["one"])
        self.assertIn(value["unresolved"][0], row["reasons"])

    def test_grounding_rejection_removes_claim_before_run_record_and_render(self):
        reviewer = Mock(return_value={"claims": [{"index": 0, "supported": False,
                    "reason": "인용은 도구 소개만 확인하고 주장한 사용 경험은 확인하지 않는다"}],
                    "unresolved": [], "question_complete": False,
                    "missing_reason": "실제 사용 경험의 근거가 없다"})
        result = self.ask(reviewer=reviewer)
        reviewer.assert_called_once()
        self.assertEqual(result["status"], "unanswered")
        self.assertEqual(result["claims"], [])
        self.assertNotIn("내 글은 Claude Code를 소개한다.", rag.render_answer(result))
        self.assertEqual(json.loads(self.paths["runs_path"].read_text())["claims"], [])

    def test_grounding_review_api_failure_never_returns_draft_as_success(self):
        result = self.ask(reviewer=Mock(side_effect=rag.GenerationError("근거 검토 연결 실패")))
        self.assertEqual(result["status"], "generation_error")
        self.assertEqual(result["claims"], [])
        self.assertFalse(result["generated"])

    def test_pipeline_preserves_first_person_context_for_review(self):
        text = "제가 사용해본 방법은 Pen.dev + Claude Code 디자인 시스템 만드는 방법입니다."
        reviewer = Mock(side_effect=supported_review)
        result = self.ask(rows=[source(text=text)], reviewer=reviewer)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(reviewer.call_args.args[0]["sources"][0]["excerpt"], text)
        self.assertEqual(reviewer.call_args.args[0]["sources"][0]["corpus"], "own")
        self.assertEqual(reviewer.call_args.args[0]["sources"][0]["author_role"], "user")


class GroundingReviewTests(unittest.TestCase):
    def setUp(self):
        self.context = rag.prepare_context("내 글과 참고 글에서 공통 사용한 도구?", [source()])

    def rejected_review(self, context):
        result = supported_review(context)
        result["claims"][0].update(supported=False, reason="own 근거만 있고 reference의 사용 경험은 없다")
        result.update(question_complete=False, missing_reason="참고 작성자의 실제 사용 근거가 없다")
        return result

    def test_own_only_quote_cannot_survive_common_use_review(self):
        value = answer()
        value["claims"][0]["text"] = "내 글과 참고 글에서 공통으로 사용한 도구는 Claude Code이다."
        draft = rag.validate_answer(value, self.context)
        result = rag.review_answer(draft, self.context["question"], self.rejected_review, context=self.context)
        self.assertEqual(result["claims"], [])
        self.assertEqual(result["status"], "unanswered")
        self.assertIn("참고 작성자의 실제 사용 근거가 없다", result["unresolved"])

    def test_can_do_reference_quote_does_not_prove_actual_work(self):
        row = source(text="frontend-design은 실제 서비스용 UI 코드를 만들어줍니다.")
        row["corpus"] = "reference"
        context = rag.prepare_context("참고 작성자가 실제 수행한 작업?", [row])
        value = answer(quote=row["text"])
        value["claims"][0]["text"] = "참고 작성자는 실제 서비스용 UI 코드를 만들었다."
        reviewer = Mock(return_value={"claims": [{"index": 0, "supported": False,
                         "reason": "기능 설명은 작성자가 작업했다는 증거가 아니다"}],
                         "unresolved": [], "question_complete": False,
                         "missing_reason": "실제 수행 경험이 원문에 없다"})
        result = rag.review_answer(rag.validate_answer(value, context), context["question"], reviewer, context=context)
        self.assertEqual(result["claims"], [])
        sent = reviewer.call_args.args[0]
        self.assertEqual(sent["claims"][0]["cited_excerpts"][0]["corpus"], "reference")
        self.assertEqual(sent["sources"][0]["author_role"], "reference_author")

    def test_review_keeps_valid_claim_and_removes_unasked_unresolved(self):
        value = answer()
        value["unresolved"] = ["어느 국가에서 실행되는지는 모름"]
        verdict = {"claims": [{"index": 0, "supported": True, "reason": "도구명 소개 명시"}],
                   "unresolved": [{"index": 0, "relevant": False, "reason": "질문에서 국가를 묻지 않음"}],
                   "question_complete": True, "missing_reason": ""}
        result = rag.review_answer(rag.validate_answer(value, self.context), "내가 소개한 도구?",
                                   Mock(return_value=verdict))
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["unresolved"], [])

    def test_review_fails_closed_on_missing_duplicate_or_wrong_boolean_verdict(self):
        draft = rag.validate_answer(answer(), self.context)
        valid = supported_review({"claims": [{"index": 0}], "unresolved": []})
        missing = {**valid, "claims": []}
        duplicate = {**valid, "claims": valid["claims"] * 2}
        wrong = {**valid, "claims": [{"index": 0, "supported": "true", "reason": "확인"}]}
        for verdict in (missing, duplicate, wrong):
            with self.subTest(verdict=verdict), self.assertRaises(rag.EvidenceError):
                rag.review_answer(draft, "질문", Mock(return_value=verdict))

    def test_review_uses_separate_structured_request_and_precise_instructions(self):
        with patch.object(rag, "generate_openai", return_value={}) as request:
            rag.generate_grounding_review({"question": "질문", "claims": [], "unresolved": []})
        options = request.call_args.kwargs
        self.assertEqual(options["schema"], rag.review_schema())
        self.assertEqual(options["schema_name"], "rag_grounding_review")
        self.assertIn("양쪽 사용 근거", options["instructions"])
        self.assertIn("직접 사용", options["instructions"])

    def test_review_receives_first_person_author_context_from_provided_excerpt(self):
        text = "제가 사용해본 방법 중 가장 편리했던\nPen.dev + Claude Code 디자인 시스템 만드는 방법입니다."
        context = rag.prepare_context("내가 디자인 시스템 만들 때 쓴 도구?", [source(text=text)])
        draft = rag.validate_answer(answer(quote="Pen.dev + Claude Code"), context)
        reviewer = Mock(side_effect=supported_review)
        rag.review_answer(draft, context["question"], reviewer, context=context)
        sent = reviewer.call_args.args[0]
        self.assertEqual(sent["sources"], [{"source_id": "one", "corpus": "own", "excerpt": text,
                                            "truncated": False, "author_role": "user"}])
        self.assertEqual(sent["claims"][0]["cited_excerpts"][0]["quote"], "Pen.dev + Claude Code")
        self.assertIn("같은 사용자", rag.REVIEW_INSTRUCTIONS)
        self.assertIn("추가 도구가 없다는 완전성 증명은 요구하지 않는다", rag.REVIEW_INSTRUCTIONS)

    def test_review_context_never_restores_hidden_source_tail_or_uncited_documents(self):
        text = "Claude Code 소개." + "원문에만있는사용경험"
        context = rag.prepare_context("도구?", [source(text=text), source("uncited", "제가 실제 사용했다")],
                                      per_document=len("Claude Code 소개."))
        reviewer = Mock(side_effect=supported_review)
        rag.review_answer(rag.validate_answer(answer(), context), "도구?", reviewer, context=context)
        sent = reviewer.call_args.args[0]
        self.assertEqual(len(sent["sources"]), 1)
        self.assertTrue(sent["sources"][0]["truncated"])
        self.assertNotIn("원문에만있는사용경험", json.dumps(sent, ensure_ascii=False))
        self.assertNotIn("uncited", json.dumps(sent, ensure_ascii=False))

    def test_own_metadata_is_not_fabricated_first_person_use_context(self):
        context = rag.prepare_context("내가 사용한 도구?", [source(text="Claude Code라는 도구가 있다.")])
        reviewer = Mock(return_value={"claims": [{"index": 0, "supported": False,
                    "reason": "own 출처이지만 사용 경험은 원문에 없다"}], "unresolved": [],
                    "question_complete": False, "missing_reason": "원문이 실제 사용을 명시하지 않는다"})
        result = rag.review_answer(rag.validate_answer(answer(), context), context["question"], reviewer,
                                   context=context)
        self.assertEqual(result["status"], "unanswered")
        self.assertEqual(reviewer.call_args.args[0]["sources"][0]["excerpt"], "Claude Code라는 도구가 있다.")
        self.assertIn("메타데이터는 글의 소유자를 연결할 뿐", rag.REVIEW_INSTRUCTIONS)


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.context = rag.prepare_context("도구?", [source()])
        self.environment = patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-secret", "OPENAI_MODEL": "test-model"})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def response(self, result):
        return io.BytesIO(json.dumps(result).encode("utf-8"))

    def test_responses_request_is_structured_non_storing_and_fixed_endpoint(self):
        with patch.object(rag, "urlopen", return_value=self.response(api_result())) as request:
            self.assertEqual(rag.generate_openai(self.context), answer())
        sent = request.call_args.args[0]
        payload = json.loads(sent.data)
        self.assertEqual(sent.full_url, "https://api.openai.com/v1/responses")
        self.assertFalse(payload["store"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(payload["text"]["format"]["schema"], rag.response_schema())
        self.assertIn("비신뢰", payload["instructions"])

    def test_http_and_connection_failures_are_sanitized(self):
        errors = [HTTPError("https://private.example/key", 401, "secret-key", {}, None),
                  URLError("secret-key")]
        for error in errors:
            with patch.object(rag, "urlopen", side_effect=error), self.assertRaises(rag.GenerationError) as caught:
                rag.generate_openai(self.context)
            self.assertNotIn("secret-key", str(caught.exception))
            self.assertNotIn("private.example", str(caught.exception))

    def test_rejects_incomplete_refusal_and_unexpected_tool_outputs(self):
        incomplete = api_result()
        incomplete["status"] = "incomplete"
        refused = api_result()
        refused["output"][0]["content"] = [{"type": "refusal", "refusal": "private-details"}]
        tool = {"status": "completed", "output": [{"type": "web_search_call"}]}
        for result in (incomplete, refused, tool):
            with patch.object(rag, "urlopen", return_value=self.response(result)), self.assertRaises(rag.GenerationError):
                rag.generate_openai(self.context)

    def test_redirect_denied_and_empty_configuration_hides_values(self):
        with self.assertRaises(rag.GenerationError):
            rag._NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "OPENAI_MODEL": ""}), self.assertRaises(rag.GenerationError):
            rag.generate_openai(self.context)

    def test_local_env_is_literal_and_never_overrides_exported_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text('OPENAI_API_KEY="new-secret"\nOPENAI_MODEL="$(echo literal)"\nOTHER=ignored\n')
            with patch.dict(os.environ, {"OPENAI_API_KEY": "exported-secret"}, clear=True):
                rag.load_local_env(path)
                self.assertEqual(os.environ["OPENAI_API_KEY"], "exported-secret")
                self.assertEqual(os.environ["OPENAI_MODEL"], "$(echo literal)")
                self.assertNotIn("OTHER", os.environ)

    def test_duplicate_json_fields_rejected(self):
        with self.assertRaises(rag.GenerationError):
            rag._decode_json('{"claims": [], "claims": [], "unresolved": []}')


if __name__ == "__main__":
    unittest.main()
