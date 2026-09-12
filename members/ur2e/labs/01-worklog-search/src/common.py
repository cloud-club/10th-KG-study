"""worklog-search 실습에서 공통으로 쓰는 경로·설정."""

from __future__ import annotations

import os
from pathlib import Path

# src/ -> 01-worklog-search/ -> labs/ -> ur2e/ -> members/ -> <repo-root>
REPO_ROOT = Path(__file__).resolve().parents[5]

LAB_DIR = REPO_ROOT / "members/ur2e/labs/01-worklog-search"
VAULT_DIR = LAB_DIR / "dataset/vault"
QUERIES_PATH = LAB_DIR / "dataset/evaluation/queries.jsonl"

# 파서·평가 결과물은 vault·queries(추적 대상)로부터 다시 만들 수 있는
# 산출물이라 data/ 아래(.gitignore 대상)에 둔다. 다른 실습(members/*/labs/*)과 같은 규칙.
CHUNKS_PATH = REPO_ROOT / "data/ur2e/processed/chunks.jsonl"
EVAL_RESULTS_PATH = REPO_ROOT / "data/ur2e/processed/eval_results.jsonl"

ES_URL = os.environ.get("ES_URL", "http://127.0.0.1:9200").rstrip("/")
ES_INDEX = os.environ.get("ES_INDEX", "ur2e_worklog_chunks")

PG_DSN = os.environ.get("PG_DSN", "postgresql://kg:kg@127.0.0.1:5432/kg")
PG_TABLE = "ur2e_worklog_chunks"

EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIMENSION = 1536
