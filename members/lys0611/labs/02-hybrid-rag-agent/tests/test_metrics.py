import pytest

from metrics import (
    all_evidence_at_k,
    ann_recall_at_k,
    document_recall_at_k,
    evidence_recall_at_k,
    reciprocal_rank,
)


def test_overlap_alternatives_are_one_evidence_group():
    assert evidence_recall_at_k(["overlap-b"], [["a", "overlap-b"]], 1) == 1.0


def test_two_hop_requires_both_groups():
    groups = [["trip"], ["company-a", "company-b"]]
    assert evidence_recall_at_k(["trip"], groups, 5) == 0.5
    assert all_evidence_at_k(["trip"], groups, 5) == 0
    assert all_evidence_at_k(["trip", "company-b"], groups, 5) == 1


def test_duplicates_do_not_inflate_metrics():
    assert document_recall_at_k(["a", "a", "x"], ["a", "b"], 3) == 0.5
    assert reciprocal_rank(["x", "a", "a"], ["a"], 3) == 0.5


def test_no_gold_is_not_zero_recall():
    assert document_recall_at_k(["a"], [], 1) is None
    assert evidence_recall_at_k(["a"], [], 1) is None
    assert all_evidence_at_k(["a"], [], 1) is None


def test_ann_recall_uses_exact_top_k_as_reference():
    assert ann_recall_at_k(["a", "c"], ["a", "b"], 2) == 0.5


def test_negative_k_fails():
    with pytest.raises(ValueError):
        document_recall_at_k([], ["a"], -1)
