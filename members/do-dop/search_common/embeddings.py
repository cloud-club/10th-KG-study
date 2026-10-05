"""로컬 Ollama 임베딩 호출."""

import json
import urllib.error
import urllib.request


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "bge-m3"
EMBEDDING_DIM = 1024


def embed(text: str, model: str = DEFAULT_MODEL, ollama_url: str = DEFAULT_OLLAMA_URL) -> list[float]:
    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    request = urllib.request.Request(f"{ollama_url}/api/embeddings", data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {ollama_url}/api/embeddings -> HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"{ollama_url}에 연결할 수 없습니다. `ollama serve`를 확인하세요: {error}") from error
    embedding = result.get("embedding")
    if not embedding:
        raise RuntimeError(f"임베딩 응답에 embedding 필드가 없습니다: {result}")
    return embedding


def to_pgvector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(repr(value) for value in embedding) + "]"

