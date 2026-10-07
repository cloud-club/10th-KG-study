import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from language_policy import validate_reference_records


class LanguagePolicyTests(unittest.TestCase):
    def test_korean_english_with_code_and_hashtags_are_allowed(self):
        docs = [{"id": "a", "corpus": "reference", "reviewed_language": "ko",
                 "text": "Python 3 코드와 #개발 #AI 주제를 설명합니다."},
                {"id": "b", "corpus": "reference", "reviewed_language": "en",
                 "text": "Learn Python APIs with #coding and JSON examples."}]
        validate_reference_records(docs, [])

    def test_language_attestation_and_fact_text_are_checked_before_persistence(self):
        docs = [{"id": "a", "corpus": "reference", "text": "Python tools"}]
        with self.assertRaises(ValueError):
            validate_reference_records(docs, [])
        docs[0]["reviewed_language"] = "en"
        facts = [{"source_id": "a", "subject_name": "a", "object_name": "AI कानून और नियमन",
                  "evidence": "Python tools"}]
        with self.assertRaises(ValueError):
            validate_reference_records(docs, facts)

    def test_short_unsupported_label_and_single_foreign_letter_are_rejected(self):
        docs = [{"id": "a", "corpus": "reference", "reviewed_language": "en",
                 "text": "AI tools"}]
        facts = [{"source_id": "a", "subject_name": "a", "object_name": "AI खतरे",
                  "evidence": "AI tools"}]
        with self.assertRaises(ValueError):
            validate_reference_records(docs, facts)
        docs[0]["text"] = "Python é tools"
        with self.assertRaises(ValueError):
            validate_reference_records(docs, [])


if __name__ == "__main__":
    unittest.main()
