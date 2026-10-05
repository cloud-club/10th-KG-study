import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "src" / "notion" / "parse_export.py"
SPEC = importlib.util.spec_from_file_location("parse_export", MODULE_PATH)
parse_export = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(parse_export)


class ParseNotionTest(unittest.TestCase):
    def test_markdown_export_becomes_stable_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "여행 계획 1234567890abcdef1234567890abcdef.md"
            path.write_text("# 제주도 여행\n\n숙소를 예약한다.\n\n민지와 함께 간다.", encoding="utf-8")

            first = parse_export.markdown_documents(path, root, chunk_size=20)
            second = parse_export.markdown_documents(path, root, chunk_size=20)

            self.assertEqual([item["id"] for item in first], [item["id"] for item in second])
            self.assertEqual(first[0]["page_id"], "1234567890abcdef1234567890abcdef")
            self.assertEqual(first[0]["title"], "여행 계획")
            self.assertEqual(first[0]["source"], path.name)
            self.assertTrue(all(len(item["content"]) <= 20 for item in first))

    def test_duplicate_page_title_is_removed_from_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "AWS - Lambda 1234567890abcdef1234567890abcdef.md"
            path.write_text("# AWS - Lambda\n\n이미지 처리", encoding="utf-8")

            documents = parse_export.markdown_documents(path, root, chunk_size=100)

            self.assertEqual(documents[0]["content"], "이미지 처리")

    def test_csv_is_only_included_when_requested(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "메모.csv").write_text("이름,상태\n검색 실습,완료\n", encoding="utf-8")

            self.assertEqual(parse_export.parse_export(root, 100, include_csv=False), [])
            documents = parse_export.parse_export(root, 100, include_csv=True)

            self.assertEqual(len(documents), 1)
            self.assertIn("이름: 검색 실습", documents[0]["content"])


if __name__ == "__main__":
    unittest.main()
