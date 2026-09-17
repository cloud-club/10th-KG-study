"""03 실습의 환경 설정과 JSONL 저장 도구."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[5]
HASHTAG_PATTERN = re.compile(r"(?<!\w)#([0-9A-Za-z_가-힣]+)")


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"환경 변수 {name} 값이 필요합니다.")
    return value


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            for row in rows:
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    temporary.replace(path)
    return count
