"""Elasticsearch BM25와 pgvector 결과를 RRF로 융합해 검색한다."""

from __future__ import annotations

import argparse

from retrieval import load_embedding_model, search_hybrid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rank-window", type=int, default=20, help="각 검색기에서 RRF로 넘길 결과 수")
    parser.add_argument("--rank-constant", type=int, default=60, help="RRF k 값")
    parser.add_argument("--host", default="http://127.0.0.1:9201")
    parser.add_argument("--index", default="kakao_chunks")
    parser.add_argument("--dsn", default="postgresql://study:study@127.0.0.1:5433/search_study")
    args = parser.parse_args()
    model = load_embedding_model()
    results = search_hybrid(args.query, args.top_k, args.rank_window, model, args.rank_constant, args.host, args.index, args.dsn)
    print(f"RRF 하이브리드 검색: query={args.query!r}, rank_window={args.rank_window}, rank_constant={args.rank_constant}")
    for rank, item in enumerate(results, 1):
        print(f"{rank}. rrf_score={item['score']:.5f} id={item['id']} date={item['date']} ({', '.join(item['origins'])})")
        print(f"   {item['content'].replace(chr(10), ' ')[:260]}")


if __name__ == "__main__":
    main()
