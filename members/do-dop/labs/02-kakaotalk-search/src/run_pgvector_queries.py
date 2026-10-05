#!/usr/bin/env python3
"""config/queries.tsv의 질의 세트를 pgvector로 모두 실행하고 유사도를 TSV로 저장한다.

BM25/grep과 달리 벡터 검색에는 자연스러운 '일치/불일치'가 없으므로, 대신
1위 코사인 유사도와 상위 5개 평균 유사도를 기록해 질의 간 비교 기준으로 삼는다.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import psycopg

from embed_ollama import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, embed
from index_pgvector import DEFAULT_DSN
from search_pgvector import search


def run_queries(
    queries_path: Path,
    conn: psycopg.Connection,
    model: str,
    ollama_url: str,
    size: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    # queries.tsv를 탭 기준으로 읽어 검색어를 한 줄씩 처리한다.
    with queries_path.open("r", encoding="utf-8", newline="") as query_file:
        reader = csv.DictReader(query_file, delimiter="\t")
        for record in reader:
            # 각 검색어를 임베딩하고 가장 가까운 청크들을 찾는다.
            query_embedding = embed(record["query"], model=model, ollama_url=ollama_url)
            results = search(conn, query_embedding, size)
            # 검색 품질을 비교할 수 있도록 1위와 상위 결과 평균을 기록한다.
            similarities = [result["cosine_similarity"] for result in results]
            top1 = similarities[0] if similarities else 0.0
            avg_top5 = sum(similarities) / len(similarities) if similarities else 0.0
            rows.append(
                {
                    "query_id": record["query_id"],
                    "type": record["type"],
                    "query": record["query"],
                    "top1_cosine_similarity": f"{top1:.4f}",
                    "avg_top5_cosine_similarity": f"{avg_top5:.4f}",
                    "purpose": record["purpose"],
                }
            )
    return rows


def write_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    # 질의별 유사도 결과를 개인정보가 없는 TSV로 저장한다.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "query_id",
        "type",
        "query",
        "top1_cosine_similarity",
        "avg_top5_cosine_similarity",
        "purpose",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="질의 세트를 pgvector로 모두 실행하고 결과를 TSV로 저장합니다."
    )
    parser.add_argument("--queries", required=True, type=Path, help="config/queries.tsv 경로")
    parser.add_argument("--output", required=True, type=Path, help="결과 TSV 출력 경로")
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="PostgreSQL 연결 문자열")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama 임베딩 모델")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama base URL")
    parser.add_argument("--size", type=int, default=5, help="질의당 살펴볼 결과 수 (기본 5)")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.queries.is_file():
        raise FileNotFoundError(f"질의 파일을 찾을 수 없습니다: {args.queries}")

    # 한 번 연결한 PostgreSQL 세션에서 모든 공통 질의를 실행한다.
    with psycopg.connect(args.dsn) as conn:
        rows = run_queries(args.queries, conn, args.model, args.ollama_url, args.size)

    write_rows(rows, args.output)

    print(f"질의 수: {len(rows)}")
    print(f"결과 파일: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
