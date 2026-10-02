"""wiki_backlog 의 순수 함수 테스트. 실행: python3 -m unittest discover -s scripts"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wiki_backlog as wb  # noqa: E402


class SourceFilterTests(unittest.TestCase):
    def test_source_scope_matches_claude_md_rule(self):
        yes = [
            "members/kim/notes/01-a.md", "members/kim/notes/week4/01-rdf.md", "members/kim/note/03.md",
            "members/kim/labs/01-x/README.md", "members/kim/labs/01-x/WEEK5_result.md",
            "members/kim/readings.md", "members/kim/README.md",
        ]
        no = [
            "members/kim/labs/01-x/src/a.py", "members/kim/labs/01-x/data/a.jsonl", "members/kim/presentation.html",
            "members/names.json", "members/kim/assets/a.png", "wiki/concepts/a.md",
            "members/ur2e/labs/01-worklog-search/dataset/vault/a.md",
        ]
        for p in yes:
            self.assertTrue(wb.is_source(p), p)
        for p in no:
            self.assertFalse(wb.is_source(p), p)
        self.assertEqual(wb.member_of("members/do-dop/notes/03-rag-loop.md"), "do-dop")


class NoteMapTests(unittest.TestCase):
    MAP = """# 지도

## 멤버별

### dldusgh318 (이연호) · main
- `notes/week2/01-grep-limits.md` 0세대 → [[grep-문자열-매칭]]
- `labs/01-three-generations/WEEK2.md` → [[검색의-세-세대]]
- `labs/01-three-generations/WEEK5_HANDOFF.md`, `WEEK5_result.md`, `data_sample/README.md` → [[LLM-트리플-추출]]

### sese2204 (박세현) · main (노트) + PR #6 미머지
- `notes/01-rag-history.md` → [[RAG-변천사]] · `notes/02-chunking.md` → [[청킹-전략]]
- `labs/01-kakao-ingest/README.md` (PR #6) → [[카카오톡-대화-내보내기-파싱]]

## 소재에서 뺀 것
- `members/*/README.md` 는 제외
"""

    def test_mapped_paths_restores_member_prefix_and_handles_multiple_per_line(self):
        mapped = wb.mapped_paths(self.MAP)
        self.assertEqual(mapped, {
            "members/dldusgh318/notes/week2/01-grep-limits.md",
            "members/dldusgh318/labs/01-three-generations/WEEK2.md",
            "members/dldusgh318/labs/01-three-generations/WEEK5_HANDOFF.md",
            "members/dldusgh318/*WEEK5_result.md",
            "members/dldusgh318/*data_sample/README.md",
            "members/sese2204/notes/01-rag-history.md",
            "members/sese2204/notes/02-chunking.md",
            "members/sese2204/labs/01-kakao-ingest/README.md",
        })

    def test_is_mapped_resolves_bare_names_by_suffix_within_member(self):
        mapped = wb.mapped_paths(self.MAP)
        self.assertTrue(wb.is_mapped("members/dldusgh318/labs/01-three-generations/WEEK5_result.md", mapped))
        self.assertTrue(wb.is_mapped("members/dldusgh318/labs/01-three-generations/data_sample/README.md", mapped))
        self.assertFalse(wb.is_mapped("members/sese2204/labs/x/WEEK5_result.md", mapped))
        self.assertFalse(wb.is_mapped("members/dldusgh318/labs/01-three-generations/WEEK5_queries.md", mapped))


class UnmappedTests(unittest.TestCase):
    def test_member_root_docs_are_skipped_but_lab_readmes_are_not(self):
        self.assertTrue(wb.MEMBER_ROOT_DOC_RE.match("members/kim/README.md"))
        self.assertTrue(wb.MEMBER_ROOT_DOC_RE.match("members/kim/readings.md"))
        self.assertIsNone(wb.MEMBER_ROOT_DOC_RE.match("members/kim/labs/01-x/README.md"))


class RenderTests(unittest.TestCase):
    def test_render_groups_by_member_and_lists_prs(self):
        report = {
            "base": "a5e4f87abc", "base_date": "2026-09-17", "head": "ddf52f6",
            "changed": [
                {"status": "A", "path": "members/kim/notes/04.md", "member": "kim", "words": 1200},
                {"status": "M", "path": "members/lee/labs/01/README.md", "member": "lee", "words": 300},
            ],
            "unmapped": ["members/kim/notes/04.md"],
            "prs": [{"number": 34, "title": "5주차", "branch": "e0ng/05", "updated": "2026-09-30",
                     "files": ["members/e0ng/notes/05-1.md"]}],
        }
        text = wb.render(report)
        self.assertIn("`a5e4f87` (2026-09-17) → `ddf52f6`", text)
        self.assertIn("## 바뀐 소재 (2건, 1,500 단어)", text)
        self.assertIn("### kim (1건)", text)
        self.assertIn("- `A` members/kim/notes/04.md (1,200 단어)", text)
        self.assertIn("### PR #34 · 5주차 (`e0ng/05`, 2026-09-30)", text)
        self.assertIn("- members/e0ng/notes/05-1.md", text)

    def test_render_without_base_says_everything_is_pending(self):
        text = wb.render({"base": "", "base_date": "", "head": "abc", "changed": [], "unmapped": [], "prs": []})
        self.assertIn("(없음 — 전체)", text)
        self.assertIn("- 없음", text)


if __name__ == "__main__":
    unittest.main()
