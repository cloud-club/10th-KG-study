"""All literals and source records in these public tests are synthetic."""
import unittest

from graph.experiment import (
    artifact_key,
    lucene_or_query,
    merge_rrf_graph_results,
    retrieval_metrics,
)


class GraphExperimentTests(unittest.TestCase):
    def test_artifact_key_uses_normalized_pull_request_and_slack_thread_ids(self):
        self.assertEqual(
            artifact_key({"source_system": "github", "citation": {"repository": "Synthetic_API-Service", "item_type": "pull_request", "item_number": 9}}),
            "github:synthetic_api_service:pull_request:9",
        )
        self.assertNotEqual(
            artifact_key({"source_system": "github", "citation": {"repository": "Synthetic_API-Service", "item_type": "issue", "item_number": 9}}),
            artifact_key({"source_system": "github", "citation": {"repository": "synthetic-api-service", "item_type": "pull_request", "item_number": 9}}),
        )
        self.assertEqual(
            artifact_key({"source_system": "slack", "citation": {"channel_id": "C1", "thread_ts": "123.4"}}),
            "slack:C1:123.4",
        )

    def test_retrieval_metrics_deduplicate_artifacts_and_measure_gold_recall(self):
        result = retrieval_metrics(
            ["pr:repo#1", "pr:repo#1", "slack:C1:1.0", "pr:repo#2"],
            {"pr:repo#1", "pr:repo#2", "slack:C1:1.0"},
            cutoffs=(1, 2, 3),
        )
        self.assertEqual(result["hit@1"], 1)
        self.assertAlmostEqual(result["recall@2"], 2 / 3)
        self.assertEqual(result["mrr"], 1.0)
        self.assertEqual(result["unique_ranked_artifacts"], 3)

    def test_lucene_query_quotes_tokens_and_drops_operator_injection(self):
        query = lucene_or_query('알림 OR *:* "proxy"')
        self.assertNotIn("*:*", query)
        self.assertNotIn(" OR *", query)
        self.assertIn('"알림"', query)
        self.assertIn('"proxy"', query)

    def test_rrf_graph_fusion_preserves_seed_order_and_appends_unique_expansion(self):
        seed = [{"retrieval_chunk_id": "a"}, {"retrieval_chunk_id": "b"}, {"retrieval_chunk_id": "c"}]
        expanded = ["b", "d", "e", "d", "f"]
        result = merge_rrf_graph_results(seed, expanded, seed_limit=2, limit=4)
        self.assertEqual([row["retrieval_chunk_id"] for row in result], ["a", "b", "d", "e"])
        self.assertEqual([row["retrieval_method"] for row in result], ["rrf_seed", "rrf_seed", "graph_expansion", "graph_expansion"])


if __name__ == "__main__":
    unittest.main()
