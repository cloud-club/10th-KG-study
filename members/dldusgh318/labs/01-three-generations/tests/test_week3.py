import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent import NOT_FOUND, answer_from_chunks, assemble_context, verify_citations
from evaluate import _evaluation_queries, _recall, build_pool, render_pool, make_pool
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

    def test_shared_complete_group_becomes_each_query_gold(self):
        qrels = {
            "version": 2,
            "queries": [
                {"id": "R07", "query": "canonical", "judgment_group": "pair"},
                {"id": "R08", "query": "variant", "judgment_group": "pair"},
                {"id": "R99", "query": "pending", "judgment_group": "pending"},
            ],
            "judgment_groups": {
                "pair": {"status": "complete", "judgments": [
                    {"id": "a", "label": "relevant"}, {"id": "b", "label": "irrelevant"},
                ]},
                "pending": {"status": "unlabeled", "judgments": []},
            },
        }
        complete, skipped = _evaluation_queries(qrels, {"a", "b"})
        self.assertEqual([q["id"] for q in complete], ["R07", "R08"])
        self.assertEqual([q["gold"] for q in complete], [{"a"}, {"a"}])
        self.assertEqual(skipped, ["R99"])

    def test_pair_pool_unites_candidates_and_preserves_per_query_ranks(self):
        questions = [dict(id=q, query=q, gold_group="pair", labeling_rule="same") for q in ("R07", "R08")]
        corpus = {key: hit(key, 1) for key in "abc"}
        with patch('evaluate.search_bm25', side_effect=[[hit('a', 1)], [hit('c', 1)]]), patch('evaluate.search_vector', side_effect=[[hit('b', 1)], [hit('b', 1)]]):
            pools, groups = build_pool(questions, corpus)
        self.assertEqual([len(p['candidates']) for p in pools], [2, 2])
        self.assertEqual([r['id'] for r in groups['pair']['candidates']], ['a', 'b', 'c'])
        a = groups['pair']['candidates'][0]
        self.assertEqual(a['ranks']['R07']['bm25'], 1)
        self.assertNotIn('R08', a['ranks'])
        self.assertIn('미판정', render_pool(questions, groups))

    def test_pool_refuses_stale_database_text(self):
        q = dict(id='R01', query='q', labeling_rule='rule')
        with patch('evaluate.search_bm25', return_value=[hit('a', 1, 'stale')]), patch('evaluate.search_vector', return_value=[]):
            with self.assertRaises(ValueError):
                build_pool([q], {'a': hit('a', 1, 'current')})

    def test_existing_labels_are_not_overwritten(self):
        q = dict(id='R01', query='q', status='ready')
        with patch('evaluate.load_questions', return_value=[q]), patch('evaluate.POOL_FILE') as path, patch('evaluate.search_bm25') as search:
            path.exists.return_value = True
            with self.assertRaises(SystemExit):
                make_pool()
            search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
