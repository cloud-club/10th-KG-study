import json

import pytest

from dataset import load_eval_set, parse_question

HASH = "a" * 40


def valid_question():
    return {
        "schema_version": 1,
        "qid": "q001",
        "question": "질문",
        "category": "semantic",
        "filters": {"room": None, "date_from": None, "date_to": None},
        "answerable": True,
        "retrieval_evaluable": True,
        "gold_evidence": [{"evidence_id": "fact", "acceptable_content_hashes": [HASH]}],
        "reference_answer": "답",
        "failure_tags": [],
    }


def test_valid_question_parses():
    question = parse_question(valid_question())
    assert question.qid == "q001"
    assert question.evidence_groups == ((HASH,),)


def test_invalid_hash_and_missing_gold_fail():
    data = valid_question()
    data["gold_evidence"][0]["acceptable_content_hashes"] = ["not-a-hash"]
    with pytest.raises(ValueError):
        parse_question(data)
    data = valid_question()
    data["gold_evidence"] = []
    with pytest.raises(ValueError):
        parse_question(data)


def test_unanswerable_question_cannot_have_gold():
    data = valid_question()
    data["answerable"] = False
    with pytest.raises(ValueError):
        parse_question(data)


def test_invalid_date_range_fails():
    data = valid_question()
    data["filters"] = {"date_from": "2025-02-01", "date_to": "2025-01-01"}
    with pytest.raises(ValueError):
        parse_question(data)


def test_duplicate_qid_fails(tmp_path):
    line = json.dumps(valid_question(), ensure_ascii=False)
    path = tmp_path / "eval.jsonl"
    path.write_text(line + "\n" + line + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_eval_set(path)
