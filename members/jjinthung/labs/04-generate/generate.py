"""검색된 대화 청크를 OpenAI 모델에 전달해 답변을 생성합니다."""

from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

SYSTEM_PROMPT_PATH = Path(__file__).resolve().with_name("system_prompt.txt")


def _load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"시스템 프롬프트 파일을 찾을 수 없습니다: {SYSTEM_PROMPT_PATH}"
        )
    prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"시스템 프롬프트 파일이 비어 있습니다: {SYSTEM_PROMPT_PATH}")
    return prompt


def _build_context(results: list[dict]) -> str:
    return "\n".join(
        json.dumps(
            {
                "검색순위": result["rank"],
                "시작": result["start"],
                "종료": result["end"],
                "대화": result["messages"],
            },
            ensure_ascii=False,
        )
        for result in results
    )


def generate_answer(
    query: str,
    results: list[dict],
    model: str | None = None,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY 환경변수가 없습니다. "
            "PowerShell에서 $env:OPENAI_API_KEY를 설정하세요."
        )
    if not results:
        return "검색된 대화 근거가 없어 답변할 수 없습니다."

    system_prompt = _load_system_prompt()
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": (
                    f"질문:\n{query}\n\n"
                    f"대화 근거(top-{len(results)}):\n{_build_context(results)}"
                ),
            },
        ],
    )
    answer = response.choices[0].message.content
    if not answer:
        raise RuntimeError("OpenAI 응답에 답변 내용이 없습니다.")
    return answer.strip()
