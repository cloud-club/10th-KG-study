"""카카오톡 하이브리드 검색·답변 에이전트를 브라우저에서 실행한다."""

from __future__ import annotations

import argparse
import html
import os
import re
from functools import lru_cache

from flask import Flask, render_template, request

from chatbot import answer_question
from retrieval import load_embedding_model

app = Flask(__name__)
CITATION_PATTERN = re.compile(r"\[(kakao-\d{5})\]")


@lru_cache(maxsize=1)
def embedding_model():
    """첫 질문에서만 임베딩 모델을 메모리에 올린다."""
    return load_embedding_model()


def answer_to_html(answer: str) -> str:
    """답변의 청크 인용을 아래 근거 카드로 이동하는 링크로 바꾼다."""
    escaped = html.escape(answer)
    linked = CITATION_PATTERN.sub(
        lambda match: f'<a class="citation" href="#source-{match.group(1)}">[{match.group(1)}]</a>',
        escaped,
    )
    return linked.replace("\n", "<br>")


@app.route("/", methods=["GET", "POST"])
def index():
    question = request.form.get("question", "").strip()
    answer = None
    results: list[dict] = []
    error = None

    if request.method == "POST":
        if not question:
            error = "질문을 입력하세요."
        elif not os.getenv("OPENAI_API_KEY"):
            error = "OPENAI_API_KEY 환경변수가 없습니다. 같은 PowerShell 창에서 API 키를 설정한 뒤 다시 실행하세요."
        else:
            try:
                answer, results, _ = answer_question(
                    question,
                    os.getenv("OPENAI_MODEL", "gpt-5-mini"),
                    top_k=5,
                    rank_window=20,
                    rank_constant=60,
                    embedding_model=embedding_model(),
                )
            except RuntimeError as exc:
                error = str(exc)
            except Exception:
                error = "검색 또는 답변 생성 중 오류가 발생했습니다. Docker 컨테이너와 API 키 설정을 확인하세요."

    return render_template(
        "index.html",
        question=question,
        answer=answer,
        answer_html=answer_to_html(answer) if answer else None,
        results=results,
        error=error,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
