"""OpenAI 임베딩 API 호출을 한 곳에 모아둔다."""

from __future__ import annotations

from openai import OpenAI

from common import EMBED_DIMENSION, EMBED_MODEL

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()  # OPENAI_API_KEY 환경변수를 그대로 씀
    return _client


def embed_texts(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client().embeddings.create(model=EMBED_MODEL, input=batch)
        vectors.extend(item.embedding for item in response.data)
    for vector in vectors:
        if len(vector) != EMBED_DIMENSION:
            raise ValueError(f"임베딩 차원이 {len(vector)}입니다. 예상값: {EMBED_DIMENSION}")
    return vectors


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
