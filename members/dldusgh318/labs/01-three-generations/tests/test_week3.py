import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent import NOT_FOUND, answer_from_chunks, assemble_context, verify_citations
from evaluate import _recall
from hybrid_search import reciprocal_rank_fusion


def hit(chunk_id, rank, text=None):
    return {
        "id": chunk_id, "rank": rank, "score": 999,
        "title": chunk_id, "source": "test", "heading": "", "text": text or chunk_id,
    }


class RRFTest(unittest.TestCase):
    def test_uses_rank_and_keeps_one_sided_results(self):
        result = reciprocal_rank_fusion(
            [[hit("a", 1), hit("b", 2)], [hit("c", 1), hit("a", 2)]], k=60
        )
        self.assertEqual([row["id"] for row in result], ["a", "c", "b"])
        self.assertAlmostEqual(result[0]["rrf_score"], 1 / 61 + 1 / 62)
        self.assertIn("b", [row["id"] for row in result])

    def test_rejects_duplicate_id_in_one_ranking(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([[hit("a", 1), hit("a", 2)]])


class CitationTest(unittest.TestCase):
    def setUp(self):
        self.chunks = [hit("chunk-a", 1, "Redis는 메모리에 데이터를 저장한다."), hit("chunk-b", 2, "다른 기록")]

    def test_context_uses_short_numbers_but_mapping_keeps_ids(self):
        context, mapping = assemble_context(self.chunks)
        self.assertIn("[1]", context)
        self.assertNotIn("id: chunk-a", context)
        self.assertEqual(mapping[1]["id"], "chunk-a")

    def test_verifies_verbatim_substring(self):
        _, mapping = assemble_context(self.chunks)
        citations = verify_citations(
            {"citations": [{"source": 1, "snippet": "메모리에 데이터를 저장"}, {"source": 2, "snippet": "없는 문장"}]},
            mapping,
        )
        self.assertTrue(citations[0]["valid"])
        self.assertFalse(citations[1]["valid"])

    def test_answer_marks_invalid_citation(self):
        def fake_generator(_question, _context):
            return {"answer": "답", "citations": [{"source": 1, "snippet": "환각"}], "grounded": True}

        result = answer_from_chunks("질문", self.chunks, generator=fake_generator)
        self.assertFalse(result["citation_verified"])

    def test_no_data_answer_can_have_no_citation(self):
        def fake_generator(_question, _context):
            return {"answer": NOT_FOUND, "citations": [], "grounded": False}

        result = answer_from_chunks("질문", self.chunks, generator=fake_generator)
        self.assertTrue(result["citation_verified"])


class EvaluationTest(unittest.TestCase):
    def test_recall_uses_all_gold_chunks_as_denominator(self):
        self.assertEqual(_recall(["a", "x", "b"], {"a", "b", "c", "d"}, 3), 0.5)


if __name__ == "__main__":
    unittest.main()
