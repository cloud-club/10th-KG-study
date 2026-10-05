#!/usr/bin/env python3
"""추출 JSONL과 Postgres 지식 그래프의 품질 통계를 만든다."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


LAB_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = LAB_DIR / "extracted.jsonl"
DEFAULT_OUTPUT = LAB_DIR / "output" / "extraction-stats.md"
DEFAULT_JSON_OUTPUT = LAB_DIR / "output" / "extraction-stats.json"
DEFAULT_DSN = "postgresql://study:study@localhost:5433/study"

REJECTION_REASONS = (
    "unknown_predicate",
    "dangling_subject",
    "evidence_not_found",
    "domain_mismatch",
    "range_mismatch",
)
PREDICATES = ("partOf", "usesTechnology", "hasPurpose", "hasStatus", "replaces")
ENTITY_TYPES = ("Project", "Technology", "TechnologyUse")


@dataclass
class ExtractionStats:
    chunks: int
    error_chunks: int
    total_extracted_triples: int
    validation_passed: int
    validation_rejected: int
    pass_rate_percent: float
    evidence_not_found: int
    hallucination_rate_percent: float
    rejected_by_reason: dict[str, int]
    accepted_by_predicate: dict[str, int]


@dataclass
class DatabaseStats:
    entities: int
    edges: int
    nodes_by_type: dict[str, int]
    edges_by_predicate: dict[str, int]
    extraction_runs: dict[str, int]


def load_extraction_stats(path: Path) -> ExtractionStats:
    chunks = 0
    error_chunks = 0
    passed = 0
    rejected = 0
    rejected_by_reason = Counter({reason: 0 for reason in REJECTION_REASONS})
    accepted_by_predicate = Counter({predicate: 0 for predicate in PREDICATES})

    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: 잘못된 JSON: {exc}") from exc
            chunks += 1
            if record.get("error") is not None:
                error_chunks += 1

            triples = record.get("triples") or []
            rejected_items = record.get("rejected") or []
            passed += len(triples)
            rejected += len(rejected_items)
            accepted_by_predicate.update(
                str(triple.get("predicate", "missing")) for triple in triples
            )
            rejected_by_reason.update(
                str(item.get("reason", "missing")) for item in rejected_items
            )

    total = passed + rejected
    evidence_not_found = rejected_by_reason["evidence_not_found"]
    pass_rate = passed / total * 100 if total else 0.0
    hallucination_rate = evidence_not_found / total * 100 if total else 0.0
    return ExtractionStats(
        chunks=chunks,
        error_chunks=error_chunks,
        total_extracted_triples=total,
        validation_passed=passed,
        validation_rejected=rejected,
        pass_rate_percent=pass_rate,
        evidence_not_found=evidence_not_found,
        hallucination_rate_percent=hallucination_rate,
        rejected_by_reason=dict(sorted(rejected_by_reason.items())),
        accepted_by_predicate=dict(sorted(accepted_by_predicate.items())),
    )


def connect(dsn: str):
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - 설치 오류 안내 경로
        raise RuntimeError(
            "psycopg가 필요합니다. python3 -m pip install -r requirements.txt 를 실행하세요."
        ) from exc
    return psycopg.connect(dsn)


def _count_map(cursor, query: str, params: tuple[Any, ...] = ()) -> dict[str, int]:
    cursor.execute(query, params)
    return {str(key): int(count) for key, count in cursor.fetchall()}


def load_database_stats(connection, extraction_run: str | None = None) -> DatabaseStats:
    edge_where = " WHERE extraction_run = %s" if extraction_run else ""
    params: tuple[Any, ...] = (extraction_run,) if extraction_run else ()
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM entities")
        entities = int(cursor.fetchone()[0])
        cursor.execute("SELECT count(*) FROM edges" + edge_where, params)
        edges = int(cursor.fetchone()[0])
        nodes_by_type = _count_map(
            cursor,
            "SELECT type, count(*) FROM entities GROUP BY type ORDER BY type",
        )
        edges_by_predicate = _count_map(
            cursor,
            "SELECT predicate, count(*) FROM edges"
            + edge_where
            + " GROUP BY predicate ORDER BY predicate",
            params,
        )
        extraction_runs = _count_map(
            cursor,
            "SELECT extraction_run, count(*) FROM edges "
            "GROUP BY extraction_run ORDER BY extraction_run",
        )

    for entity_type in ENTITY_TYPES:
        nodes_by_type.setdefault(entity_type, 0)
    for predicate in PREDICATES:
        edges_by_predicate.setdefault(predicate, 0)
    return DatabaseStats(
        entities=entities,
        edges=edges,
        nodes_by_type=dict(sorted(nodes_by_type.items())),
        edges_by_predicate=dict(sorted(edges_by_predicate.items())),
        extraction_runs=dict(sorted(extraction_runs.items())),
    )


def render_markdown(
    input_path: Path,
    extraction: ExtractionStats,
    database: DatabaseStats,
    extraction_run: str | None,
) -> str:
    scope = extraction_run or "전체 run"
    lines = [
        "# 트리플 추출 통계",
        "",
        f"- 입력: `{input_path}`",
        f"- DB 엣지 범위: `{scope}`",
        "- 총 추출 트리플 수는 검증 통과와 rejected를 합친 LLM 후보 수다.",
        "- evidence_not_found 비율(환각률)은 전체 후보 중 원문에서 근거를 찾지 못한 비율이다.",
        "",
        "## 검증 요약",
        "",
        "| 항목 | 값 |",
        "|---|---:|",
        f"| 처리 청크 | {extraction.chunks:,} |",
        f"| 오류 청크 | {extraction.error_chunks:,} |",
        f"| 총 추출 트리플 후보 | {extraction.total_extracted_triples:,} |",
        f"| 검증 통과 | {extraction.validation_passed:,} |",
        f"| 검증 탈락 | {extraction.validation_rejected:,} |",
        f"| 통과율 | {extraction.pass_rate_percent:.2f}% |",
        f"| evidence_not_found | {extraction.evidence_not_found:,} |",
        f"| evidence_not_found 비율(환각률) | {extraction.hallucination_rate_percent:.2f}% |",
        "",
        "## rejected 사유별 분포",
        "",
        "| 사유 | 개수 |",
        "|---|---:|",
    ]
    lines.extend(
        f"| `{reason}` | {count:,} |"
        for reason, count in extraction.rejected_by_reason.items()
    )
    lines.extend(
        [
            "",
            "## 술어별 분포",
            "",
            "| 술어 | JSONL 검증 통과 | DB 엣지 |",
            "|---|---:|---:|",
        ]
    )
    all_predicates = sorted(
        set(extraction.accepted_by_predicate) | set(database.edges_by_predicate)
    )
    lines.extend(
        f"| `{predicate}` | {extraction.accepted_by_predicate.get(predicate, 0):,} "
        f"| {database.edges_by_predicate.get(predicate, 0):,} |"
        for predicate in all_predicates
    )
    lines.extend(
        [
            "",
            "## DB 노드 타입별 개수",
            "",
            "| 타입 | 개수 |",
            "|---|---:|",
        ]
    )
    lines.extend(
        f"| `{entity_type}` | {count:,} |"
        for entity_type, count in database.nodes_by_type.items()
    )
    lines.extend(
        [
            "",
            f"DB 합계: 엔티티 {database.entities:,}개, 엣지 {database.edges:,}개.",
            "",
            "## DB extraction_run별 엣지",
            "",
            "| extraction_run | 엣지 |",
            "|---|---:|",
        ]
    )
    lines.extend(
        f"| `{run}` | {count:,} |" for run, count in database.extraction_runs.items()
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="추출 JSONL과 Postgres의 품질 통계를 생성합니다.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dsn", default=os.environ.get("POSTGRES_DSN", DEFAULT_DSN))
    parser.add_argument("--extraction-run", help="지정하면 해당 run의 DB 엣지만 집계")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        extraction = load_extraction_stats(args.input)
        with connect(args.dsn) as connection:
            database = load_database_stats(connection, args.extraction_run)
        markdown = render_markdown(args.input, extraction, database, args.extraction_run)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(
                {"extraction": asdict(extraction), "database": asdict(database)},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    print(markdown, end="")
    print(f"Markdown 저장: {args.output}")
    print(f"JSON 저장: {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
