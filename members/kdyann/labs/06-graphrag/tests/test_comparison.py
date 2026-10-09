import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from compare_retrievers import compare_one, graph_context, is_aggregate_question
from evidence_generation import assemble_answer, prompt_input
from query_plan import route_question, planned_paths
from text2cypher import TEMPLATES, run_one, validate_generated
from rag_agent import EvidenceError


def post(identifier, corpus="own"):
    return {"id": identifier, "corpus": corpus, "text": f"{identifier} 주제를 설명합니다.",
            "permalink": "https://www.instagram.com/p/ABC/"}


class FakeSearch:
    def __init__(self):
        self.documents = [post("a"), post("b"), post("c"), post("outside")]
        self.by_id = {row["id"]: row for row in self.documents}

    def _ensure_indexed(self):
        pass

    def _bm25(self, *_args):
        return [self.by_id[key] for key in ("a", "b", "outside", "c")]

    def _vector(self, *_args):
        return [self.by_id[key] for key in ("a", "c", "outside", "b")]


class FakeGraph:
    def __init__(self):
        self.calls = []

    def query(self, cypher, **params):
        self.calls.append((cypher, params))
        if "RETURN count(DISTINCT p) AS count" in cypher:
            return [{"count": 3}]
        if "RETURN t.name AS topic, count(DISTINCT p) AS post_count" in cypher:
            return [{"topic": "야구", "post_count": 3}]
        if "curated_interest_area" in cypher:
            return [{"seed_id": "a", "other_id": "c", "seed_topic": "오픈소스 기여",
                     "other_topic": "Python 학습", "interest_area": "개발",
                     "path_type": "curated_interest_area", "seed_quote": "a 주제를",
                     "other_quote": "c 주제를"}]
        return []


