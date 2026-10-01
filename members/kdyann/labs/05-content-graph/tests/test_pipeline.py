import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))
import pipeline
import persist


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.documents = pipeline.load_documents([LAB / "examples/documents.jsonl"], limit_own=2,
                                                 limit_reference=1, no_recency_filter=True)
        rows = pipeline._read_jsonl(LAB / "examples/predictions.jsonl")
        self.predictions = {row["source_id"]: {"facts": row["facts"]} for row in rows}

    def test_sample_replays_to_both_rdf_formats_with_grounded_spans(self):
        with tempfile.TemporaryDirectory() as directory:
            result = pipeline.run(self.documents, self.predictions, Path(directory))
            self.assertEqual(result["documents"], 3)
            self.assertEqual(result["facts"], 12)
            facts = pipeline._read_jsonl(Path(directory) / "facts.jsonl")
            saved_documents = pipeline._read_jsonl(Path(directory) / "documents.jsonl")
            self.assertEqual(saved_documents, self.documents)
            self.assertEqual(saved_documents[-1]["selection"]["observed_likes"], 1200)
            source = {row["id"]: row["text"] for row in self.documents}
            for fact in facts:
                self.assertEqual(source[fact["source_id"]][fact["start"]:fact["end"]], fact["evidence"])
            rdf = json.loads((Path(directory) / "graph.jsonld").read_text())
            self.assertEqual(sum(len(values) for node in rdf["@graph"] for key, values in node.items() if key != "@id"), result["rdf_triples"])
            turtle = (Path(directory) / "graph.ttl").read_text()
            self.assertEqual(sum(line.startswith("<") and line.endswith(" .") for line in turtle.splitlines()), result["rdf_triples"])
            self.assertIn("statesReleaseStatus", turtle)
            self.assertIn("describesFeature", turtle)
            self.assertIn('"출시 됐습니다"', turtle)
            release_values = [value for node in rdf["@graph"] for value in node.get(pipeline.BASE + "statesReleaseStatus", [])]
            self.assertCountEqual([value["@value"] for value in release_values], ["출시 됐습니다", "출시되어"])
            self.assertTrue(all("@id" not in value for value in release_values))

    def test_wrong_span_and_wrong_domain_fail_closed(self):
        doc = self.documents[0]
        fact = dict(self.predictions[doc["id"]]["facts"][0])
        fact["evidence"] = "캡션에 없는 문장"
        with self.assertRaises(pipeline.ValidationError):
            pipeline.validate(doc, {"facts": [fact]})
        fact["evidence"] = "스터디언은 외계인 모리랑 공부하면 행성을 모아가는 뽀모도로 앱입니다."
        fact["subject_type"] = "Project"
        with self.assertRaises(pipeline.ValidationError):
            pipeline.validate(doc, {"facts": [fact]})

    def test_foreign_post_and_extra_fields_fail_closed(self):
        doc = self.documents[0]
        fact = dict(self.predictions[doc["id"]]["facts"][0])
        fact["subject_name"] = "another-post"
        with self.assertRaises(pipeline.ValidationError):
            pipeline.validate(doc, {"facts": [fact]})
        fact["subject_name"] = doc["id"]
        fact["confidence"] = 1
        with self.assertRaises(pipeline.ValidationError):
            pipeline.validate(doc, {"facts": [fact]})

    def test_entity_id_normalization_only_merges_matching_spelling(self):
        self.assertEqual(pipeline._node_id("Project", " 스터디언 "), pipeline._node_id("Project", "스터디언"))
        self.assertNotEqual(pipeline._node_id("Feature", "행성 모으기"), pipeline._node_id("Feature", "행성 뽑기"))

    def test_literal_must_be_exact_part_of_evidence(self):
        doc = self.documents[0]
        fact = next(fact for fact in self.predictions[doc["id"]]["facts"]
                    if fact["predicate"] == "statesReleaseStatus")
        with self.assertRaisesRegex(pipeline.ValidationError, "Literal 값"):
            pipeline.validate(doc, {"facts": [{**fact, "object_name": "미출시"}]})

    def test_selected_metadata_survives_input_filter(self):
        selected = pipeline.load_documents_from_rows([
            {"id": "new", "corpus": "reference", "text": "공부", "published_at": "2026-09-29T00:00:00Z",
             "collected_at": "2026-09-30T00:00:00Z", "selection": {"observed_likes": 1200},
             "metrics": {"likes": 1200}}
        ], 0, 1, as_of=datetime(2026, 9, 30, tzinfo=timezone.utc))
        self.assertEqual(selected[0]["selection"]["observed_likes"], 1200)
        self.assertEqual(selected[0]["metrics"]["likes"], 1200)

    def test_reference_recency_precedes_limit_and_keeps_own(self):
        rows = [
            {"id": "own", "corpus": "own", "text": "내 글", "published_at": "2025-01-01T00:00:00+00:00"},
            {"id": "old", "corpus": "reference", "text": "오래된 글", "published_at": "2026-09-01T00:00:00+00:00"},
            {"id": "bad", "corpus": "reference", "text": "날짜 오류", "published_at": "invalid"},
            {"id": "future", "corpus": "reference", "text": "미래 글", "published_at": "2026-09-18T00:00:00+00:00"},
            {"id": "fresh", "corpus": "reference", "text": "최근 글", "published_at": "2026-09-15T00:00:00+00:00"},
        ]
        selected = pipeline.load_documents_from_rows(rows, 1, 1,
            as_of=datetime(2026, 9, 17, tzinfo=timezone.utc))
        self.assertEqual([row["id"] for row in selected], ["own", "fresh"])

    def test_no_recent_references_is_explicit_error(self):
        rows = [{"id": "old", "corpus": "reference", "text": "오래된 글",
                 "published_at": "2026-09-01T00:00:00+00:00"}]
        with self.assertRaisesRegex(pipeline.ValidationError, "최근 7일 참고 게시물이 없습니다"):
            pipeline.load_documents_from_rows(rows, 0, 1,
                as_of=datetime(2026, 9, 17, tzinfo=timezone.utc))

    def test_as_of_date_includes_same_day_posts(self):
        row = {"id": "same-day", "corpus": "reference", "text": "당일 글",
               "published_at": "2026-09-16T08:31:00+0000"}
        from datetime import date, time
        selected = pipeline.load_documents_from_rows([row], 0, 1,
            as_of=datetime.combine(date(2026, 9, 16), time.max, tzinfo=timezone.utc))
        self.assertEqual(selected[0]["id"], "same-day")

    def test_meta_timezone_without_colon_is_preserved_in_rdf_and_persistence(self):
        self.assertEqual(pipeline._published_utc("2026-09-29T12:06:12+0000"),
                         datetime(2026, 9, 29, 12, 6, 12, tzinfo=timezone.utc))
        self.assertEqual(pipeline._published_utc("2026-09-29T21:06:12+0900"),
                         datetime(2026, 9, 29, 12, 6, 12, tzinfo=timezone.utc))
        self.assertEqual(pipeline._published_utc("2026-09-29T21:06:12+09:00"),
                         datetime(2026, 9, 29, 12, 6, 12, tzinfo=timezone.utc))
        self.assertIsNone(pipeline._published_utc("2026-09-29T12:06:12"))
        document = {"id": "meta-post", "corpus": "reference", "text": "최근 글",
                    "published_at": "2026-09-29T12:06:12+0000",
                    "collected_at": "2026-09-30T13:04:58+0000"}
        rdf = json.loads(pipeline.serialize_jsonld(pipeline._triples([document], [])))
        values = [node[pipeline.BASE + "publishedAt"][0]["@value"] for node in rdf["@graph"]
                  if pipeline.BASE + "publishedAt" in node]
        self.assertEqual(values, ["2026-09-29T12:06:12+00:00"])
        stored = persist.prepare([document], [])
        self.assertEqual(stored["documents"][0]["published_at"],
                         datetime(2026, 9, 29, 12, 6, 12, tzinfo=timezone.utc))
        self.assertEqual(stored["documents"][0]["collected_at"],
                         datetime(2026, 9, 30, 13, 4, 58, tzinfo=timezone.utc))

    def test_latest_reference_selected_before_limit_with_stable_tie_break(self):
        rows = [
            {"id": "own-old", "corpus": "own", "text": "내 글", "published_at": "2025-01-01T00:00:00Z"},
            {"id": "older", "corpus": "reference", "text": "이전", "published_at": "2026-09-14T00:00:00Z"},
            {"id": "z-latest", "corpus": "reference", "text": "최신", "published_at": "2026-09-16T08:00:00Z"},
            {"id": "a-latest", "corpus": "reference", "text": "최신", "published_at": "2026-09-16T08:00:00+00:00"},
        ]
        selected = pipeline.load_documents_from_rows(rows, 1, 2,
            as_of=datetime(2026, 9, 17, tzinfo=timezone.utc))
        self.assertEqual([row["id"] for row in selected], ["own-old", "a-latest", "z-latest"])
        rdf = json.loads(pipeline.serialize_jsonld(pipeline._triples(selected, [])))
        published = [node[pipeline.BASE + "publishedAt"][0] for node in rdf["@graph"]
                     if pipeline.BASE + "publishedAt" in node]
        self.assertEqual(len(published), 3)
        self.assertTrue(all(value["@type"] == pipeline.XSD + "dateTime" for value in published))
        self.assertIn('^^xsd:dateTime', pipeline.serialize_turtle(pipeline._triples(selected, [])))

    def test_llm_invalid_evidence_retries_then_saves_valid_result(self):
        document = self.documents[0]
        valid = self.predictions[document["id"]]
        invalid_fact = {**valid["facts"][0], "evidence": "원문에 없는 근거"}
        invalid = {"facts": [invalid_fact]}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(pipeline, "extract_openai", side_effect=[invalid, valid]) as extractor:
                result = pipeline.run([document], None, Path(directory))
            self.assertEqual(extractor.call_count, 2)
            self.assertEqual(result["facts"], len(valid["facts"]))

    def test_llm_persistent_invalid_result_fails_after_three_calls(self):
        document = self.documents[0]
        invalid_fact = {**self.predictions[document["id"]]["facts"][0],
                        "evidence": "원문에 없는 근거"}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch.object(pipeline, "extract_openai", return_value={"facts": [invalid_fact]}) as extractor:
                with self.assertRaisesRegex(pipeline.ValidationError, document["id"]):
                    pipeline.run([document], None, output)
            self.assertEqual(extractor.call_count, 3)
            self.assertFalse((output / "facts.jsonl").exists())

    def test_supplied_prediction_fails_without_llm_retry(self):
        document = self.documents[0]
        invalid_fact = {**self.predictions[document["id"]]["facts"][0],
                        "evidence": "원문에 없는 근거"}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(pipeline, "extract_openai") as extractor:
                with self.assertRaises(pipeline.ValidationError):
                    pipeline.run([document], {document["id"]: {"facts": [invalid_fact]}}, Path(directory))
            extractor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
