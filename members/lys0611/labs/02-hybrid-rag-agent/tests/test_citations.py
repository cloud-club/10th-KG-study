import pytest

from citations import assert_valid_citations, extract_citations, validate_citations


def test_extracts_multiple_and_deduplicates():
    assert extract_citations("첫째 [C1][C2]. 다시 [C1].") == ("C1", "C2")


def test_unknown_citation_fails():
    with pytest.raises(ValueError):
        assert_valid_citations("답입니다. [C9]", ["C1"])


def test_factual_answer_needs_citation():
    with pytest.raises(ValueError):
        assert_valid_citations("마감은 금요일입니다.", ["C1"])


def test_refusal_may_have_no_citation():
    check = assert_valid_citations("제공된 근거로는 확인할 수 없습니다.", [])
    assert check.cited == ()


def test_coverage_is_structural_not_semantic_support():
    check = validate_citations("첫 문장입니다. [C1]\n둘째 문장입니다.", ["C1"])
    assert check.factual_sentences == 2
    assert check.cited_sentences == 1
    assert check.coverage == 0.5
