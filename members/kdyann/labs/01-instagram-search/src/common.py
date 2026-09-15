"""Instagram 검색 실습에서 공통으로 사용하는 설정과 데이터 로더."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[5]
DOCUMENTS = REPO_ROOT / "data/kdyann/processed/instagram_documents.jsonl"
GREP_CORPUS = REPO_ROOT / "data/kdyann/processed/instagram_captions.tsv"

ES_URL = os.environ.get("ES_URL", "http://127.0.0.1:9200").rstrip("/")
ES_INDEX = os.environ.get("ES_INDEX", "kdyann_instagram_posts")

PG_DSN = os.environ.get("PG_DSN", "postgresql://kg:kg@127.0.0.1:5432/kg")
PG_TABLE = "kdyann_instagram_posts"

EMBED_MODEL = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-small")
EMBED_DIMENSION = 384


def load_documents() -> list[dict[str, Any]]:
    if not DOCUMENTS.exists():
        raise FileNotFoundError(
            f"검색 문서가 없습니다: {DOCUMENTS}\n"
            "먼저 src/fetch_instagram.py를 실행하세요."
        )

    rows = [
        json.loads(line)
        for line in DOCUMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError(f"검색 문서가 비어 있습니다: {DOCUMENTS}")
    return rows


def one_line(text: str) -> str:
    """grep 저장 파일과 터미널 출력에 적합한 한 줄 텍스트로 바꾼다."""
    return " ".join(text.replace("\t", " ").split())


def metric(document: dict[str, Any], name: str) -> int | float | None:
    value = document.get("metrics", {}).get(name)
    return value if isinstance(value, (int, float)) else None


def rate(document: dict[str, Any], name: str) -> float | None:
    value = document.get("rates", {}).get(name)
    return float(value) if isinstance(value, (int, float)) else None


def result_label(document: dict[str, Any]) -> str:
    parts = []
    for key, label in (("views", "조회"), ("reach", "도달"), ("saved", "저장"), ("shares", "공유")):
        value = metric(document, key)
        if value is not None:
            parts.append(f"{label} {value:g}")
    return " · ".join(parts)
