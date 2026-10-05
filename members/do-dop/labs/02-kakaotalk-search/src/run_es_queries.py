#!/usr/bin/env python3
"""config/queries.tsv의 질의 세트를 text(nori)/text.ngram 필드에 모두 실행하고
질의별 전체 일치 수와 최고 점수를 TSV로 저장한다.

run_grep_queries.sh와 같은 원칙으로 원문은 출력/저장하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from search_es import (  # noqa: E402  (동일 디렉터리 모듈)
    DEFAULT_ES_URL,
    DEFAULT_INDEX,
    FIELD_CHOICES,
    build_search_body,
    http_search,
    total_hits,
)


def top_score(response: dict) -> float:
    # 결과는 점수순이므로 첫 번째 문서의 BM25 점수를 가져온다.
    hits = response.get("hits", {}).get("hits", [])
    if not hits:
        return 0.0
    return float(hits[0].get("_score") or 0.0)


def run_queries(
    queries_path: Path, es_url: str, index_name: str
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    # queries.tsv를 탭으로 구분해 한 줄씩 읽는다.
    with queries_path.open("r", encoding="utf-8", newline="") as query_file:
        reader = csv.DictReader(query_file, delimiter="\t")
        for record in reader:
            # type이 phrase인 질의는 개별 토큰 OR 매칭이 아니라 구문 일치로 실행한다.
            match_type = "match_phrase" if record["type"] == "phrase" else "match"
            # 같은 질의를 nori 필드와 2-gram 필드에 각각 실행한다.
            for field in FIELD_CHOICES:
                body = build_search_body(record["query"], field, size=5, match_type=match_type)
                response = http_search(es_url, index_name, body)
                rows.append(
                    {
                        "query_id": record["query_id"],
                        "type": record["type"],
                        "query": record["query"],
                        "field": field,
                        "match_type": match_type,
                        "hits": str(total_hits(response)),
                        "top_score": f"{top_score(response):.4f}",
                        "purpose": record["purpose"],
                    }
                )
    return rows


def write_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    # 결과 폴더를 만든 뒤 검색 결과를 TSV 형식으로 저장한다.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "query_id",
        "type",
        "query",
        "field",
        "match_type",
        "hits",
        "top_score",
        "purpose",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="질의 세트를 nori/ngram 필드에 모두 실행하고 결과를 TSV로 저장합니다."
    )
    parser.add_argument("--queries", required=True, type=Path, help="config/queries.tsv 경로")
    parser.add_argument("--output", required=True, type=Path, help="결과 TSV 출력 경로")
    parser.add_argument("--index", default=DEFAULT_INDEX, help="색인 이름")
    parser.add_argument("--es-url", default=DEFAULT_ES_URL, help="Elasticsearch base URL")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    # 잘못된 경로로 빈 실험 결과가 만들어지는 것을 막는다.
    if not args.queries.is_file():
        raise FileNotFoundError(f"질의 파일을 찾을 수 없습니다: {args.queries}")

    rows = run_queries(args.queries, args.es_url, args.index)
    write_rows(rows, args.output)

    print(f"질의 수: {len(rows) // len(FIELD_CHOICES)}")
    print(f"결과 행 수(필드 {len(FIELD_CHOICES)}개 x 질의): {len(rows)}")
    print(f"결과 파일: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
