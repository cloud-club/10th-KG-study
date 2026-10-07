"""W6 reviewed input의 한국어·영어 언어 검토 관문."""
from __future__ import annotations

import unicodedata

ALLOWED_LANGUAGES = frozenset({"ko", "en"})


def unsupported_script_letters(text: str) -> int:
    """한글·영문 코드·해시태그를 허용하고 그 외 문자를 센다."""
    return sum(1 for char in text if unicodedata.category(char).startswith("L") and not (
        "A" <= char <= "Z" or "a" <= char <= "z"
        or "\uac00" <= char <= "\ud7a3"
        or "\u1100" <= char <= "\u11ff"
        or "\u3130" <= char <= "\u318f"
    ))


def validate_language(text: str, reviewed_language: str | None, source_id: str) -> None:
    if reviewed_language not in ALLOWED_LANGUAGES:
        raise ValueError(f"{source_id}: 참고 글의 검토 언어는 ko/en이어야 합니다.")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{source_id}: 본문이 비어 있습니다.")
    if unsupported_script_letters(text):
        raise ValueError(f"{source_id}: 한국어·영어 이외 문자권 글자가 있습니다.")


def validate_reference_records(documents: list[dict], facts: list[dict]) -> None:
    languages = {}
    for doc in documents:
        if doc.get("corpus") == "reference":
            source_id = doc.get("id", doc.get("source_id", "?"))
            language = doc.get("reviewed_language")
            validate_language(doc.get("text"), language, source_id)
            languages[source_id] = language
    for fact in facts:
        source_id = fact.get("source_id")
        if source_id in languages:
            for field in ("subject_name", "object_name", "evidence"):
                value = fact.get(field)
                if isinstance(value, str):
                    validate_language(value, languages[source_id], source_id)