class ComparisonTests(unittest.TestCase):
    def test_evidence_failure_is_not_reported_as_api_failure(self):
        with patch("compare_retrievers.generate_openai", side_effect=EvidenceError("인용 불일치")):
            result = compare_one({"id": "q", "query": "개발", "scope": "own"},
                                 FakeSearch(), FakeGraph(), {"a", "b", "c"},
                                 generate_answers=True)
        for arm in result["arms"].values():
            self.assertEqual(arm["generation_failure"]["error_code"], "evidence_error")

    def test_both_arms_select_evidence_ids_with_same_prompt(self):
        draft = {"claims": [{"text": "a 주제를 설명합니다.", "evidence_ids": ["E01"]}], "unresolved": []}
        with patch("compare_retrievers.generate_openai", return_value=draft) as model, \
             patch("compare_retrievers.review_answer", side_effect=lambda answer, *_args, **_kw: answer):
            result = compare_one({"id": "q", "query": "a 주제 설명", "scope": "own"},
                                 FakeSearch(), FakeGraph(), {"a", "b", "c"},
                                 generate_answers=True, capture_raw=True)
        self.assertEqual(model.call_count, 2)
        self.assertEqual(model.call_args_list[0].kwargs["instructions"],
                         model.call_args_list[1].kwargs["instructions"])
        for arm in result["arms"].values():
            self.assertEqual(arm["answer"]["claims"][0]["evidence"][0]["quote"],
                             "a 주제를 설명합니다.")
            self.assertIn("내 글 3개", arm["answer"]["scope_note"])

    def test_reviewer_receives_same_full_context_catalog_as_generator(self):
        draft = {"claims": [{"text": "a 주제", "evidence_ids": ["E01"]}], "unresolved": []}
        def run_review(answer, _query, reviewer, **_kwargs):
            reviewer({"claims": [], "unresolved": []})
            return answer
        with patch("compare_retrievers.generate_openai", side_effect=[draft, {}, draft, {}]) as model, \
             patch("compare_retrievers.review_answer", side_effect=run_review):
            compare_one({"id": "q", "query": "a 주제", "scope": "own"},
                        FakeSearch(), FakeGraph(), {"a", "b", "c"}, generate_answers=True)
        self.assertEqual(model.call_args_list[0].args[0]["evidence_catalog"],
                         model.call_args_list[1].args[0]["available_evidence_catalog"])
        self.assertEqual(model.call_args_list[2].args[0]["evidence_catalog"],
                         model.call_args_list[3].args[0]["available_evidence_catalog"])

    def test_reference_request_without_reference_context_abstains_in_both_arms(self):
        for query in ("내 글과 같은 관심 분야로 연결되는 참고 게시물을 찾아줘",
                      "내 글을 바탕으로 참고 글과 추천 주제를 알려줘"):
            with self.subTest(query=query), patch("compare_retrievers.generate_openai") as model:
                result = compare_one({"id": "q", "query": query, "scope": "all"},
                                     FakeSearch(), FakeGraph(), {"a", "b", "c"},
                                     generate_answers=True)
            model.assert_not_called()
            for arm in result["arms"].values():
                self.assertEqual(arm["answer"]["status"], "unanswered")
                self.assertEqual(arm["answer"]["answer_source"], "missing_reference_guard")

    def test_adhoc_count_question_is_routed_to_full_corpus_guard(self):
        self.assertTrue(is_aggregate_question("내 야구 게시물은 모두 몇 개야?"))
        self.assertTrue(is_aggregate_question("가장 많이 다룬 주제는?"))
        self.assertFalse(is_aggregate_question("내 디자인 도구는 뭐야?"))

    def test_v2_uses_only_shared_corpus_and_same_total_budget(self):
        result = compare_one({"id": "q", "query": "개발 분야", "scope": "own", "relevant_ids": ["c"]},
                             FakeSearch(), FakeGraph(), {"a", "b", "c"}, limit=3,
                             seed_count=1, per_document=30, total_chars=500)
        v1, v2 = result["arms"]["v1_hybrid"], result["arms"]["v2_graph"]
        self.assertNotIn("outside", v1["source_ids"] + v2["source_ids"])
        self.assertIn("c", v2["source_ids"])
        self.assertTrue(any(source["corpus"] == "graph" for source in v2["context"]["sources"]))
        self.assertLessEqual(v1["context_chars"], 500)
        self.assertLessEqual(v2["context_chars"], 500)
        self.assertGreaterEqual(v2["retrieval_ms"], v1["retrieval_ms"])

    def test_graph_context_only_reports_paths_between_selected_posts(self):
        paths = [{"seed_id": "a", "other_id": "c", "path_type": "shared_topic",
                  "seed_topic": "개발", "seed_quote": "a", "other_quote": "c"}]
        context = graph_context("q", [post("a")], paths, per_document=30, total_chars=100)
        self.assertEqual(len(context["sources"]), 1)

    def test_canonical_project_path_is_grounded_in_v2_context(self):
        path = {"other_id": "app", "entity_type": "Project", "entity_name": "스터디언",
                "relationship": "DESCRIBES_PROJECT", "other_quote": "스터디언이 출시되어",
                "path_type": "entity_fact"}
        row = {"id": "app", "corpus": "own", "text": "스터디언이 출시되어 App Store에 있어요",
               "permalink": "https://www.instagram.com/p/ABC/"}
        context = graph_context("앱 이름?", [row], [path], per_document=100, total_chars=1000)
        self.assertIn("Project '스터디언'", context["sources"][-1]["excerpt"])

    def test_aggregate_uses_full_graph_only_for_v2_and_skips_llm(self):
        with patch("compare_retrievers.generate_openai") as model:
            result = compare_one({"id": "count", "query": "내 게시물 모두 몇 개야?", "scope": "own",
                                  "category": "direct"}, FakeSearch(), FakeGraph(), {"a", "b", "c"},
                                 limit=3, seed_count=1, generate_answers=True)
        model.assert_not_called()
        self.assertEqual(result["plan"]["route"], "aggregate")
        self.assertEqual(result["arms"]["v1_hybrid"]["answer"]["status"], "unanswered")
        self.assertIn("3개", result["arms"]["v2_graph"]["answer"]["claims"][0]["text"])
        self.assertIsNone(result["arms"]["v2_graph"]["recall_at_k"])
        self.assertEqual(result["graph_aggregation"]["parameters"]["allowed_id_count"], 3)

    def test_plan_rejects_unknown_topic_and_unsupported_date_count(self):
        catalog = [{"topic": "야구", "area": "야구"}]
        self.assertEqual(route_question("축구 주제 게시물 몇 개?", catalog, {"야구"})["route"], "unsupported")
        self.assertEqual(route_question("지난달 야구 게시물 몇 개?", catalog, {"야구"})["route"], "unsupported")
        self.assertEqual(route_question("작년에 내 게시물 몇 개야?", catalog, {"야구"})["route"], "unsupported")
        self.assertEqual(route_question("참고 글 몇 개야?", catalog, {"야구"})["route"], "unsupported")
        self.assertEqual(route_question("내 축구 글 몇 개야?", catalog, {"야구"})["route"], "unsupported")
        self.assertEqual(route_question("내 게시물로 만들만한 주제 추천해줘", catalog, {"야구"})["route"], "recommendation")

    def test_top_topic_question_bypasses_unknown_topic_modifier_guard(self):
        catalog = [{"topic": "야구", "area": "야구"}]
        for query in ("현재 실습 데이터에서 내 게시물에 가장 많이 연결된 주제와 그 게시물 수는?",
                      "내 게시물에서 가장 많은 주제는 뭐야?",
                      "내 게시물에 제일 많이 붙은 주제를 알려줘"):
            with self.subTest(query=query):
                plan = route_question(query, catalog, {"야구"})
                self.assertEqual(plan["route"], "aggregate")
                self.assertEqual(plan["aggregate"], "top_topic")

    def test_topic_anchor_ignores_unrelated_high_ranked_baseball(self):
        catalog = [
            {"source_id": "baseball", "corpus": "own", "topic": "야구", "area": "야구", "quote": "야구"},
            {"source_id": "own-dev", "corpus": "own", "topic": "오픈소스 기여", "area": "개발", "quote": "오픈소스", "area_provenance": "manual_review"},
            {"source_id": "ref-dev", "corpus": "reference", "topic": "Python 학습", "area": "개발", "quote": "Python", "area_provenance": "manual_review"},
        ]
        plan = route_question("내 오픈소스 기여 글과 같은 관심 분야 참고 글", catalog, {"개발", "야구"})
        selected, paths = planned_paths(plan, catalog, ["baseball", "own-dev", "ref-dev"], {"개발", "야구"}, "all")
        self.assertEqual(selected[:2], ["own-dev", "ref-dev"])
        self.assertEqual(paths[0]["area_provenance"], "manual_review")

    def test_new_ai_recommendation_uses_all_own_topics_even_reference_scope(self):
        catalog = [
            {"source_id": "own-ai", "corpus": "own", "topic": "AI", "area": "AI", "quote": "AI"},
            {"source_id": "ref-repeat", "corpus": "reference", "topic": "AI", "area": "AI", "quote": "AI"},
            {"source_id": "ref-new", "corpus": "reference", "topic": "AI 에이전트 운영", "area": "AI", "quote": "에이전트"},
        ]
        plan = route_question("아직 올리지 않은 AI 주제를 추천", catalog, {"AI"})
        selected, paths = planned_paths(plan, catalog, ["ref-repeat", "ref-new"], {"AI"}, "reference")
        self.assertEqual(selected, ["ref-new"])
        self.assertEqual(paths[0]["path_type"], "profile_interest")

    def test_evidence_ids_reconstruct_exact_excerpt_and_reject_unknown_id(self):
        context = {"question": "무엇?", "sources": [{"source_id": "a", "excerpt": "정확한 원문", "permalink": "",
                                            "corpus": "own", "truncated": False}]}
        self.assertEqual(prompt_input(context)["evidence_catalog"][0]["evidence_id"], "E01")
        answer = assemble_answer({"claims": [{"text": "답", "evidence_ids": ["E01"]}],
                                  "unresolved": []}, context)
        self.assertEqual(answer["claims"][0]["evidence"][0]["quote"], "정확한 원문")
        with self.assertRaises(EvidenceError):
            assemble_answer({"claims": [{"text": "답", "evidence_ids": ["E02"]}],
                             "unresolved": []}, context)


