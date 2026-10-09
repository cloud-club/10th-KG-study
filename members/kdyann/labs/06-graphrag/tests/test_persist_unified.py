import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from persist_unified import assign_post_numbers, display_name_for_entity


class PostNumberTests(unittest.TestCase):
    def test_existing_numbers_never_shift_and_new_ids_append(self):
        current = {"old-a": 1, "old-b": 3}
        docs = [{"source_id": "old-a", "corpus": "own", "published_at": "2026-10-01"},
                {"source_id": "new-b", "corpus": "own", "published_at": "2026-10-03"},
                {"source_id": "new-a", "corpus": "own", "published_at": "2026-10-02"},
                {"source_id": "ref", "corpus": "reference", "published_at": "2026-10-04"}]
        numbered = assign_post_numbers(current, docs)
        self.assertEqual(numbered, {"old-a": 1, "old-b": 3, "new-a": 4, "new-b": 5})
        self.assertEqual(assign_post_numbers(numbered, docs), numbered)

    def test_current_number_map_covers_fourteen_own_posts(self):
        lab = Path(__file__).resolve().parents[1]
        numbers = json.loads((lab / "own_post_numbers.json").read_text(encoding="utf-8"))
        self.assertEqual(len(numbers), 14)
        self.assertEqual(sorted(numbers.values()), list(range(1, 15)))

    def test_own_post_display_name_uses_stable_number(self):
        own = {"entity_type": "Post", "corpus": "own", "source_id": "own-1", "name": "long caption"}
        reference = {"entity_type": "Post", "corpus": "reference", "source_id": "ref-1", "name": "ref"}
        self.assertEqual(display_name_for_entity(own, {"own-1": "long caption"}, {"own-1": 1}), "게시글 1")
        self.assertEqual(display_name_for_entity(reference, {"ref-1": "짧은 설명"}, {}), "짧은 설명")


if __name__ == "__main__":
    unittest.main()
