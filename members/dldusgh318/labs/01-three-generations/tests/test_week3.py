import io
import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent import DEFAULT_MODEL, NOT_FOUND, answer_from_chunks, assemble_context, call_openai, compare_normal_oracle, verify_citations
from evaluate import _evaluation_queries, _recall, build_pool, render_pool, make_pool
from failure_experiment import check_retrieval, load_cases
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
        context, mapping, trace = assemble_context(self.chunks)
        self.assertIn("[1]", context)
        self.assertNotIn("id: chunk-a", context)
        self.assertEqual(mapping[1]["id"], "chunk-a")
        self.assertEqual(trace["included_chunk_ids"], ["chunk-a", "chunk-b"])

    def test_verifies_verbatim_substring(self):
        _, mapping, _ = assemble_context(self.chunks)
        citations = verify_citations(
            {"citations": [{"source": 1, "snippet": "메모리에 데이터를 저장"}, {"source": 2, "snippet": "없는 문장"}]},
            mapping,
        )
        self.assertTrue(citations[0]["valid"])
        self.assertFalse(citations[1]["valid"])

    def test_rejects_empty_and_unknown_citations(self):
        _, mapping, _ = assemble_context(self.chunks)
        citations = verify_citations(
            {"citations": [{"source": 1, "snippet": ""}, {"source": 99, "snippet": "다른 기록"}]},
            mapping,
        )
        self.assertEqual([citation["valid"] for citation in citations], [False, False])

    def test_openai_request_uses_structured_output_without_storage(self):
        response = {
            "output": [{"content": [{"type": "output_text", "text": json.dumps({
                "answer": "답", "citations": [{"source": 1, "snippet": "근거"}], "grounded": True,
            }, ensure_ascii=False)}]}]
        }

        class FakeResponse(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        captured = {}

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data)
            captured["timeout"] = timeout
            return FakeResponse(json.dumps(response, ensure_ascii=False).encode())

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True), patch("agent.urlopen", side_effect=fake_urlopen):
            payload = call_openai("질문", "[1]\ntext: 근거")

        self.assertEqual(payload["answer"], "답")
        self.assertEqual(captured["body"]["model"], DEFAULT_MODEL)
        self.assertFalse(captured["body"]["store"])
        self.assertEqual(captured["body"]["text"]["format"]["type"], "json_schema")
        self.assertIn("Question:\n질문", captured["body"]["input"])

    def test_context_tracks_top_k_exclusion_and_truncation(self):
        chunks = [hit("a", 1, "12345"), hit("b", 2, "67890"), hit("c", 3, "last")]
        first_header_size = len("[1]\ntitle: a\nsource: test\ntext: ")
        context, mapping, trace = assemble_context(
            chunks, max_chunks=2, max_chars=first_header_size + 3,
        )
        self.assertEqual(mapping[1]["text"], "123")
        self.assertNotIn(2, mapping)
        self.assertEqual(len(context), first_header_size + 3)
        self.assertEqual(trace["truncated"], [{"id": "a", "original_chars": 5, "included_chars": 3}])
        self.assertEqual(trace["excluded"], [
            {"id": "c", "reason": "beyond_top_k"},
            {"id": "b", "reason": "context_budget"},
        ])

    def test_answer_marks_invalid_citation(self):
        def fake_generator(_question, _context):
            return {"answer": "답", "citations": [{"source": 1, "snippet": "환각"}], "grounded": True}

        result = answer_from_chunks("질문", self.chunks, generator=fake_generator)
        self.assertFalse(result["citation_verified"])
        self.assertEqual(result["semantic_correctness"], "not_evaluated")

    def test_no_data_answer_can_have_no_citation(self):
        def fake_generator(_question, _context):
            return {"answer": NOT_FOUND, "citations": [], "grounded": False}

        result = answer_from_chunks("질문", self.chunks, generator=fake_generator)
        self.assertTrue(result["citation_verified"])

    def test_normal_and_oracle_use_same_generation_and_verification_path(self):
        normal_chunks = [hit("normal", 1, "normal evidence")]
        oracle_chunk = hit("oracle", 1, "oracle evidence")
        seen_contexts = []

        def fake_generator(_question, context):
            seen_contexts.append(context)
            snippet = "normal evidence" if "normal evidence" in context else "oracle evidence"
            return {"answer": "답", "citations": [{"source": 1, "snippet": snippet}], "grounded": True}

        with patch("agent.hybrid_search", return_value=normal_chunks), patch("agent.load_chunks_by_id", return_value={"oracle": oracle_chunk}):
            result = compare_normal_oracle("질문", ["oracle"], generator=fake_generator)

        self.assertEqual(len(seen_contexts), 2)
        self.assertTrue(result["normal"]["citation_verified"])
        self.assertTrue(result["oracle"]["citation_verified"])
        self.assertEqual(result["shared_generation_path"], "answer_from_chunks")
        self.assertEqual(result["missing_oracle_from_normal"], ["oracle"])


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


class FailureExperimentTest(unittest.TestCase):
    def test_load_cases_rejects_unknown_gold_chunk(self):
        payload = {"cases": [{
            "id": "S01", "kind": "single-hop", "question": "질문",
            "expected": "기대 답", "gold_chunks": ["missing"],
        }]}
        with patch("failure_experiment.CASES") as cases_path, patch("failure_experiment.load_chunks_by_id", return_value={}):
            cases_path.exists.return_value = True
            cases_path.read_text.return_value = json.dumps(payload)
            with self.assertRaises(SystemExit):
                load_cases()

    def test_check_retrieval_reports_missing_gold_without_llm(self):
        case = {
            "id": "M01", "kind": "2-hop", "question": "질문",
            "expected": "기대 답", "gold_chunks": ["a", "b"],
        }
        with patch("failure_experiment.load_cases", return_value=[case]), \
             patch("failure_experiment.hybrid_search", return_value=[hit("a", 1)]), \
             patch("failure_experiment.RETRIEVAL_CHECK") as result_path:
            records = check_retrieval()

        self.assertEqual(records[0]["missing_gold_chunks"], ["b"])
        self.assertEqual(records[0]["retrieval_coverage"], 0.5)
        result_path.write_text.assert_called_once()


if __name__ == "__main__":
    unittest.main()
