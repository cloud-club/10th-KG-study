import argparse
import sys
from pathlib import Path

from common import openai_response, response_text
from graph_retriever import format_graph_context, retrieve_graph_context


LAB_DIR = Path(__file__).resolve().parents[1]
W3_SRC = LAB_DIR.parent / "02-hybrid-search-rag" / "src"
sys.path.insert(0, str(W3_SRC))

from hybrid_search import (  # noqa: E402
    DEFAULT_DSN,
    DEFAULT_MODEL,
    reciprocal_rank_fusion,
    search_bm25,
    search_vector,
)


def retrieve_contexts(
    question: str,
    embedding_model=None,
    candidate_limit: int = 20,
    document_limit: int = 5,
    graph_limit: int = 5,
) -> tuple[list[dict], list[dict], list[dict]]:
    bm25 = search_bm25(
        question,
        candidate_limit,
        "http://127.0.0.1:9200",
        "notion_chunks",
    )
    vector = search_vector(
        question,
        candidate_limit,
        DEFAULT_DSN,
        DEFAULT_MODEL,
        embedding_model,
    )
    documents = reciprocal_rank_fusion(bm25, vector, 60)[:document_limit]
    chunk_ids = [document["id"] for document in documents]
    graph, excluded = retrieve_graph_context(question, chunk_ids, graph_limit)
    return documents, graph, excluded


def format_document_context(documents: list[dict]) -> str:
    return "\n\n".join(
        f"[D{index}] {document['document_title']} — {document['heading']}\n"
        f"{document['content']}"
        for index, document in enumerate(documents, 1)
    )


def ask_agent(
    question: str,
    documents: list[dict],
    graph: list[dict],
    model: str = "gpt-5-mini",
) -> str:
    document_context = format_document_context(documents)
    graph_context = format_graph_context(graph)
    prompt = f"""질문: {question}

[문서 검색 결과]
{document_context}

[그래프 검색 결과]
{graph_context}

문서와 그래프 근거 안에서만 한국어로 답하세요.
문서 근거는 [D1], 그래프 근거는 [G1]처럼 인용하세요.
두 근거가 충돌하거나 부족하면 추측하지 말고 그 사실을 말하세요.
"""
    response = openai_response(
        {
            "model": model,
            "reasoning": {"effort": "minimal"},
            "max_output_tokens": 2000,
            "instructions": (
                "당신은 사용자의 개인 문서를 검색해 답하는 GraphRAG 에이전트입니다. "
                "제공된 근거 밖의 사실을 만들지 마세요."
            ),
            "input": prompt,
        }
    )
    return response_text(response)


def print_preview(question: str, documents: list[dict], graph: list[dict], excluded: list[dict]):
    print(f"질문: {question}")
    print(f"문서 근거: {len(documents)}개")
    for index, document in enumerate(documents, 1):
        print(f"  [D{index}] {document['document_title']} — {document['heading']}")
    print(f"그래프 근거: {len(graph)}개")
    for index, relation in enumerate(graph, 1):
        print(
            f"  [G{index}] {relation['subject']} -{relation['predicate']}-> "
            f"{relation['object']}"
        )
    print(f"검토 대상으로 제외한 관계: {len(excluded)}개")


def main():
    parser = argparse.ArgumentParser(description="문서 검색과 그래프 검색을 결합한 에이전트 v2")
    parser.add_argument("question")
    parser.add_argument("--dry-run", action="store_true", help="OpenAI API를 호출하지 않음")
    parser.add_argument("--model", default="gpt-5-mini")
    args = parser.parse_args()

    print("하이브리드 문서 검색과 로컬 그래프 검색 중...")
    documents, graph, excluded = retrieve_contexts(args.question)
    print_preview(args.question, documents, graph, excluded)
    if args.dry_run:
        print("\n--dry-run: 여기서 멈췄습니다. OpenAI API 호출과 과금은 없습니다.")
        return

    print(f"\n{args.model}에 문서와 그래프 근거를 전달하여 답변 생성 중...")
    answer = ask_agent(args.question, documents, graph, args.model)
    print(f"\n답변:\n{answer}")


if __name__ == "__main__":
    main()
