"""공통 설정/연결 헬퍼.

프로젝트 루트의 .env 를 읽어 Postgres / Elasticsearch 연결 정보와
임베딩·청킹 파라미터를 제공한다. 모든 스크립트가 이 파일만 import 한다.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# ---- 저장소 --------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://kg:kg@localhost:5432/kg")
ES_URL = os.getenv("ES_URL", "http://localhost:9200")
ES_INDEX = os.getenv("ES_INDEX", "kakao_chunks")
ES_MSG_INDEX = os.getenv("ES_MSG_INDEX", "kakao_messages")

# ---- 임베딩 --------------------------------------------------------------
# EMBED_PROVIDER: openai | gemini | local
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "openai").lower()
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "64"))

# ---- 청킹 ----------------------------------------------------------------
SESSION_GAP_MIN = int(os.getenv("SESSION_GAP_MIN", "30"))    # 이 시간 이상 끊기면 새 세션
CHUNK_MAX_MSGS = int(os.getenv("CHUNK_MAX_MSGS", "30"))      # 청크당 최대 메시지 수
CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "700"))   # 청크당 최대 글자 수(대략)
CHUNK_OVERLAP_MSGS = int(os.getenv("CHUNK_OVERLAP_MSGS", "3"))  # 인접 청크가 겹치는 메시지 수


def get_pg():
    """psycopg(v3) 커넥션. autocommit=False 이므로 호출자가 commit 한다."""
    import psycopg

    return psycopg.connect(DATABASE_URL)


def get_es():
    """elasticsearch-py 클라이언트. 서버 메이저 버전(9.x)과 클라이언트 메이저 버전이 같아야 한다."""
    from elasticsearch import Elasticsearch

    return Elasticsearch(ES_URL, request_timeout=60)


def vec_literal(vec) -> str:
    """파이썬 float 리스트 -> pgvector 리터럴 문자열 '[0.1,0.2,...]'.

    어댑터 등록 없이 `%s::vector` 로 캐스팅해 쓰기 위한 가장 단순한 방법.
    """
    return "[" + ",".join(f"{float(x):.7g}" for x in vec) + "]"


def room_filter_sql(room: str | None, alias: str = "r") -> tuple[str, list]:
    """room 이름이 주어지면 WHERE 절 조각과 파라미터를 돌려준다."""
    if room:
        return f" AND {alias}.name = %s", [room]
    return "", []
