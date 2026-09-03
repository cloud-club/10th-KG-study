"""build_dashboard / dashboard_llm 의 순수 함수 테스트. 실행: python3 -m unittest discover -s scripts"""
from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import os
from unittest import mock

import build_dashboard as bd  # noqa: E402
import dashboard_llm as llm  # noqa: E402


class FrontmatterTests(unittest.TestCase):
    def test_parses_scalars_inline_list_and_block_list(self):
        text = "---\ntitle: RDF 기초\ndate: 2026-09-03\ntags: [RDF, sparql]\nrefs:\n  - a\n  - b\n---\n# 본문\n"
        meta, body = bd.parse_frontmatter(text)
        self.assertEqual(meta["title"], "RDF 기초")
        self.assertEqual(meta["tags"], ["RDF", "sparql"])
        self.assertEqual(meta["refs"], ["a", "b"])
        self.assertEqual(body, "# 본문\n")

    def test_returns_empty_meta_without_frontmatter(self):
        meta, body = bd.parse_frontmatter("# 제목\n내용")
        self.assertEqual(meta, {})
        self.assertEqual(body, "# 제목\n내용")


class MarkdownTests(unittest.TestCase):
    def test_first_heading_and_placeholder_is_ignored(self):
        self.assertEqual(bd.first_heading("intro\n# 01. 데이터 모델\n## 하위"), "01. 데이터 모델")
        self.assertEqual(bd.clean_title("NN. 주제"), "")

    def test_section_text_joins_paragraph_and_skips_code_and_quotes(self):
        body = "## 한 줄 요약\n> 인용\n첫 줄\n둘째 줄\n```py\nx=1\n```\n## 다음\n무시"
        self.assertEqual(bd.section_text(body, "한 줄 요약"), "첫 줄 둘째 줄")

    def test_section_text_drops_template_placeholder(self):
        body = "## 한 줄 요약\n\n이 주제를 한 문장으로 정리합니다.\n"
        self.assertEqual(bd.section_text(body, "한 줄 요약"), "")

    def test_humanize_strips_number_prefix(self):
        self.assertEqual(bd.humanize("01-data-model"), "data model")

    def test_normalize_tags_lowercases_and_dedupes(self):
        self.assertEqual(bd.normalize_tags(["RDF", "#rdf", " SPARQL ", ""]), ["rdf", "sparql"])
        self.assertEqual(bd.normalize_tags("neo4j"), ["neo4j"])
        self.assertEqual(bd.normalize_tags(None), [])


class ReadingsTests(unittest.TestCase):
    REPO = {"url": "https://github.com/x/y", "branch": "main"}

    def test_parse_reading_line_markdown_link_with_note(self):
        item = bd.parse_reading_line("[DPR](https://arxiv.org/abs/2004.04906) — dense 검색의 시작")
        self.assertEqual(item, {"title": "DPR", "url": "https://arxiv.org/abs/2004.04906", "note": "dense 검색의 시작"})

    def test_parse_reading_line_bare_url_gets_host_label(self):
        item = bd.parse_reading_line("https://www.anthropic.com/news/contextual-retrieval : 맥락 붙이기")
        self.assertEqual(item["title"], "anthropic.com/news/contextual-retrieval")
        self.assertEqual(item["url"], "https://www.anthropic.com/news/contextual-retrieval")
        self.assertEqual(item["note"], "맥락 붙이기")

    def test_parse_reading_line_plain_text_book(self):
        item = bd.parse_reading_line("『AI 에이전트 엔지니어링』 (한빛미디어)")
        self.assertEqual(item, {"title": "『AI 에이전트 엔지니어링』 (한빛미디어)", "url": "", "note": ""})

    def test_parse_readings_groups_by_week_heading(self):
        text = (
            "# 읽을거리\n- 주차 밖 자료\n\n## 1주차 · RAG 기초\n- [A](https://a.com) — 메모\n1. https://b.com\n"
            "```\n- 코드블록 안은 무시\n```\n### Week 2\n* [C](https://c.com)\n## 정리\n- 다른 제목 아래\n"
        )
        with mock.patch.object(bd, "read_text", return_value=text):
            items = bd.parse_readings(bd.ROOT / "members/kim/readings.md", "kim", self.REPO)
        self.assertEqual([(i["week"], i["title"]) for i in items],
                         [(None, "주차 밖 자료"), (1, "A"), (1, "b.com"), (2, "C"), (None, "다른 제목 아래")])
        self.assertEqual(items[1]["label"], "RAG 기초")
        self.assertEqual(items[1]["member"], "kim")
        self.assertTrue(items[1]["source_url"].endswith("members/kim/readings.md"))

    def test_build_readings_merges_members_latest_week_first(self):
        def reading(member, week, title, label=""):
            return {"week": week, "label": label, "title": title, "url": "", "note": "", "member": member, "source_url": ""}
        members = [
            {"readings": [reading("kim", 1, "a", "RAG"), reading("kim", 2, "b")]},
            {"readings": [reading("lee", 1, "c"), reading("lee", None, "d")]},
        ]
        weeks = bd.build_readings(members)
        self.assertEqual([w["week"] for w in weeks], [2, 1, None])
        self.assertEqual(weeks[1]["label"], "RAG")
        self.assertEqual(weeks[1]["members"], ["kim", "lee"])
        self.assertEqual([i["title"] for i in weeks[1]["items"]], ["a", "c"])
        self.assertNotIn("week", weeks[1]["items"][0])

    def test_classify_commit_marks_readings_file(self):
        self.assertEqual(bd.classify_commit(["members/kim/readings.md"]), "reading")
        self.assertEqual(bd.classify_commit(["members/kim/readings.md", "members/kim/notes/01.md"]), "note")


