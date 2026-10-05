import pytest

from models import RankedHit
from rrf import reciprocal_rank_fusion


def hit(letter: str, rank: int, source: str, score: float = 1.0) -> RankedHit:
    content_hash = (letter.lower() * 40)[:40]
    return RankedHit(ord(letter), content_hash, rank, score, source)


def test_rrf_combines_rankings_without_mixing_raw_scores():
    bm25 = [hit("A", 1, "bm25", 100), hit("B", 2, "bm25", 1), hit("C", 3, "bm25", 0.5)]
    vector = [hit("B", 1, "vector", 0.2), hit("D", 2, "vector", 0.9), hit("A", 3, "vector", 0.1)]

    result = reciprocal_rank_fusion({"bm25": bm25, "vector": vector}, rank_constant=60)

    assert [item.content_hash[0] for item in result] == ["b", "a", "d", "c"]
    assert result[0].score == pytest.approx(1 / 62 + 1 / 61)
    assert result[0].ranks == {"bm25": 2, "vector": 1}


def test_duplicate_in_one_source_contributes_once():
    duplicate = hit("A", 2, "bm25", 0.8)
    result = reciprocal_rank_fusion(
        {"bm25": [hit("A", 1, "bm25"), duplicate], "vector": []}, rank_constant=60
    )
    assert len(result) == 1
    assert result[0].score == pytest.approx(1 / 61)


def test_tie_is_deterministic_by_content_hash():
    result = reciprocal_rank_fusion(
        {"bm25": [hit("B", 1, "bm25")], "vector": [hit("A", 1, "vector")]},
        rank_constant=60,
    )
    assert [item.content_hash[0] for item in result] == ["a", "b"]


def test_conflicting_chunk_id_for_same_hash_fails():
    first = hit("A", 1, "bm25")
    second = RankedHit(999, first.content_hash, 1, 0.5, "vector")
    with pytest.raises(RuntimeError):
        reciprocal_rank_fusion({"bm25": [first], "vector": [second]})


def test_invalid_constant_and_limit_fail():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion({}, rank_constant=0)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion({}, limit=-1)
