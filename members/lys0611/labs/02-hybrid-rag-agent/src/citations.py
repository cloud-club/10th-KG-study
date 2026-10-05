"""인용 표기의 구조만 검증한다. 실제 주장 지지는 사람이 별도로 판정한다."""
from __future__ import annotations

import re
from collections.abc import Iterable

from models import CitationCheck

_CITATION = re.compile(r"\[(C\d+)\]")
_SENTENCE = re.compile(r"(?<=[.!?。])\s+(?!\[C\d+\])|\n+")
_REFUSAL = ("근거가 부족", "확인할 수 없", "알 수 없", "판단할 수 없")


def extract_citations(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_CITATION.findall(text)))


def validate_citations(answer: str, allowed: Iterable[str]) -> CitationCheck:
    allowed_set = set(allowed)
    cited = extract_citations(answer)
    unknown = tuple(citation for citation in cited if citation not in allowed_set)
    sentences = [part.strip() for part in _SENTENCE.split(answer) if part.strip()]
    factual = [
        sentence
        for sentence in sentences
        if not sentence.startswith(("근거:", "출처:"))
        and not any(marker in sentence for marker in _REFUSAL)
    ]
    cited_sentences = sum(bool(_CITATION.search(sentence)) for sentence in factual)
    return CitationCheck(
        cited=cited,
        unknown=unknown,
        factual_sentences=len(factual),
        cited_sentences=cited_sentences,
    )


def assert_valid_citations(answer: str, allowed: Iterable[str]) -> CitationCheck:
    check = validate_citations(answer, allowed)
    if check.unknown:
        raise ValueError(f"제공하지 않은 인용 ID: {', '.join(check.unknown)}")
    is_refusal = any(marker in answer for marker in _REFUSAL)
    if not is_refusal and not check.cited:
        raise ValueError("근거를 사용한 답변에는 [C#] 인용이 하나 이상 필요합니다.")
    return check