class ProgressTests(unittest.TestCase):
    def test_xp_and_level(self):
        p = bd.progress(n_notes=2, n_labs=1, n_commits=4)
        self.assertEqual(p["xp"], 2 * 40 + 80 + 4 * 5)
        self.assertEqual(p["level"], 2)
        self.assertEqual(p["xp_in_level"], 80)

    def test_streak_counts_back_from_today_or_yesterday(self):
        today = dt.date(2026, 9, 5)
        self.assertEqual(bd.current_streak(["2026-09-05", "2026-09-04", "2026-09-02"], today), 2)
        self.assertEqual(bd.current_streak(["2026-09-04", "2026-09-03"], today), 2)
        self.assertEqual(bd.current_streak(["2026-09-01"], today), 0)
        self.assertEqual(bd.current_streak(["bad-date"], today), 0)

    def test_heatmap_has_fixed_length_and_counts(self):
        today = dt.date(2026, 9, 5)
        cells = bd.build_heatmap(["2026-09-05", "2026-09-05", "2026-01-01"], today)
        self.assertEqual(len(cells), bd.HEATMAP_DAYS)
        self.assertEqual(cells[-1], {"date": "2026-09-05", "count": 2})
        self.assertEqual(cells[0]["date"], "2026-06-14")


def make_member(**overrides) -> dict:
    base = {
        "id": "sehyun", "name": "sehyun", "intro": "", "title": "", "summary": "", "highlights": [],
        "llm": False, "streak": 0, "last_active": "", "tags": [],
        "counts": {"notes": 0, "labs": 0, "commits": 0}, "notes": [], "labs": [], "_commits": [],
    }
    base.update(overrides)
    return base


class GraphTests(unittest.TestCase):
    def test_links_member_items_and_shared_topics(self):
        a = make_member(id="a", name="a", notes=[{"kind": "note", "id": "a/notes/01", "title": "n", "tags": ["rdf"], "url": ""}])
        b = make_member(id="b", name="b", labs=[{"kind": "lab", "id": "b/labs/01", "title": "l", "tags": ["rdf", "neo4j"], "url": ""}])
        for m in (a, b):
            m["avatar"] = ""
        graph = bd.build_graph([a, b])
        ids = {n["id"] for n in graph["nodes"]}
        self.assertEqual(ids, {"m:a", "m:b", "n:a/notes/01", "l:b/labs/01", "t:rdf", "t:neo4j"})
        self.assertEqual(len(graph["links"]), 5)


