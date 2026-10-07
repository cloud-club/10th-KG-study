import argparse
import json
from pathlib import Path

from graphrag_agent import ask_agent, print_preview, retrieve_contexts


LAB_DIR = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="에이전트 v1과 v2를 같은 질문으로 비교")
    parser.add_argument("--run-api", action="store_true", help="v1/v2 답변 생성을 실제로 실행")
    parser.add_argument("--model", default="gpt-5-mini")
    args = parser.parse_args()

    questions = json.loads((LAB_DIR / "questions.json").read_text(encoding="utf-8"))
    for index, question in enumerate(questions, 1):
        print(f"\n{'=' * 72}\n[{index}] {question}")
        documents, graph, excluded = retrieve_contexts(question)
        print_preview(question, documents, graph, excluded)
        if not args.run_api:
            continue

        v1_answer = ask_agent(question, documents, [], args.model)
        v2_answer = ask_agent(question, documents, graph, args.model)
        print(f"\n[v1: 문서 검색만]\n{v1_answer}")
        print(f"\n[v2: 문서 + 그래프]\n{v2_answer}")

    if not args.run_api:
        print("\n미리보기만 완료했습니다. OpenAI API 호출과 과금은 없습니다.")
        print("실제 답변을 비교하려면 같은 명령 끝에 --run-api를 붙이세요.")


if __name__ == "__main__":
    main()
