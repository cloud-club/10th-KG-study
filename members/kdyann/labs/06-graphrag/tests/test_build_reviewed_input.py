import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from build_reviewed_input import ValidationError, build


class ReviewedInputTests(unittest.TestCase):
    def setUp(self):
        self.own = [{"id": f"own-{index}", "corpus": "own", "text": "내 글"} for index in range(13)]
        self.reference = [{"id": "ref-1", "text": "Python 학습 앱입니다.",
                           "published_at": "2026-10-05T00:00:00+00:00"}]
        self.review = {"ref-1": {"language": "ko", "review_note": "Python 학습 앱을 명시한다.", "facts": [{
            "subject_type": "Post", "subject_name": "ref-1", "predicate": "coversTopic",
            "object_type": "Topic", "object_name": "Python 학습 앱", "evidence": "Python 학습 앱"}]}}

    def test_build_reuses_own_facts_and_only_reviewed_reference(self):
        previous = [{"source_id": "own-1", "subject_type": "Post", "subject_name": "own-1",
                     "predicate": "coversTopic", "object_type": "Topic", "object_name": "내 글",
                     "evidence": "내 글", "start": 0, "end": 3}]
        documents, predictions = build(self.own, previous, self.reference, self.review)
        self.assertEqual(len(documents), 14)
        self.assertEqual(documents[-1]["corpus"], "reference")
        self.assertEqual(predictions[1]["facts"][0]["object_name"], "내 글")
        self.assertEqual(predictions[-1]["facts"][0]["object_name"], "Python 학습 앱")

    def test_rejects_quote_not_in_caption(self):
        self.review["ref-1"]["facts"][0]["evidence"] = "근거 없음"
        with self.assertRaises(ValidationError):
            build(self.own, [], self.reference, self.review)

    def test_rejects_unreviewed_or_non_korean_english_reference(self):
        del self.review["ref-1"]["language"]
        with self.assertRaises(ValidationError):
            build(self.own, [], self.reference, self.review)
        self.review["ref-1"]["language"] = "pt"
        with self.assertRaises(ValidationError):
            build(self.own, [], self.reference, self.review)
        self.review["ref-1"]["language"] = "ko"
        self.reference[0]["text"] = "हिन्दी भाषा के इस वाक्य में Python 학습 앱입니다."
        with self.assertRaises(ValidationError):
            build(self.own, [], self.reference, self.review)

    def test_accepts_new_own_post_with_reviewed_quote(self):
        latest = [{"id": "own-14", "text": "#야구 새 게시물"}]
        additions = {"own-14": {"review_note": "태그 확인", "facts": [{
            "subject_type": "Post", "subject_name": "own-14", "predicate": "coversTopic",
            "object_type": "Topic", "object_name": "야구", "evidence": "#야구"}]}}
        documents, predictions = build(self.own, [], self.reference, self.review, latest, additions)
        self.assertEqual(len([doc for doc in documents if doc["corpus"] == "own"]), 14)
        self.assertEqual(predictions[13]["facts"][0]["object_name"], "야구")

    def test_adds_grounded_topic_to_existing_own_post_without_duplicate_document(self):
        additions = {"own-1": {"review_note": "본문 확인", "facts": [{
            "subject_type": "Post", "subject_name": "own-1", "predicate": "coversTopic",
            "object_type": "Topic", "object_name": "내 글", "evidence": "내 글"}]}}
        documents, predictions = build(self.own, [], self.reference, self.review, [], additions)
        self.assertEqual(len(documents), 14)
        self.assertEqual([doc["id"] for doc in documents].count("own-1"), 1)
        self.assertEqual(predictions[1]["facts"][0]["object_name"], "내 글")


if __name__ == "__main__":
    unittest.main()
