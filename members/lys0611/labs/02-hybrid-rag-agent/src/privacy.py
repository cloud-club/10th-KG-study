"""외부 모델 호출 전에 질문에 남은 실명·기본 PII를 로컬에서 치환한다."""
from __future__ import annotations

import json
import re
from pathlib import Path

from common import NAME_MAP_PATH

_PII_PATTERNS = (
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[이메일]"),
    (re.compile(r"(?<!\d)01[016789][- .]?\d{3,4}[- .]?\d{4}(?!\d)"), "[전화번호]"),
    (re.compile(r"(?<!\d)\d{6}\s?-\s?[1-4]\d{6}(?!\d)"), "[주민번호]"),
    (re.compile(r"(?<!\d)\d{10,14}(?!\d)"), "[숫자열]"),
)


def load_name_map(path: Path = NAME_MAP_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("name_map은 {실명: 가명} JSON 객체여야 합니다.")
    return {str(real): str(fake) for real, fake in data.items() if str(real).strip()}


def mask_query(query: str, name_map: dict[str, str] | None = None) -> str:
    masked = query
    mapping = load_name_map() if name_map is None else name_map
    for real, fake in sorted(mapping.items(), key=lambda item: -len(item[0])):
        masked = masked.replace(real, fake)
    for pattern, replacement in _PII_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked
