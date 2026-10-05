"""RRF 하이브리드 검색 결과에 근거해 OpenAI Responses API로 답하는 카카오톡 에이전트."""

from __future__ import annotations

import argparse
import os
import re

from openai import OpenAI
from openai import APIError, RateLimitError

from retrieval import load_embedding_model, search_hybrid

SYSTEM_INSTRUCTIONS = """당신은 사용자의 카카오톡 공지 검색 에이전트입니다.
오직 제공된 '근거 청크'에 있는 정보만 사용해 한국어로 답하세요.
핵심 사실마다 반드시 [kakao-00000] 형식으로 근거 청크 ID를 붙이세요.
근거 청크가 질문에 답하지 못하면 추측하지 말고 '제공된 카카오톡 자료에서 확인할 수 없습니다.'라고 답하세요.
인용하지 않은 사실, 외부 지식, 일반적인 조언을 덧붙이지 마세요.
"""

EMPTY_ANSWER_MESSAGE = (
    "답변 생성 모델이 텍스트를 반환하지 않았습니다. "
    "아래 '검색 근거'는 정상적으로 찾았으므로, 다시 한 번 질문해 보세요."
)


def build_context(results: list[dict]) -> str:
    """LLM이 실제로 읽은 청크 ID·날짜·원문을 명시적으로 조립한다."""
    return "\n\n".join(f"[{item['id']}] 날짜: {item['date']}\n{item['content']}" for item in results)


def invalid_citations(answer: str, results: list[dict]) -> list[str]:
    allowed = {item["id"] for item in results}
    cited = set(re.findall(r"\[(kakao-\d{5})\]", answer))
    return sorted(cited - allowed)


def response_text(response) -> str:
    """SDK의 편의 속성이 비어 있어도 output 항목에서 텍스트를 읽는다."""
    if response.output_text and response.output_text.strip():
        return response.output_text.strip()

    parts: list[str] = []
    for item in response.output:
        for content in getattr(item, "content", []):
            if getattr(content, "type", None) == "output_text":
                parts.append(getattr(content, "text", ""))
    return "".join(parts).strip()


def answer_question(question: str, model_name: str, top_k: int, rank_window: int, rank_constant: int, embedding_model) -> tuple[str, list[dict], list[str]]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY 환경변수가 없습니다. README의 PowerShell 설정 명령을 먼저 실행하세요.")
    results = search_hybrid(question, top_k, rank_window, embedding_model, rank_constant)
    context = build_context(results)
    client = OpenAI()
    try:
        response = client.responses.create(
            model=model_name,
            instructions=SYSTEM_INSTRUCTIONS,
            input=f"질문: {question}\n\n근거 청크:\n{context}",
            # 짧은 근거 기반 질의에서는 숨은 추론이 출력 예산을 모두 쓰지 않게 한다.
            reasoning={"effort": "minimal"},
            max_output_tokens=900,
            store=False,
        )
    except RateLimitError as error:
        raise RuntimeError(
            "OpenAI API 잔액 또는 요청 한도가 부족합니다. "
            "플랫폼의 Billing을 확인한 뒤 다시 실행하세요."
        ) from error
    except APIError as error:
        raise RuntimeError(f"OpenAI API 요청에 실패했습니다: {error}") from error

    answer = response_text(response) or EMPTY_ANSWER_MESSAGE
    return answer, results, invalid_citations(answer, results)


def print_answer(question: str, answer: str, results: list[dict], invalid: list[str]) -> None:
    print(f"\n질문: {question}\n\n답변:\n{answer}\n\n검색 근거:")
    for item in results:
        print(f"- [{item['id']}] {item['date']} | {item['content'].replace(chr(10), ' ')[:180]}")
    if invalid:
        print(f"\n경고: 답변에 검색 결과에 없는 인용이 있습니다: {', '.join(invalid)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rank-window", type=int, default=20)
    parser.add_argument("--rank-constant", type=int, default=60)
    args = parser.parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY 환경변수가 없습니다. README의 PowerShell 설정 명령을 먼저 실행하세요.")
    embedding_model = load_embedding_model()

    def run(question: str) -> None:
        answer, results, invalid = answer_question(question, args.model, args.top_k, args.rank_window, args.rank_constant, embedding_model)
        print_answer(question, answer, results, invalid)

    if args.question:
        run(args.question)
        return
    print("카카오톡 개인 데이터 에이전트입니다. 종료하려면 exit 또는 quit을 입력하세요.")
    while True:
        question = input("\n질문> ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if question:
            run(question)


if __name__ == "__main__":
    main()