class Text2CypherTests(unittest.TestCase):
    def test_only_exact_read_template_is_executed_with_allowed_ids(self):
        graph = FakeGraph()
        response = {"cypher": TEMPLATES["own_topic_count"], "topic": "야구"}
        result = run_one("야구 몇 개?", graph, {"a", "b"}, lambda _q: response)
        self.assertEqual(result["status"], "success")
        self.assertEqual(graph.calls[0][1], {"topic": "야구", "allowed_ids": ["a", "b"]})

    def test_generated_write_unknown_schema_and_unsupported_are_recorded(self):
        graph = FakeGraph()
        for cypher in ("MATCH (n) SET n.name = 'x' RETURN n LIMIT 1",
                       "MATCH (x:Person) RETURN x LIMIT 10"):
            result = run_one("q", graph, {"a"}, lambda _q: {"cypher": cypher, "topic": ""})
            self.assertEqual(result["status"], "rejected")
            self.assertEqual(result["generated"]["cypher"], cypher)
        self.assertEqual(run_one("q", graph, {"a"}, lambda _q: {"cypher": "", "topic": ""})["status"],
                         "unsupported")
        self.assertEqual(graph.calls, [])
        with self.assertRaises(ValueError):
            validate_generated({"cypher": TEMPLATES["own_topic_count"], "topic": ""})


if __name__ == "__main__":
    unittest.main()
