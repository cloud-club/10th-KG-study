"""답변 생성 제공자. 검색·평가 명령에서는 이 모듈이 네트워크를 호출하지 않는다."""
from __future__ import annotations

from typing import Protocol

from common import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_OUTPUT_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
)


class AnswerGenerator(Protocol):
    def generate(self, *, system: str, user: str) -> str: ...


class OpenAIGenerator:
    def __init__(self, model: str) -> None:
        from openai import OpenAI

        self.model = model
        self.client = OpenAI()

    def generate(self, *, system: str, user: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            instructions=system,
            input=user,
            max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
        )
        return response.output_text.strip()


class OpenAICompatibleGenerator:
    def __init__(self, model: str) -> None:
        from openai import OpenAI

        if not LLM_BASE_URL:
            raise ValueError("openai-compatible에는 LLM_BASE_URL이 필요합니다.")
        self.model = model
        self.client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY or "local")

    def generate(self, *, system: str, user: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0,
            max_tokens=LLM_MAX_OUTPUT_TOKENS,
        )
        return (response.choices[0].message.content or "").strip()


class GeminiGenerator:
    def __init__(self, model: str) -> None:
        from google import genai

        self.model = model
        self.client = genai.Client()

    def generate(self, *, system: str, user: str) -> str:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0,
                max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
            ),
        )
        return (response.text or "").strip()


def create_generator() -> AnswerGenerator | None:
    if LLM_PROVIDER in {"", "none"}:
        return None
    if not LLM_MODEL:
        raise ValueError("LLM_PROVIDER를 사용하려면 LLM_MODEL이 필요합니다.")
    if LLM_PROVIDER == "openai":
        return OpenAIGenerator(LLM_MODEL)
    if LLM_PROVIDER == "openai-compatible":
        return OpenAICompatibleGenerator(LLM_MODEL)
    if LLM_PROVIDER == "gemini":
        return GeminiGenerator(LLM_MODEL)
    raise ValueError(f"지원하지 않는 LLM_PROVIDER: {LLM_PROVIDER}")