class CommitTests(unittest.TestCase):
    RAW = (
        "\x1eaaa111\x1f2026-09-02\x1fSEHYUN PARK\x1f1+sese2204@users.noreply.github.com\x1ffeat: parser\n\n"
        "members/sese2204/labs/01-parser/src/main.py\nmembers/sese2204/labs/01-parser/README.md\n"
        "\x1ebbb222\x1f2026-09-01\x1fWoongbi\x1fkungbi@example.com\x1ffeat: agent\n\nshared/cloudclub-agent/app.py\n"
        "\x1eccc333\x1f2026-09-01\x1fsehyun\x1fx@y.com\x1fstyle: dashboard\n\ndashboard/style.css\nREADME.md\n"
    )

    def test_parse_git_log_reads_records_and_files(self):
        commits = bd.parse_git_log(self.RAW)
        self.assertEqual([c["sha"] for c in commits], ["aaa111", "bbb222", "ccc333"])
        self.assertEqual(commits[0]["files"][0], "members/sese2204/labs/01-parser/src/main.py")
        self.assertEqual(commits[1]["email"], "kungbi@example.com")

    def test_study_files_excludes_infra(self):
        self.assertEqual(bd.study_files(["dashboard/app.js", "README.md", "shared/x.py", ".github/w.yml",
                                         "members/a/labs/.gitkeep"]), ["shared/x.py"])

    def test_classify_commit_priority(self):
        self.assertEqual(bd.classify_commit(["members/a/labs/01/src/x.py", "members/a/notes/01.md"]), "lab")
        self.assertEqual(bd.classify_commit(["members/a/notes/01.md"]), "note")
        self.assertEqual(bd.classify_commit(["shared/agent/app.py"]), "shared")
        self.assertEqual(bd.classify_commit(["members/a/README.md"]), "commit")

    def test_attribute_by_member_path_then_noreply_email(self):
        repo = {"owner": "o", "name": "n"}
        by_path = {"sha": "1", "files": ["members/kungbi/notes/a.md"], "email": "x@y.com", "author": "someone"}
        self.assertEqual(bd.attribute_commit(by_path, {"kungbi", "sese2204"}, repo, {}), "kungbi")
        by_noreply = {"sha": "2", "files": ["shared/a.py"], "email": "99+sese2204@users.noreply.github.com", "author": "SEHYUN"}
        self.assertEqual(bd.attribute_commit(by_noreply, {"kungbi", "sese2204"}, repo, {}), "sese2204")

    def test_attribute_falls_back_to_cached_login_then_email_then_name(self):
        repo = {"owner": "o", "name": "n"}
        cache = {"author:3": "kungbi"}
        c = {"sha": "3", "files": ["shared/a.py"], "email": "whoever@x.com", "author": "Someone"}
        self.assertEqual(bd.attribute_commit(c, {"kungbi"}, repo, cache), "kungbi")
        with mock.patch.object(bd, "github_login", return_value=""):
            by_email = {"sha": "4", "files": ["shared/a.py"], "email": "kungbi@x.com", "author": "Someone"}
            self.assertEqual(bd.attribute_commit(by_email, {"kungbi"}, repo, {}), "kungbi")
            unknown = {"sha": "5", "files": ["shared/a.py"], "email": "z@x.com", "author": "Guest"}
            self.assertEqual(bd.attribute_commit(unknown, {"kungbi"}, repo, {}), "Guest")

    def test_collect_study_commits_drops_infra_only(self):
        with mock.patch.object(bd, "git_all_commits", return_value=bd.parse_git_log(self.RAW)), \
             mock.patch.object(bd, "github_login", return_value=""):
            commits = bd.collect_study_commits({"owner": "o", "name": "n"}, {"sese2204", "kungbi"}, {})
        self.assertEqual([(c["sha"], c["kind"], c["member"]) for c in commits],
                         [("aaa111", "lab", "sese2204"), ("bbb222", "shared", "kungbi")])


