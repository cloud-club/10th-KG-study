import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *a, **k: None
sys.modules.setdefault("dotenv", dotenv_stub)


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclass가 `from __future__ import annotations`로 미룬 타입 힌트를 처리할 때
    # sys.modules[모듈명]이 이미 있어야 해서, exec 전에 등록해야 한다.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load_module("common", "src/common.py")
et = load_module("extract_triples", "src/extract_triples.py")


def page(page_id: str, title: str, source: str, content: str = "충분히 긴 본문") -> dict:
    return {"id": page_id, "page_id": page_id, "title": title, "source": source, "chunk_index": 0, "content": content}


class PeriodAndActivityTest(unittest.TestCase):
    def test_period_folder_with_subfolder_is_activity(self):
        period, activity, org = et.period_and_activity(
            "notion_2026_data/2026/2026 1학기/졸전/V-O api/file.md", "회원가입"
        )
        self.assertEqual((period, activity, org), ("2026 1학기", "졸전", None))

    def test_period_folder_direct_file_uses_title(self):
        period, activity, org = et.period_and_activity("notion_2026_data/2026/2026 1학기/AWS - IAM.md", "AWS - IAM")
        self.assertEqual((period, activity, org), ("2026 1학기", "AWS - IAM", None))

    def test_company_folder_becomes_organization_and_activity(self):
        period, activity, org = et.period_and_activity("notion_2026_data/2026/Naver/코테 준비.md", "코테 준비")
        self.assertEqual((period, activity, org), (None, "Naver 지원 준비", "Naver"))

    def test_deoksung_folder(self):
        period, activity, org = et.period_and_activity("notion_2026_data/덕성/강의 정보/파일.md", "05 조건문")
        self.assertEqual((period, activity, org), (None, "덕성 강의 정보", None))


class ParseStatusAndTypeTest(unittest.TestCase):
    def test_parses_status_and_splits_mixed_type_values(self):
        content = "Status: In progress\ntype: 대외, 프로젝트"
        status, kinds, scopes = et.parse_status_and_type(content)
        self.assertEqual(status, "In progress")
        self.assertEqual(kinds, ["프로젝트"])
        self.assertEqual(scopes, ["대외"])

    def test_unknown_type_value_is_dropped(self):
        _, kinds, scopes = et.parse_status_and_type("type: 돈 :)")
        self.assertEqual((kinds, scopes), ([], []))

    def test_no_fields_returns_none(self):
        self.assertEqual(et.parse_status_and_type("아무 내용"), (None, [], []))


class BuildGraphTest(unittest.TestCase):
    def test_dual_types_single_page_activity_with_status(self):
        groups = {
            (None, "git 정리", None): [page("p1", "git 정리", "x", "Status: Done\ntype: 개인")],
        }
        graph = et.build_graph(groups, {})

        entity = graph.entities["activity_git_정리"]
        self.assertCountEqual(entity.types, ["Activity", "Document"])
        statuses = [e for e in graph.edges if e.predicate == "status"]
        self.assertEqual(statuses[0].object_literal, "Done")

    def test_multi_document_activity_creates_separate_documents(self):
        groups = {
            ("2026 1학기", "링커스", None): [
                page("p1", "회원가입", "x"),
                page("p2", "로그인", "x"),
            ],
        }
        graph = et.build_graph(groups, {})

        self.assertNotIn("Document", graph.entities["activity_링커스"].types)
        doc_ids = {e.object_id for e in graph.edges if e.predicate == "hasDocument"}
        self.assertEqual(doc_ids, {"doc_p1", "doc_p2"})

    def test_organization_split_from_activity(self):
        groups = {(None, "Naver 지원 준비", "Naver"): [page("p1", "자기소개서", "x")]}
        graph = et.build_graph(groups, {})

        self.assertIn("org_Naver", graph.entities)
        related = [e for e in graph.edges if e.predicate == "relatedToOrganization"]
        self.assertEqual(related[0].object_id, "org_Naver")

    def test_same_activity_across_periods_merges_into_one_entity(self):
        groups = {
            ("2026 1학기", "git 정리", None): [page("p1", "git 정리", "x", "Status: In progress")],
            ("2026 Winter", "git 정리", None): [page("p2", "git 정리", "y", "Status: In progress")],
        }
        graph = et.build_graph(groups, {})

        entity = graph.entities["activity_git_정리"]
        self.assertEqual(entity.types.count("Document"), 1)  # 중복 타입 버그 회귀 테스트
        periods = {e.object_id for e in graph.edges if e.predicate == "occursInPeriod"}
        self.assertEqual(periods, {"period_2026_1학기", "period_2026_Winter"})


class WriteTurtleTest(unittest.TestCase):
    def test_writes_valid_looking_triples(self, tmp_path=Path("/tmp/kg_lab_test.ttl")):
        groups = {(None, "Naver 지원 준비", "Naver"): [page("p1", "자기소개서", "x")]}
        graph = et.build_graph(groups, {"Naver 지원 준비": "이력서 작성"})
        et.write_turtle(graph, tmp_path)

        text = tmp_path.read_text(encoding="utf-8")
        self.assertIn(':org_Naver a :Organization ; schema:name "Naver" .', text)
        self.assertIn('schema:about "이력서 작성"', text)


if __name__ == "__main__":
    unittest.main()
