"""네트워크 없이 수집·선정·근거 보존과 실패 시 저장 동작을 검증한다."""

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import fetch_topic_instagram as topics
import propose_content as content

NOW = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)
ENV = {"INSTAGRAM_API_VERSION": "v25.0", "FACEBOOK_INSTAGRAM_USER_ID": "100",
       "FACEBOOK_ACCESS_TOKEN": "synthetic-secret"}


def document(identifier="1", age=1, metrics=None):
    return {"id": identifier, "text": "개발 습관 #코딩", "permalink": f"https://www.instagram.com/p/{identifier}/",
            "published_at": (NOW - timedelta(days=age)).isoformat(), "metrics": metrics or {},
            "discovery": [{"hashtag": "코딩", "edge": "recent_media"}]}


class TopicTests(unittest.TestCase):
    def test_both_edges_dedup_and_all_topics_preserved(self):
        pages = [{"data": [{"id": "200"}]}, {"data": [{"id": "1", "caption": "코딩", "like_count": 0}]},
                 {"data": [{"id": "1", "comments_count": 2}]}, {"data": [{"id": "201"}]},
                 {"data": [{"id": "1"}]}, {"data": [{"id": "2", "caption": "AI"}]}]
        with patch.object(topics, "_request_json", side_effect=pages) as request:
            rows = topics.fetch_topics("https://graph.facebook.com/v25.0", "100", "fake", ["코딩", "AI"], 5)
        self.assertEqual(request.call_count, 6)
        self.assertTrue(request.call_args_list[1].args[0].endswith("/200/top_media"))
        self.assertTrue(request.call_args_list[2].args[0].endswith("/200/recent_media"))
        self.assertEqual(request.call_args_list[1].args[2]["user_id"], "100")
        self.assertEqual(request.call_args_list[1].args[2]["limit"], 5)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]["discovery"]), 3)
        self.assertEqual(rows[0]["media"]["like_count"], 0)
        self.assertEqual(rows[0]["media"]["comments_count"], 2)

    def test_partial_metrics_remain_missing_and_invalid_counts_ignored(self):
        row = {"media": {"id": "1", "caption": " #AI test", "comments_count": 4,
                         "like_count": None}, "discovery": []}
        self.assertEqual(topics.normalize_topic(row, "now")["metrics"], {"comments": 4})
        for bad in (True, -1, float("nan"), float("inf"), "100"):
            row["media"]["like_count"] = bad
            self.assertNotIn("likes", topics.normalize_topic(row, "now")["metrics"])

    def test_selection_excludes_unknown_future_old_and_bad_source(self):
        rows = [document("1", metrics={"likes": 1000}), document("old", 8, {"likes": 1000}),
                document("future", -1, {"likes": 1000}), document("unknown", metrics={"likes": 1000})]
        rows[-1]["published_at"] = None
        bad = document("bad", metrics={"likes": 100000})
        bad["permalink"] = "https://evil.example/p/x"
        rows.append(bad)
        selected = topics.select_documents(rows, NOW, 3, 7)
        self.assertEqual([row["id"] for row in selected], ["1"])
        self.assertIsNone(selected[0]["selection"]["observed_comments"])
        self.assertEqual(selected[0]["selection"], {"method": "likes_comments_rrf", "score": 1 / 61,
                         "k": 60, "likes_rank": 1, "comments_rank": None, "min_age_hours": 24,
                         "min_likes": 1000, "max_age_days": 7, "observed_likes": 1000,
                         "observed_comments": None})
        self.assertEqual(topics.select_documents([], NOW, 3, 7), [])

    def test_numeric_timestamp_and_only_requested_ranking_signals(self):
        rows = [document("a", 1, {"likes": 1200, "comments": 4}),
                document("b", 2, {"likes": 1000, "comments": 1})]
        rows[0]["published_at"] = (NOW - timedelta(days=1)).timestamp()
        before = topics.select_documents(rows, NOW, 3, 7)
        rows[1].update({"text": "my app ideal feature", "app_relevance": 999999, "views": 99999999})
        rows[1]["metrics"]["views"] = 99999999
        self.assertEqual(before[0]["id"], "a")
        self.assertEqual([row["id"] for row in before],
                         [row["id"] for row in topics.select_documents(rows, NOW, 3, 7)])

    def test_selection_age_and_like_boundaries_are_inclusive(self):
        rows = [document("at24h", 1, {"likes": 1000}), document("at7d", 7, {"likes": 1000}),
                document("under1000", 2, {"likes": 999}), document("under24h", metrics={"likes": 9000}),
                document("over7d", metrics={"likes": 9000})]
        rows[3]["published_at"] = (NOW - timedelta(hours=23, minutes=59)).isoformat()
        rows[4]["published_at"] = (NOW - timedelta(days=7, seconds=1)).isoformat()
        self.assertEqual([row["id"] for row in topics.select_documents(rows, NOW, 3, 7)], ["at24h", "at7d"])
        self.assertEqual([row["id"] for row in topics.select_documents(rows, NOW, 3, 1)], ["at24h"])

    def test_comments_change_likes_order_without_recency_contribution(self):
        rows = [document("lowlikes", 1, {"likes": 1000, "comments": 400}),
                document("highlikes", 7, {"likes": 2000, "comments": 1}),
                document("mixed", 5, {"likes": 1500, "comments": 500}),
                document("unknownlikes", 2, {"comments": 999999})]
        selected = topics.select_documents(rows, NOW, 3, 7)
        self.assertEqual([row["id"] for row in selected], ["mixed", "highlikes", "lowlikes"])
        self.assertAlmostEqual(selected[0]["selection"]["score"], 1 / 62 + 1 / 61)
        self.assertEqual(selected[0]["selection"]["likes_rank"], 2)
        self.assertEqual(selected[0]["selection"]["comments_rank"], 1)
        rows[0]["published_at"], rows[1]["published_at"] = rows[1]["published_at"], rows[0]["published_at"]
        after = topics.select_documents(rows, NOW, 3, 7)
        self.assertEqual([row["id"] for row in selected], [row["id"] for row in after])
        self.assertEqual([row["selection"] for row in selected], [row["selection"] for row in after])

    def test_comment_ties_put_unknown_after_observed_without_filling_zero(self):
        rows = [document("missing", metrics={"likes": 1000}),
                document("zero", metrics={"likes": 1000, "comments": 0}),
                document("b", metrics={"likes": 1000, "comments": 4}),
                document("a", metrics={"likes": 1000, "comments": 4})]
        self.assertEqual([row["id"] for row in topics.select_documents(rows, NOW, 3, 7)], ["a", "b", "zero"])
        selected = topics.select_documents(rows[:2], NOW, 3, 7)
        self.assertEqual([row["id"] for row in selected], ["zero", "missing"])
        self.assertEqual(selected[0]["selection"]["observed_comments"], 0)
        self.assertIsNone(selected[1]["selection"]["observed_comments"])
        self.assertNotIn("comments", selected[1]["metrics"])
        self.assertIsNone(selected[1]["selection"]["comments_rank"])
        self.assertAlmostEqual(selected[1]["selection"]["score"], 1 / (60 + selected[1]["selection"]["likes_rank"]))

    def test_default_topics_and_selection_cap_ten(self):
        args = topics.parse_args([])
        self.assertEqual(args.hashtag, ["reels", "fyp", "coding", "AI", "개발"])
        self.assertEqual(args.count, 10)
        rows = [document(f"p{i:02d}", metrics={"likes": 1000 + i, "comments": i}) for i in range(12)]
        selected = topics.select_documents(rows, NOW, args.count, args.max_age_days)
        self.assertEqual(len(selected), 10)
        self.assertEqual(selected[0]["id"], "p11")
        self.assertEqual(selected[-1]["id"], "p02")
        for invalid in (0, 11):
            with self.subTest(count=invalid), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                topics.parse_args(["--count", str(invalid)])
            with self.assertRaises(ValueError):
                topics.select_documents(rows, NOW, invalid, 7)

    def test_invalid_likes_excluded_and_invalid_comments_remain_unknown(self):
        for bad in (None, True, False, -1, float("nan"), float("inf"), float("-inf"), "1000"):
            with self.subTest(value=bad):
                self.assertEqual(topics.select_documents([document(metrics={"likes": bad, "comments": 999999})],
                                                        NOW, 3, 7), [])
                rows = [document("invalid", metrics={"likes": 1000, "comments": bad}),
                        document("known", metrics={"likes": 1000, "comments": 0})]
                selected = topics.select_documents(rows, NOW, 3, 7)
                self.assertEqual([row["id"] for row in selected], ["known", "invalid"])
                self.assertIsNone(selected[-1]["selection"]["observed_comments"])
        for metrics in (None, [], "1000"):
            row = document()
            row["metrics"] = metrics
            self.assertEqual(topics.select_documents([row], NOW, 3, 7), [])

    def test_corpus_accumulates_and_updates_snapshot(self):
        previous = [document("1"), document("2")]
        latest = document("2", metrics={"comments": 4})
        latest["discovery"] = [{"hashtag": "AI", "edge": "top_media"}]
        merged = topics.merge_documents(previous, [latest, document("3")])
        self.assertEqual([row["id"] for row in merged], ["1", "2", "3"])
        self.assertEqual(len(merged[1]["discovery"]), 2)
        self.assertEqual(merged[1]["metrics"], {"comments": 4})

    def test_api_failure_preserves_all_previous_outputs_and_redacts(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = [Path(temp) / name for name in ("raw", "documents", "selected")]
            for path in paths:
                path.write_text("previous", encoding="utf-8")
            with patch.dict(os.environ, ENV, clear=True), patch.object(topics, "RAW_PATH", paths[0]), \
                    patch.object(topics, "DOCUMENTS_PATH", paths[1]), patch.object(topics, "SELECTED_PATH", paths[2]), \
                    patch.object(topics, "fetch_topics", side_effect=topics.ReferenceAPIError("safe failure")), \
                    contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(topics.main([]), 1)
            self.assertTrue(all(path.read_text() == "previous" for path in paths))
            self.assertNotIn(ENV["FACEBOOK_ACCESS_TOKEN"], output.getvalue())

    def test_linked_account_setup_does_not_require_instagram_id(self):
        env = {key: value for key, value in ENV.items() if key != "FACEBOOK_INSTAGRAM_USER_ID"}
        payload = {"data": [{"name": "My page", "id": "9", "instagram_business_account": {"id": "100"}}]}
        with patch.dict(os.environ, env, clear=True), patch.object(topics, "_request_json", return_value=payload) as request, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(topics.main(["--list-linked-accounts"]), 0)
        self.assertNotIn("access_token", request.call_args.args[2]["fields"])
        self.assertIn("100", output.getvalue())
        self.assertNotIn(ENV["FACEBOOK_ACCESS_TOKEN"], output.getvalue())


class ContentTests(unittest.TestCase):
    def test_prepare_context_accepts_ten_but_rejects_eleven_and_duplicate_ids(self):
        rows = [document(f"p{i}") for i in range(11)]
        context = content.prepare_context(rows[:10], [])
        self.assertEqual(len(context["selected_posts"]), 10)
        self.assertEqual([row["id"] for row in context["selected_posts"]], [f"p{i}" for i in range(10)])
        for invalid in (rows, [], [rows[0], rows[0]]):
            with self.assertRaises(content.ContentError):
                content.prepare_context(invalid, [])

    def test_output_source_attached_from_input_and_ids_exact(self):
        context = content.prepare_context([document()], [document("own")])
        idea = {"id": "1", **{field: "새 초안" for field in content.IDEA_FIELDS}}
        result = content.attach_sources({"ideas": [idea]}, context)
        self.assertEqual(result[0]["source"]["permalink"], document()["permalink"])
        self.assertEqual(result[0]["source"]["caption_excerpt"], document()["text"])
        self.assertEqual(result[0]["own_style_example_ids"], ["own"])
        for invalid in ({"ideas": [{**idea, "id": "wrong"}]}, {"ideas": [idea, idea]},
                        {"ideas": [{**idea, "hook": " "}]},
                        {"ideas": [{**idea, "source": "invented"}]}):
            with self.assertRaises(content.ContentError):
                content.attach_sources(invalid, context)

    def test_prepare_only_and_missing_key_do_not_fake_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            selected, prompt, ideas = [Path(temp) / name for name in ("selected", "prompt", "ideas")]
            topics.write_jsonl(selected, [document()])
            ideas.write_text("previous ideas", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch.object(content, "PROMPT_PATH", prompt), \
                    patch.object(content, "IDEAS_PATH", ideas), patch.object(content, "generate") as generate, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(content.main(["--selected", str(selected), "--own-documents", str(Path(temp) / "absent"), "--prepare-only"]), 0)
                self.assertEqual(content.main(["--selected", str(selected), "--own-documents", str(Path(temp) / "absent")]), 1)
            generate.assert_not_called()
            self.assertEqual(ideas.read_text(), "previous ideas")
            self.assertEqual(json.loads(prompt.read_text())["status"], "prepared_not_generated")

    def test_responses_payload_and_safe_error_and_redirect(self):
        context = content.prepare_context([document()], [])
        reply = {"status": "completed", "output": [{"content": [{"type": "output_text", "text": '{"ideas": []}'}]}]}
        with patch.object(content, "urlopen", return_value=io.StringIO(json.dumps(reply))) as opener:
            self.assertEqual(content.generate(context, "synthetic-key", "chosen-model"), {"ideas": []})
        request = opener.call_args.args[0]
        payload = json.loads(request.data)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["model"], "chosen-model")
        self.assertTrue(payload["text"]["format"]["strict"])
        for failure in (HTTPError("secret-url", 401, "synthetic-key", {}, io.BytesIO(b"synthetic-key")),
                        URLError("synthetic-key")):
            with patch.object(content, "urlopen", side_effect=failure), self.assertRaises(content.ContentError) as caught:
                content.generate(context, "synthetic-key", "chosen-model")
            self.assertNotIn("synthetic-key", str(caught.exception))
        with self.assertRaises(content.ContentError):
            content._NoRedirect().redirect_request(request, None, 302, "redirect", {}, "https://evil.example")

    def test_malformed_response_content_is_controlled_error(self):
        context = content.prepare_context([document()], [])
        malformed = [None, 7, {}, [{"type": "output_text", "text": None}], [None]]
        for parts in malformed:
            reply = {"status": "completed", "output": [{"content": parts}]}
            with self.subTest(parts=parts), patch.object(content, "urlopen", return_value=io.StringIO(json.dumps(reply))), \
                    self.assertRaises(content.ContentError):
                content.generate(context, "synthetic-key", "chosen-model")


if __name__ == "__main__":
    unittest.main()