class FeedTests(unittest.TestCase):
    def test_commit_events_link_items_and_carry_diff(self):
        lab = {"kind": "lab", "id": "a/labs/01", "title": "파서", "date": "", "summary": "", "tags": ["nlp"],
               "url": "lab-url", "_path": "members/a/labs/01/"}
        m = make_member(id="a", labs=[lab], progress={"level": 1, "xp": 0}, folder_url="f")
        commits = [{"sha": "abc123456789xyz", "date": "2026-09-02", "message": "feat: parser", "kind": "lab",
                    "member": "a", "files": ["members/a/labs/01/src/main.py"]}]
        with mock.patch.object(bd, "commit_numstat", return_value={"files": 1, "additions": 5, "deletions": 1}), \
             mock.patch.object(bd, "commit_diff_excerpt", return_value="+print('hi')"):
            events = bd.build_feed_events(commits, [m], {"url": "https://gh/x"})
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e["id"], "commit:abc123456789")
        self.assertEqual(e["items"], [{"kind": "lab", "title": "파서", "url": "lab-url"}])
        self.assertEqual(e["tags"], ["nlp"])
        self.assertEqual(e["_diff"], "+print('hi')")
        self.assertEqual(e["url"], "https://gh/x/commit/abc123456789xyz")

    def test_milestones_sorted_before_commits_on_same_day(self):
        m = make_member(id="a", streak=3, last_active="2026-09-02", progress={"level": 2, "xp": 120}, folder_url="f")
        commits = [{"sha": "s" * 12, "date": "2026-09-02", "message": "x", "kind": "commit", "member": "a", "files": ["shared/a"]}]
        with mock.patch.object(bd, "commit_numstat", return_value={}), mock.patch.object(bd, "commit_diff_excerpt", return_value=""):
            kinds = [e["kind"] for e in bd.build_feed_events(commits, [m], {"url": "u"})]
        self.assertEqual(kinds, ["level", "streak", "commit"])

    def test_no_milestones_below_threshold(self):
        m = make_member(streak=2, progress={"level": 1, "xp": 10}, folder_url="f")
        self.assertEqual(bd.milestone_events([m]), [])

    def test_fallback_commentary_and_summary(self):
        e = {"kind": "shared", "member": "kungbi", "title": "feat: agent", "stats": {"files": 2, "additions": 10, "deletions": 3},
             "files": ["shared/agent/app.py", "shared/agent/README.md"]}
        self.assertIn("kungbi", llm.fallback_commentary(e))
        self.assertIn("공유 프로젝트", llm.fallback_commentary(e))
        self.assertEqual(llm.fallback_summary_line(e), "파일 2개 변경 (+10 / -3): app.py, README.md")

    def test_build_feed_without_key_uses_templates(self):
        events = [{"id": "commit:1", "date": "2026-09-01", "member": "a", "kind": "note", "title": "t", "url": "u",
                   "summary": "", "tags": ["rdf"], "items": [], "stats": None, "files": [], "_diff": ""}]
        feed, source = llm.build_feed(events, "", {})
        self.assertEqual(source, "fallback")
        self.assertEqual(feed[0]["id"], "commit:1")
        self.assertEqual(feed[0]["tags"], ["rdf"])
        self.assertNotIn("_diff", feed[0])
        self.assertEqual(llm.build_feed([], "", {}), ([], "empty"))

    def test_feed_texts_uses_per_event_cache_and_batches_new_ones(self):
        llm._state["model"] = "gpt-5-mini"
        cache = {"feed:gpt-5-mini:commit:old": {"text": "cached", "summary": "", "tags": []}}
        events = [
            {"id": "commit:old", "date": "d", "member": "a", "kind": "note", "title": "t", "url": "", "summary": "", "tags": [],
             "items": [], "stats": None, "files": [], "_diff": ""},
            {"id": "commit:new", "date": "d", "member": "a", "kind": "lab", "title": "t2", "url": "", "summary": "", "tags": [],
             "items": [], "stats": {"files": 1, "additions": 1, "deletions": 0}, "files": ["x.py"], "_diff": "+x"},
        ]
        fake = mock.Mock(return_value={"lines": [{"id": "commit:new", "text": "새 중계", "summary": "요약", "tags": ["NLP"]}]})
        with mock.patch.object(llm, "cached_call", fake):
            texts = llm.feed_texts(events, "key", cache)
        self.assertEqual(texts["commit:old"]["text"], "cached")
        self.assertEqual(texts["commit:new"], {"text": "새 중계", "summary": "요약", "tags": ["nlp"]})
        self.assertIn("feed:gpt-5-mini:commit:new", cache)
        prompt = fake.call_args[0][0]
        self.assertIn("commit:new", prompt)
        self.assertNotIn("commit:old", prompt)
        llm._state["model"] = None


