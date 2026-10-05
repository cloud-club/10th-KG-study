"""W3 설정과 외부 저장소 연결.

W2의 .env를 먼저 읽고 W3의 .env가 있으면 덮어쓴다. 원본 데이터나
실명 매핑은 이 모듈에서 출력하지 않는다.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

LAB_ROOT = Path(__file__).resolve().parents[1]


def _resolve_from_lab(value: str | None, default: Path) -> Path:
    if not value:
        return default.resolve()
    path = Path(value).expanduser()
    return (LAB_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


INGEST_ROOT = _resolve_from_lab(os.getenv("INGEST_ROOT"), LAB_ROOT.parent / "01-ingest")
load_dotenv(INGEST_ROOT / ".env")
load_dotenv(LAB_ROOT / ".env", override=True)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://kg:kg@localhost:5432/kg")
ES_URL = os.getenv("ES_URL", "http://localhost:9200")
ES_INDEX = os.getenv("ES_INDEX", "kakao_chunks")

EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "local").lower()
EMBED_MODEL = os.getenv("EMBED_MODEL", "nlpai-lab/KURE-v1")
EMBED_DIM = int(os.getenv("EMBED_DIM", "1024"))

RRF_RANK_CONSTANT = int(os.getenv("RRF_RANK_CONSTANT", "60"))
RRF_CANDIDATE_K = int(os.getenv("RRF_CANDIDATE_K", "50"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "6000"))
HNSW_EF_SEARCH = int(os.getenv("HNSW_EF_SEARCH", "100"))

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "800"))

NAME_MAP_PATH = _resolve_from_lab(
    os.getenv("NAME_MAP_PATH"), INGEST_ROOT / "data" / "private" / "name_map.json"
)


def get_pg():
    import psycopg

    return psycopg.connect(DATABASE_URL)


def get_es():
    from elasticsearch import Elasticsearch

    return Elasticsearch(ES_URL, request_timeout=60)


def vec_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.7g}" for value in vector) + "]"


def validate_search_settings() -> None:
    if RRF_RANK_CONSTANT < 1:
        raise ValueError("RRF_RANK_CONSTANT는 1 이상이어야 합니다.")
    if RRF_CANDIDATE_K < 1 or RAG_TOP_K < 1:
        raise ValueError("RRF_CANDIDATE_K와 RAG_TOP_K는 1 이상이어야 합니다.")
    if RRF_CANDIDATE_K < RAG_TOP_K:
        raise ValueError("RRF_CANDIDATE_K는 RAG_TOP_K 이상이어야 합니다.")
