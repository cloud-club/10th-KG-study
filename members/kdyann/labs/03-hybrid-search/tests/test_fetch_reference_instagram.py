"""외부 네트워크·실제 토큰 없이 참고 계정 수집의 경계 조건을 검증한다."""

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import fetch_reference_instagram as collector


BASE = "https://graph.facebook.com/v24.0"
TOKEN = "synthetic-secret"


def discovery(items, next_url=None):
    media = {"data": items}
    if next_url:
        media["paging"] = {"next": next_url}
    return {"business_discovery": {"id": "200", "username": "reference", "media": media}}


class ReferenceCollectorTests(unittest.TestCase):
    def test_nested_pagination_caps_deduplicates_and_strips_tokens(self):
        next_url = BASE + "/200/media?after=cursor&access_token=" + TOKEN
        pages = [discovery([{"id": "1", "caption": "first"}], next_url),
                 {"data": [{"id": "1"}, {"id": "2", "caption": "second"}, {"id": "3"}]}]
        with patch.object(collector, "_request_json", side_effect=pages) as request:
            rows = collector.fetch_reference(BASE, "100", TOKEN, "reference", 2)
        self.assertEqual([row["media"]["id"] for row in rows], ["1", "2"])
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[1].args[0], BASE + "/200/media?after=cursor")
        fields = request.call_args_list[0].args[2]["fields"]
        self.assertEqual(fields, "business_discovery.username(reference){id,username,media.limit(2){"
                         + collector.MEDIA_FIELDS + "}}")
        self.assertNotIn("insights", fields)
        self.assertNotIn(TOKEN, json.dumps(rows))

    def test_bearer_only_request_shape(self):
        with patch.object(collector, "urlopen", return_value=io.StringIO('{"data": []}')) as opener:
            collector._request_json(BASE + "/100?access_token=" + TOKEN, TOKEN, {"fields": "id,username"})
        request = opener.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertNotIn(TOKEN, request.full_url)
        self.assertEqual(parse_qs(urlparse(request.full_url).query), {"fields": ["id,username"]})

    def test_enveloped_next_page_and_missing_media(self):
        next_url = BASE + "/200/media?after=next"
        with patch.object(collector, "_request_json", side_effect=[discovery([{"id": "1"}], next_url),
                         discovery([{"id": "2"}])]):
            rows = collector.fetch_reference(BASE, "100", TOKEN, "reference", 2)
        self.assertEqual(len(rows), 2)
        with patch.object(collector, "_request_json", return_value={"business_discovery": {
                "id": "200", "username": "reference"}}):
            with self.assertRaises(collector.ReferenceAPIError):
                collector.fetch_reference(BASE, "100", TOKEN, "reference", 2)

    def test_malformed_token_header_is_redacted(self):
        with patch.object(collector, "urlopen") as opener:
            with self.assertRaises(collector.ReferenceAPIError) as caught:
                collector._request_json(BASE, TOKEN + "\r\ninvalid")
        opener.assert_not_called()
        self.assertNotIn(TOKEN, str(caught.exception))

    def test_missing_metrics_not_zero_and_no_rates(self):
        row = {"media": {"id": "1", "caption": " #공부 hello", "like_count": 0},
               "username": "reference", "discovery": {"method": "business_discovery"}}
        document = collector.normalize_reference(row, "now")
        self.assertEqual(document["metrics"], {"likes": 0})
        self.assertTrue(all(value is None for value in document["rates"].values()))
        self.assertEqual(document["source_type"], "reference")
        self.assertEqual(document["hashtags"], ["공부"])
        row["media"]["caption"] = " "
        self.assertIsNone(collector.normalize_reference(row, "now"))

    def test_preflight_uses_facebook_user_permissions_and_ig_id(self):
        responses = [{"data": [{"permission": "instagram_basic", "status": "granted"},
                               {"permission": "pages_read_engagement", "status": "declined"}]},
                     {"id": "100", "username": "own_account"}]
        with patch.object(collector, "_request_json", side_effect=responses) as request:
            summary = collector.check_access(BASE, "100", TOKEN)
        self.assertEqual(summary["granted_permissions"], ["instagram_basic"])
        self.assertEqual(request.call_args_list[0].args[0], BASE + "/me/permissions")
        self.assertEqual(request.call_args_list[1].args[2], {"fields": "id,username"})
        self.assertNotIn(TOKEN, json.dumps(summary))

    def test_failure_leaves_previous_files_untouched(self):
        env = {"INSTAGRAM_API_VERSION": "v24.0", "FACEBOOK_INSTAGRAM_USER_ID": "100",
               "FACEBOOK_ACCESS_TOKEN": TOKEN}
        with tempfile.TemporaryDirectory() as temp:
            raw, processed = Path(temp) / "raw.jsonl", Path(temp) / "processed.jsonl"
            raw.write_text("previous", encoding="utf-8")
            with patch.dict(os.environ, env, clear=True), patch.object(collector, "DEFAULT_RAW", raw), \
                    patch.object(collector, "DEFAULT_PROCESSED", processed), \
                    patch.object(collector, "fetch_reference", side_effect=[[], collector.ReferenceAPIError("denied")]), \
                    contextlib.redirect_stderr(io.StringIO()):
                result = collector.main(["--username", "one", "--username", "two"])
            self.assertEqual(result, 1)
            self.assertEqual(raw.read_text(encoding="utf-8"), "previous")
            self.assertFalse(processed.exists())

    def test_own_token_is_not_used(self):
        env = {"INSTAGRAM_API_VERSION": "v24.0", "FACEBOOK_INSTAGRAM_USER_ID": "100",
               "INSTAGRAM_ACCESS_TOKEN": TOKEN}
        stderr = io.StringIO()
        with patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(stderr), \
                patch.object(collector, "_request_json") as request:
            self.assertEqual(collector.main(["--check-access"]), 1)
        request.assert_not_called()
        self.assertIn("FACEBOOK_ACCESS_TOKEN", stderr.getvalue())
        self.assertNotIn(TOKEN, stderr.getvalue())

    def test_repeated_cursor_fails_instead_of_hanging(self):
        next_url = BASE + "/200/media?after=same"
        with patch.object(collector, "_request_json", side_effect=[discovery([], next_url),
                         {"data": [], "paging": {"next": next_url}}]) as request:
            with self.assertRaises(collector.ReferenceAPIError):
                collector.fetch_reference(BASE, "100", TOKEN, "reference", 2)
        self.assertEqual(request.call_count, 2)

    def test_host_validation_and_redirects_do_not_leak_auth(self):
        for url in ["http://graph.facebook.com/x", "https://evil.example/x",
                    "https://graph.facebook.com.evil.example/x", "https://user@graph.facebook.com/x",
                    "https://graph.facebook.com:444/x", "https://graph.facebook.com/x#fragment"]:
            with self.subTest(url=url), self.assertRaises(collector.ReferenceAPIError):
                collector._safe_url(url)
        handler = collector._GraphRedirectHandler()
        with self.assertRaises(collector.ReferenceAPIError):
            handler.redirect_request(Request(BASE, headers={"Authorization": "Bearer " + TOKEN}),
                                     None, 302, "redirect", {}, "https://evil.example/x")

    def test_api_and_network_errors_redact_tokens(self):
        error_body = io.BytesIO(json.dumps({"error": {"message": TOKEN}}).encode())
        errors = [HTTPError(BASE + "?access_token=" + TOKEN, 403, TOKEN, {}, error_body),
                  URLError(TOKEN)]
        for error in errors:
            with self.subTest(error=type(error).__name__), patch.object(collector, "urlopen", side_effect=error):
                with self.assertRaises(collector.ReferenceAPIError) as caught:
                    collector._request_json(BASE, TOKEN)
                self.assertNotIn(TOKEN, str(caught.exception))
            if isinstance(error, HTTPError):
                error.close()


if __name__ == "__main__":
    unittest.main()
