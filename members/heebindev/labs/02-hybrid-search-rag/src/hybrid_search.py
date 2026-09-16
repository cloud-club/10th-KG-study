"""Elasticsearch BM25와 pgvector 검색 결과를 RRF로 결합한다."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
FIRST_LAB_ROOT = LAB_ROOT.parent / "01-notion-search"
os.environ.setdefault("HF_HOME", str(FIRST_LAB_ROOT / ".cache" / "huggingface"))

import psycopg
from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_DSN = "postgresql://kg:kg@127.0.0.1:5432/kg"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="검색할 자연어 질문")
    parser.add_argument("--limit", type=int, default=5, help="최종 출력 결과 수")
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=20,
        help="각 검색 방식에서 가져올 후보 수",
    )
    parser.add_argument("--rrf-k", type=int, default=60, help="RRF 평활화 상수")
    parser.add_argument("--url", default="http://127.0.0.1:9200")
    parser.add_argument("--index", default="notion_chunks")
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    return parser.parse_args()


def vector_literal(vector) -> str:
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def search_bm25(query: str, limit: int, url: str, index: str) -> list[dict]:
    body = {
        "size": limit,
        "_source": ["id", "document_title", "heading", "content"],
        "query": {"match": {"content": query}},
    }
    request = urllib.request.Request(
        f"{url.rstrip('/')}/{index}/_search",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Elasticsearch 검색 실패 ({error.code}): {message}"
        ) from error

    return [
        {
            "id": hit["_id"],
            "document_title": hit["_source"]["document_title"],
            "heading": hit["_source"]["heading"],
            "content": hit["_source"]["content"],
            "original_score": hit["_score"],
        }
        for hit in result["hits"]["hits"]
    ]


def search_vector(
    query: str,
    limit: int,
    dsn: str,
    model_name: str,
    model: SentenceTransformer | None = None,
) -> list[dict]:
    if model is None:
        model = SentenceTransformer(model_name)
    embedding = model.encode(f"query: {query}", normalize_embeddings=True)
    query_vector = vector_literal(embedding)

    with psycopg.connect(dsn) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                document_title,
                heading,
                content,
                1 - (embedding <=> %s::vector) AS similarity
            FROM document_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query_vector, query_vector, limit),
        ).fetchall()

    return [
        {
            "id": chunk_id,
            "document_title": title,
            "heading": heading,
            "content": content,
            "original_score": float(similarity),
        }
        for chunk_id, title, heading, content, similarity in rows
    ]


def reciprocal_rank_fusion(
    bm25_results: list[dict],
    vector_results: list[dict],
    rrf_k: int,
) -> list[dict]:
    scores: defaultdict[str, float] = defaultdict(float)
    documents: dict[str, dict] = {}
    ranks: defaultdict[str, dict[str, int]] = defaultdict(dict)

    for search_name, results in (
        ("BM25", bm25_results),
        ("벡터", vector_results),
    ):
        for rank, result in enumerate(results, start=1):
            chunk_id = result["id"]
            scores[chunk_id] += 1 / (rrf_k + rank)
            ranks[chunk_id][search_name] = rank
            documents.setdefault(chunk_id, result)

    fused_results = []
    for chunk_id, score in scores.items():
        fused_results.append(
            {
                **documents[chunk_id],
                "rrf_score": score,
                "bm25_rank": ranks[chunk_id].get("BM25"),
                "vector_rank": ranks[chunk_id].get("벡터"),
            }
        )
    return sorted(fused_results, key=lambda result: result["rrf_score"], reverse=True)


def rank_label(rank: int | None) -> str:
    return f"{rank}위" if rank is not None else "후보 밖"


def main() -> None:
    args = parse_args()
    if args.limit <= 0 or args.candidate_limit <= 0:
        raise ValueError("--limit과 --candidate-limit은 1 이상이어야 합니다.")
    if args.rrf_k < 0:
        raise ValueError("--rrf-k는 0 이상이어야 합니다.")

    print("BM25 검색 중...")
    bm25_results = search_bm25(args.query, args.candidate_limit, args.url, args.index)
    print("벡터 검색 중...")
    vector_results = search_vector(
        args.query,
        args.candidate_limit,
        args.dsn,
        args.model,
    )
    fused_results = reciprocal_rank_fusion(bm25_results, vector_results, args.rrf_k)

    print(f"\n검색어: {args.query}")
    print(
        f"후보: BM25 {len(bm25_results)}개 + 벡터 {len(vector_results)}개, "
        f"RRF k={args.rrf_k}"
    )

    for rank, result in enumerate(fused_results[: args.limit], start=1):
        preview = " ".join(result["content"].split())[:180]
        print(f"\n{rank}. RRF 점수={result['rrf_score']:.6f}")
        print(
            f"   원래 순위: BM25 {rank_label(result['bm25_rank'])}, "
            f"벡터 {rank_label(result['vector_rank'])}"
        )
        print(f"   청크 ID: {result['id']}")
        print(f"   문서: {result['document_title']}")
        print(f"   소제목: {result['heading']}")
        print(f"   내용: {preview}...")


if __name__ == "__main__":
    main()
