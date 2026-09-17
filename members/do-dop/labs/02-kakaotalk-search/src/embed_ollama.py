"""공통 Ollama 임베딩 함수를 카카오톡 실습에 다시 노출한다."""

import sys
from pathlib import Path


DO_DOP_ROOT = Path(__file__).resolve().parents[3]
if str(DO_DOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DO_DOP_ROOT))

from search_common.embeddings import (  # noqa: E402,F401
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_URL,
    EMBEDDING_DIM,
    embed,
    to_pgvector_literal,
)