class ModelFallbackTests(unittest.TestCase):
    def setUp(self):
        llm._state["model"] = None

    def test_candidate_models_put_env_override_first(self):
        with mock.patch.dict(os.environ, {"OPENAI_MODEL": "gpt-4o-mini"}):
            self.assertEqual(llm.candidate_models()[0], "gpt-4o-mini")
            self.assertEqual(len(llm.candidate_models()), len(llm.FALLBACK_MODELS))
        with mock.patch.dict(os.environ, {"OPENAI_MODEL": ""}):
            self.assertEqual(llm.candidate_models(), llm.FALLBACK_MODELS)

    def test_cached_call_moves_to_next_model_when_unavailable(self):
        tried = []

        def fake_call(prompt, api_key, model):
            tried.append(model)
            if model == "gpt-5-mini":
                raise llm.ModelUnavailable("model not found")
            return {"ok": model}

        cache = {}
        with mock.patch.dict(os.environ, {"OPENAI_MODEL": ""}), mock.patch.object(llm, "call_openai", fake_call):
            self.assertEqual(llm.cached_call("p", "key", cache), {"ok": "gpt-4.1-mini"})
            self.assertEqual(llm.resolved_model(), "gpt-4.1-mini")
            # 두 번째 호출부터는 확정된 모델만 쓴다
            llm.cached_call("q", "key", cache)
        self.assertEqual(tried, ["gpt-5-mini", "gpt-4.1-mini", "gpt-4.1-mini"])
        self.assertEqual(len(cache), 2)

    def test_cached_call_returns_none_when_all_models_fail(self):
        with mock.patch.dict(os.environ, {"OPENAI_MODEL": ""}), \
             mock.patch.object(llm, "call_openai", mock.Mock(side_effect=llm.ModelUnavailable("x"))):
            self.assertIsNone(llm.cached_call("p", "key", {}))

    def test_cache_hit_skips_network(self):
        cache = {llm.cache_key("gpt-5-mini", "p"): {"cached": True}}
        with mock.patch.dict(os.environ, {"OPENAI_MODEL": ""}), \
             mock.patch.object(llm, "call_openai", mock.Mock(side_effect=AssertionError("no network"))):
            self.assertEqual(llm.cached_call("p", "key", cache), {"cached": True})


class LlmTests(unittest.TestCase):
    def test_extract_json_handles_code_fences(self):
        self.assertEqual(llm.extract_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertIsNone(llm.extract_json("not json"))
        self.assertIsNone(llm.extract_json("[1, 2]"))

    def test_request_body_adds_reasoning_only_for_gpt5(self):
        self.assertIn("reasoning_effort", llm.request_body("gpt-5-mini", "p"))
        self.assertNotIn("reasoning_effort", llm.request_body("gpt-4o-mini", "p"))

    def test_apply_member_result_merges_tags_without_overriding(self):
        note = {"kind": "note", "id": "sehyun/notes/01", "title": "t", "date": "", "summary": "", "tags": ["rdf"], "url": ""}
        member = make_member(notes=[note], counts={"notes": 1, "labs": 0, "commits": 0})
        llm.apply_member_result(member, {
            "title": "트리플 견습생", "summary": "요약", "highlights": ["h1"],
            "items": {"sehyun/notes/01": {"tags": ["RDF", "sparql"], "one_liner": "한 줄"}},
        })
        self.assertEqual(member["title"], "트리플 견습생")
        self.assertTrue(member["llm"])
        self.assertEqual(note["tags"], ["rdf", "sparql"])
        self.assertEqual(note["summary"], "한 줄")
        self.assertEqual(member["tags"], ["rdf", "sparql"])

    def test_fallbacks_fill_empty_members(self):
        member = make_member()
        llm.apply_fallbacks([member])
        self.assertEqual(member["title"], "이제 막 입장한 탐험가")
        self.assertTrue(member["summary"])
        digest = llm.fallback_digest([member], {"members": 1, "notes": 0, "labs": 0, "commits": 1})
        self.assertIn("1명", digest)


if __name__ == "__main__":
    unittest.main()
