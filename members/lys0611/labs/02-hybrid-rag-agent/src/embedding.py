"""W2 문서 벡터와 같은 모델로 질문 벡터를 만든다."""
from __future__ import annotations

import math

from common import EMBED_DIM, EMBED_MODEL, EMBED_PROVIDER


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class QueryEmbedder:
    def __init__(self) -> None:
        self.provider = EMBED_PROVIDER
        self.model = EMBED_MODEL
        self.dim = EMBED_DIM
        if self.provider == "local":
            from sentence_transformers import SentenceTransformer

            self.client = SentenceTransformer(self.model)
        elif self.provider == "openai":
            from openai import OpenAI

            self.client = OpenAI()
        elif self.provider == "gemini":
            from google import genai

            self.client = genai.Client()
        else:
            raise ValueError(f"지원하지 않는 EMBED_PROVIDER: {self.provider}")

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.provider == "local":
            result = self.client.encode(
                texts,
                batch_size=min(32, len(texts)),
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            vectors = [[float(value) for value in row] for row in result]
        elif self.provider == "openai":
            response = self.client.embeddings.create(
                model=self.model, input=texts, dimensions=self.dim
            )
            vectors = [list(item.embedding) for item in response.data]
        else:
            from google.genai import types

            response = self.client.models.embed_content(
                model=self.model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=self.dim,
                ),
            )
            vectors = [list(item.values) for item in response.embeddings]

        if vectors and len(vectors[0]) != self.dim:
            raise ValueError(
                f"질문 임베딩 차원 {len(vectors[0])}이 저장 차원 {self.dim}과 다릅니다."
            )
        return [_normalize(vector) for vector in vectors]

    def embed_one(self, text: str) -> list[float]:
        return self.embed_many([text])[0]
