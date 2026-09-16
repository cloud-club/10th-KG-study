"""로컬 Ollama 서버(bge-m3)로 텍스트를 임베딩한다.

개인 대화 원문을 외부 서비스로 보내지 않기 위해 로컬에서 실행하는 모델만 쓴다.
표준 라이브러리 urllib만 사용한다.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "bge-m3"
EMBEDDING_DIM = 1024


def embed(
    text: str, model: str = DEFAULT_MODEL, ollama_url: str = DEFAULT_OLLAMA_URL
) -> list[float]:
    # 텍스트를 로컬 Ollama의 임베딩 API에 보낸다.
    body = {"model": model, "prompt": text}
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{ollama_url}/api/embeddings", data=payload, method="POST"
    )
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"POST {ollama_url}/api/embeddings -> HTTP {error.code}: {detail}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"{ollama_url}에 연결할 수 없습니다. `ollama serve`가 실행 중인지 확인하세요: {error}"
        ) from error

    # 응답에서 bge-m3가 만든 1024차원 벡터를 꺼낸다.
    embedding = result.get("embedding")
    if not embedding:
        raise RuntimeError(f"임베딩 응답에 embedding 필드가 없습니다: {result}")
    return embedding


def to_pgvector_literal(embedding: list[float]) -> str:
    """psycopg에 vector 타입으로 바인딩할 수 있는 '[0.1,0.2,...]' 문자열을 만든다."""
    return "[" + ",".join(repr(value) for value in embedding) + "]"
