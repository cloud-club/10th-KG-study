"""build_dashboard / dashboard_llm 의 순수 함수 테스트. 실행: python3 -m unittest discover -s scripts"""
from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

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
