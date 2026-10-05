import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]

elasticsearch_stub = types.ModuleType("elasticsearch")
elasticsearch_stub.Elasticsearch = object
elasticsearch_stub.helpers = types.SimpleNamespace()
sys.modules.setdefault("elasticsearch", elasticsearch_stub)

psycopg_stub = types.ModuleType("psycopg")
psycopg_stub.connect = None
sys.modules.setdefault("psycopg", psycopg_stub)


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    sys.modules[name] = module
    return module


load_module("common", "src/common.py")
load_module("index_documents", "src/retrieval/keyword/index_documents.py")
load_module("keyword_search_module", "src/retrieval/keyword/search.py")
load_module("vector_index_documents", "src/retrieval/vector/index_documents.py")
load_module("vector_search_module", "src/retrieval/vector/search.py")
load_module("hybrid_search_module", "src/retrieval/hybrid/search.py")
build_ground_truth = load_module("build_ground_truth", "src/evaluation/build_ground_truth.py")


def document(doc_id: str, source: str) -> dict:
    return {
        "id": doc_id,
        "page_id": doc_id,
        "title": doc_id,
        "content": doc_id,
        "source": source,
        "chunk_index": 0,
    }


def result(document_id: str, rank: int) -> dict:
    return {
        "id": document_id,
        "rank": rank,
        "score": 1.0,
        "title": document_id,
        "source": f"{document_id}.md",
        "chunk_index": 0,
        "content": document_id,
    }


class TopicGroupTest(unittest.TestCase):
    def test_uses_second_path_segment_when_nested(self):
        self.assertEqual(
            build_ground_truth.topic_group("졸전/V-O api/로그인 39ed....md"), "V-O api"
        )
        self.assertEqual(
            build_ground_truth.topic_group("졸전/Study/AWS - S3 344....md"), "Study"
        )

    def test_falls_back_to_root_when_not_nested(self):
        self.assertEqual(build_ground_truth.topic_group("졸전 317d....md"), "(root)")


class StratifiedSampleTest(unittest.TestCase):
    def test_samples_up_to_per_group_from_each_topic(self):
        documents = (
            [document(f"vo{i}", f"졸전/V-O api/api{i}.md") for i in range(5)]
            + [document(f"study{i}", f"졸전/Study/note{i}.md") for i in range(2)]
            + [document("root0", "졸전 317d.md")]
        )

        sampled = build_ground_truth.stratified_sample(documents, per_group=2, seed=1)

        groups = [build_ground_truth.topic_group(doc["source"]) for doc in sampled]
        self.assertEqual(groups.count("V-O api"), 2)
        self.assertEqual(groups.count("Study"), 2)
        self.assertEqual(groups.count("(root)"), 1)

    def test_same_seed_is_deterministic(self):
        documents = [document(f"vo{i}", f"졸전/V-O api/api{i}.md") for i in range(6)]

        first = build_ground_truth.stratified_sample(documents, per_group=3, seed=7)
        second = build_ground_truth.stratified_sample(documents, per_group=3, seed=7)

        self.assertEqual([doc["id"] for doc in first], [doc["id"] for doc in second])


class StripCodeFenceTest(unittest.TestCase):
    def test_removes_markdown_json_fence(self):
        fenced = "```json\n[{\"id\": \"a\"}]\n```"
        self.assertEqual(build_ground_truth._strip_code_fence(fenced), '[{"id": "a"}]')

    def test_leaves_plain_text_unchanged(self):
        self.assertEqual(build_ground_truth._strip_code_fence("plain"), "plain")


class GenerateQueriesTest(unittest.TestCase):
    def test_raises_when_query_type_missing(self):
        chunk = document("a", "졸전/Study/note.md")
        with patch.object(
            build_ground_truth,
            "call_openai_json",
            return_value={"single_keyword": "x", "compound_keyword": "y"},
        ):
            with self.assertRaisesRegex(RuntimeError, "natural_language"):
                build_ground_truth.generate_queries(chunk, api_key="k", model="m")


class BuildCandidatePoolTest(unittest.TestCase):
    def test_unions_and_dedupes_candidates_by_id(self):
        with (
            patch.object(build_ground_truth, "keyword_search", return_value=[result("A", 1), result("B", 2)]),
            patch.object(build_ground_truth, "vector_search", return_value=[result("B", 1), result("C", 2)]),
            patch.object(build_ground_truth, "hybrid_search", return_value=[result("A", 1)]),
        ):
            pool = build_ground_truth.build_candidate_pool(
                "query", es_client=object(), es_url="http://localhost:9200", postgres=object(), rank_window=20
            )

        self.assertEqual({candidate["id"] for candidate in pool}, {"A", "B", "C"})


class JudgeCandidatesTest(unittest.TestCase):
    def test_defaults_missing_scores_to_zero_and_drops_them(self):
        candidates = [result("A", 1), result("B", 2)]
        with patch.object(
            build_ground_truth, "call_openai_json", return_value=[{"id": "A", "score": 2}]
        ):
            scores = build_ground_truth.judge_candidates("q", "natural_language", candidates, "k", "m")

        self.assertEqual(scores, {"A": 2})

    def test_drops_unknown_candidate_ids_instead_of_failing(self):
        candidates = [result("A", 1)]
        with patch.object(
            build_ground_truth,
            "call_openai_json",
            return_value=[{"id": "Z", "score": 2}, {"id": "A", "score": 3}],
        ):
            scores = build_ground_truth.judge_candidates("q", "natural_language", candidates, "k", "m")

        self.assertEqual(scores, {"A": 3})

    def test_returns_empty_for_no_candidates(self):
        self.assertEqual(
            build_ground_truth.judge_candidates("q", "natural_language", [], "k", "m"), {}
        )


if __name__ == "__main__":
    unittest.main()
