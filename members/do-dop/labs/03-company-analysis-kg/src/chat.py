#!/usr/bin/env python3
"""질문 -> 하이브리드 검색 -> 컨텍스트 조립 -> LLM 답변(근거 인용)."""

import argparse

import common_path  # noqa: F401
from hybrid_search import load_chunk_lookup, search_hybrid
from index_es import DEFAULT_INDEX
from index_pgvector import DEFAULT_DSN
from prompts import CHAT_SYSTEM_PROMPT
from search_common.elasticsearch import DEFAULT_ES_URL
from search_common.embeddings import DEFAULT_MODEL, DEFAULT_OLLAMA_URL
from search_common.llm import DEFAULT_CHAT_MODEL, chat

try:
    import psycopg
except ImportError as error:
    raise SystemExit("pgvector 단계는 `pip install -r requirements.txt`가 필요합니다.") from error


def build_context(chunks: list[dict]) -> str:
    blocks = [
        f"[{rank}] {chunk['title']} ({chunk['date']}, 소속: {'/'.join(chunk['company'])})\n{chunk['text']}"
        for rank, chunk in enumerate(chunks, start=1)
    ]
    return "\n\n".join(blocks)


def print_sources(chunks: list[dict]) -> None:
    print("\n[참고한 근거]")
    for rank, chunk in enumerate(chunks, start=1):
        print(f"[{rank}] {chunk['title']} ({chunk['date']}) chunk={chunk['id']} url={chunk['url']}")


def answer_question(
    conn,
    question: str,
    chunk_lookup: dict[str, dict],
    *,
    es_url: str = DEFAULT_ES_URL,
    index: str = DEFAULT_INDEX,
    embed_model: str = DEFAULT_MODEL,
    chat_model: str = DEFAULT_CHAT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    pool_size: int = 20,
    size: int = 5,
    rrf_k: int = 60,
) -> tuple[str, list[dict]]:
    chunks = search_hybrid(
        conn, question, chunk_lookup,
        es_url=es_url, index=index, model=embed_model, ollama_url=ollama_url,
        pool_size=pool_size, size=size, rrf_k=rrf_k,
    )
    if not chunks:
        return "검색된 근거가 없습니다.", chunks

    context = build_context(chunks)
    answer = chat(
        [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": f"[근거]\n{context}\n\n[질문]\n{question}"},
        ],
        model=chat_model,
        ollama_url=ollama_url,
    )
    return answer, chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--es-url", default=DEFAULT_ES_URL)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--embed-model", default=DEFAULT_MODEL)
    parser.add_argument("--chat-model", default=DEFAULT_CHAT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--pool-size", type=int, default=20, help="RRF 융합 전 각 검색의 후보 개수")
    parser.add_argument("--size", type=int, default=5, help="LLM에 넘길 최종 근거 개수")
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--show-context", action="store_true", help="LLM에 넘긴 근거 원문도 출력")
    args = parser.parse_args()

    chunk_lookup = load_chunk_lookup()
    with psycopg.connect(args.dsn) as conn:
        answer, chunks = answer_question(
            conn, args.question, chunk_lookup,
            es_url=args.es_url, index=args.index,
            embed_model=args.embed_model, chat_model=args.chat_model, ollama_url=args.ollama_url,
            pool_size=args.pool_size, size=args.size, rrf_k=args.rrf_k,
        )

    if args.show_context and chunks:
        print(build_context(chunks))
        print("---")

    print(answer)
    print_sources(chunks)


if __name__ == "__main__":
    main()
