#!/usr/bin/env python3
"""extracted.jsonl을 정규화해 Postgres에 적재하고 RDF로 내보낸다.

실행 예시:
    python3 src/store_kg.py
    python3 src/store_kg.py --input extracted.review20.jsonl --mode load
    python3 src/store_kg.py --mode export
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable


LAB_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = LAB_DIR / "extracted.jsonl"
DEFAULT_OUTPUT_DIR = LAB_DIR / "output"
DEFAULT_DSN = "postgresql://study:study@localhost:5433/study"
KG_BASE = "http://example.org/kg/"

ENTITY_TYPES = {"Project", "Technology", "TechnologyUse"}
IRI_PREDICATES = {"partOf", "usesTechnology", "replaces"}
LITERAL_PREDICATES = {"hasPurpose", "hasStatus"}
PREDICATES = IRI_PREDICATES | LITERAL_PREDICATES


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    type      TEXT NOT NULL,
    label     TEXT NOT NULL,
    props     JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS edges (
    id             BIGSERIAL PRIMARY KEY,
    subject        TEXT NOT NULL REFERENCES entities(entity_id),
    predicate      TEXT NOT NULL,
    object         TEXT NOT NULL,
    chunk_id       TEXT NOT NULL REFERENCES chunks(chunk_id),
    evidence       TEXT NOT NULL,
    confidence     REAL,
    extraction_run TEXT NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS edges_subject_predicate_idx
    ON edges (subject, predicate);
CREATE INDEX IF NOT EXISTS edges_object_predicate_idx
    ON edges (object, predicate);
CREATE UNIQUE INDEX IF NOT EXISTS edges_unique_spoc_idx
    ON edges (subject, predicate, object, chunk_id);
"""


PROJECT_ALIASES = {
    "secause": "secause",
    "직행": "jikhaeng",
    "zighang": "jikhaeng",
    "kusitms x 직행 기업과제": "jikhaeng",
    "teamficial": "teamficial",
    "teampicial": "teamficial",
    "팀피셜": "teamficial",
}

TECHNOLOGY_ALIASES = {
    "레디스": "redis",
    "redis": "redis",
    "redis queue": "rq",
    "rq": "rq",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "포스트그레스": "postgresql",
    "포스트그레sql": "postgresql",
    "opensearch": "opensearch",
    "오픈서치": "opensearch",
    "spring boot": "spring boot",
    "spring boot 3": "spring boot",
    "spring boot 3 x": "spring boot",
    "spring boot 4": "spring boot",
    "aws s3": "aws s3",
    "s3": "aws s3",
    "aws ec2": "aws ec2",
    "ec2": "aws ec2",
}


@dataclass
class NormalizedData:
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[dict[str, Any]] = field(default_factory=list)
    mappings: list[dict[str, str]] = field(default_factory=list)
    skipped_errors: int = 0
    dropped_uses: int = 0

    @property
    def source_entity_count(self) -> int:
        return len(self.mappings)

    @property
    def merged_count(self) -> int:
        return self.source_entity_count - len(self.entities)


def clean_label(value: str) -> str:
    """라벨을 NFKC 소문자로 바꾸고 특수문자를 공백으로 치환한다."""
    value = unicodedata.normalize("NFKC", str(value)).lower().strip()
    value = "".join(ch if ch.isalnum() or ch in {" ", "-"} else " " for ch in value)
    return re.sub(r"[\s-]+", " ", value).strip()


def canonical_label(label: str, entity_type: str) -> str:
    cleaned = clean_label(label)
    aliases = PROJECT_ALIASES if entity_type == "Project" else TECHNOLOGY_ALIASES
    if entity_type == "Technology" and re.fullmatch(r"spring boot(?: \d+(?: \d+)*)?", cleaned):
        return "spring boot"
    return aliases.get(cleaned, cleaned)


def slugify(label: str) -> str:
    """정규화된 라벨을 영문 소문자·숫자·하이픈 slug로 바꾼다."""
    normalized = unicodedata.normalize("NFKC", label).lower()
    if normalized.isascii():
        romanized = normalized
    else:
        try:
            from unidecode import unidecode
        except ImportError as exc:  # pragma: no cover - 설치 오류 안내 경로
            raise RuntimeError(
                "한글 IRI 생성에 Unidecode가 필요합니다. "
                "python3 -m pip install -r requirements.txt 를 실행하세요."
            ) from exc
        romanized = unidecode(normalized)
    slug = re.sub(r"[^a-z0-9]+", "-", romanized).strip("-")
    if not slug:
        raise ValueError(f"IRI로 변환할 수 없는 라벨입니다: {label!r}")
    return slug


def make_entity_id(entity_type: str, label: str) -> str:
    slug = slugify(label)
    if entity_type == "Project":
        return f"kg:{slug}"
    if entity_type == "Technology":
        return f"kg:tech-{slug}"
    raise ValueError(f"일반 엔티티 ID 생성이 불가능한 타입입니다: {entity_type}")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: 잘못된 JSON: {exc}") from exc
    return records


def _merge_props(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if value not in (None, "") and target.get(key) in (None, ""):
            target[key] = value


def _add_entity(result: NormalizedData, entity: dict[str, Any]) -> None:
    existing = result.entities.get(entity["entity_id"])
    if existing is None:
        result.entities[entity["entity_id"]] = entity
        return
    if existing["type"] != entity["type"]:
        raise ValueError(
            f"정규화 ID 충돌: {entity['entity_id']}가 "
            f"{existing['type']}와 {entity['type']}에 동시에 사용됐습니다."
        )
    _merge_props(existing["props"], entity["props"])


def _first_object(triples: list[dict[str, Any]], subject: str, predicate: str) -> str | None:
    for triple in triples:
        if triple.get("subject") == subject and triple.get("predicate") == predicate:
            value = triple.get("object")
            return str(value) if value is not None else None
    return None


def normalize_records(records: list[dict[str, Any]]) -> NormalizedData:
    """LLM ID를 버리고 전체 입력에서 일관된 ID와 엣지를 만든다."""
    result = NormalizedData()
    local_ids: dict[tuple[str, str], str] = {}
    use_contexts: dict[tuple[str, str], tuple[str, str, str, str]] = {}
    use_labels: dict[tuple[str, str], str] = {}
    use_props: dict[tuple[str, str], dict[str, str | None]] = {}

    valid_records: list[dict[str, Any]] = []
    for record in records:
        if record.get("error") is not None:
            result.skipped_errors += 1
            continue
        valid_records.append(record)
        chunk_id = str(record["chunk_id"])
        for entity in record.get("entities", []):
            entity_type = entity.get("type")
            if entity_type not in ENTITY_TYPES or entity_type == "TechnologyUse":
                continue
            old_id = str(entity.get("id", ""))
            old_label = str(entity.get("label", ""))
            new_label = canonical_label(old_label, entity_type)
            new_id = make_entity_id(entity_type, new_label)
            local_ids[(chunk_id, old_id)] = new_id
            _add_entity(
                result,
                {
                    "entity_id": new_id,
                    "type": entity_type,
                    "label": new_label,
                    "props": dict(entity.get("props") or {}),
                },
            )
            result.mappings.append(
                {
                    "chunk_id": chunk_id,
                    "old_id": old_id,
                    "old_label": old_label,
                    "type": entity_type,
                    "new_id": new_id,
                    "new_label": new_label,
                }
            )

    signatures_by_pair: dict[tuple[str, str], set[tuple[str, str, str, str]]] = defaultdict(set)
    for record in valid_records:
        chunk_id = str(record["chunk_id"])
        triples = list(record.get("triples", []))
        for entity in record.get("entities", []):
            if entity.get("type") != "TechnologyUse":
                continue
            old_id = str(entity.get("id", ""))
            project_old = _first_object(triples, old_id, "partOf")
            technology_old = _first_object(triples, old_id, "usesTechnology")
            project_id = local_ids.get((chunk_id, project_old or ""))
            technology_id = local_ids.get((chunk_id, technology_old or ""))
            if project_id is None or technology_id is None:
                result.dropped_uses += 1
                continue
            props = dict(entity.get("props") or {})
            purpose = _first_object(triples, old_id, "hasPurpose") or props.get("purpose") or ""
            status = _first_object(triples, old_id, "hasStatus") or props.get("status") or ""
            signature = (project_id, technology_id, clean_label(str(purpose)), clean_label(str(status)))
            use_contexts[(chunk_id, old_id)] = signature
            use_labels[(chunk_id, old_id)] = str(entity.get("label", ""))
            use_props[(chunk_id, old_id)] = {
                "purpose": str(purpose) if purpose else None,
                "status": str(status) if status else None,
            }
            signatures_by_pair[(project_id, technology_id)].add(signature)

    signature_ids: dict[tuple[str, str, str, str], str] = {}
    for pair, signatures in signatures_by_pair.items():
        project_slug = pair[0].removeprefix("kg:")
        technology_slug = pair[1].removeprefix("kg:tech-")
        for number, signature in enumerate(sorted(signatures), 1):
            signature_ids[signature] = f"kg:use-{project_slug}-{technology_slug}-{number}"

    for occurrence, signature in use_contexts.items():
        chunk_id, old_id = occurrence
        new_id = signature_ids[signature]
        _add_entity(
            result,
            {
                "entity_id": new_id,
                "type": "TechnologyUse",
                "label": f"{signature[0].removeprefix('kg:')} {signature[1].removeprefix('kg:tech-')} use",
                "props": use_props[occurrence],
            },
        )
        local_ids[occurrence] = new_id
        result.mappings.append(
            {
                "chunk_id": chunk_id,
                "old_id": old_id,
                "old_label": use_labels[occurrence],
                "type": "TechnologyUse",
                "new_id": new_id,
                "new_label": result.entities[new_id]["label"],
            }
        )

    seen_edges: set[tuple[str, str, str, str]] = set()
    for record in valid_records:
        chunk_id = str(record["chunk_id"])
        for triple in record.get("triples", []):
            predicate = str(triple.get("predicate", ""))
            if predicate not in PREDICATES:
                continue
            subject = local_ids.get((chunk_id, str(triple.get("subject", ""))))
            if subject is None:
                continue
            if predicate in IRI_PREDICATES:
                obj = local_ids.get((chunk_id, str(triple.get("object", ""))))
                if obj is None:
                    continue
            else:
                obj = str(triple.get("object", ""))
            edge_key = (subject, predicate, obj, chunk_id)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            result.edges.append(
                {
                    "subject": subject,
                    "predicate": predicate,
                    "object": obj,
                    "chunk_id": chunk_id,
                    "evidence": str(triple.get("evidence", "")),
                    "confidence": triple.get("confidence"),
                }
            )
    return result


def write_mapping_log(path: Path, mappings: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for mapping in mappings:
            stream.write(json.dumps(mapping, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_summary(path: Path, data: NormalizedData, changed_count: int) -> None:
    summary = {
        "source_entities": data.source_entity_count,
        "canonical_entities": len(data.entities),
        "merged_entities": data.merged_count,
        "changed_entities": changed_count,
        "edges": len(data.edges),
        "skipped_error_chunks": data.skipped_errors,
        "dropped_technology_uses": data.dropped_uses,
    }
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def connect(dsn: str):
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - 설치 오류 안내 경로
        raise RuntimeError(
            "psycopg가 필요합니다. python3 -m pip install -r requirements.txt 를 실행하세요."
        ) from exc
    return psycopg.connect(dsn)


def ensure_schema(connection) -> None:
    try:
        with connection.cursor() as cursor:
            try:
                cursor.execute("SELECT chunk_id FROM chunks LIMIT 0")
            except Exception as exc:
                raise RuntimeError(
                    "chunks(chunk_id) 테이블을 먼저 적재해야 entities/edges 스키마를 만들 수 있습니다."
                ) from exc
            for statement in SCHEMA_SQL.split(";"):
                if statement.strip():
                    cursor.execute(statement)
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def check_chunk_ids(connection, chunk_ids: set[str]) -> None:
    if not chunk_ids:
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT chunk_id FROM chunks WHERE chunk_id = ANY(%s)",
                (list(chunk_ids),),
            )
            existing = {row[0] for row in cursor.fetchall()}
    except Exception as exc:
        connection.rollback()
        raise RuntimeError(
            "chunks(chunk_id)를 조회하지 못했습니다. 청크 테이블을 먼저 적재했는지 확인하세요."
        ) from exc
    missing = sorted(chunk_ids - existing)
    if missing:
        preview = ", ".join(missing[:10])
        suffix = " ..." if len(missing) > 10 else ""
        raise RuntimeError(f"chunks 테이블에 없는 chunk_id {len(missing)}개: {preview}{suffix}")


def load_postgres(connection, data: NormalizedData, extraction_run: str) -> tuple[int, int]:
    from psycopg.types.json import Jsonb

    check_chunk_ids(connection, {edge["chunk_id"] for edge in data.edges})
    entity_rows = [
        (entity["entity_id"], entity["type"], entity["label"], Jsonb(entity["props"]))
        for entity in data.entities.values()
    ]
    edge_rows = [
        (
            edge["subject"],
            edge["predicate"],
            edge["object"],
            edge["chunk_id"],
            edge["evidence"],
            edge["confidence"],
            extraction_run,
        )
        for edge in data.edges
    ]
    try:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO entities (entity_id, type, label, props)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (entity_id) DO NOTHING
                """,
                entity_rows,
            )
            inserted_entities = cursor.rowcount
            cursor.executemany(
                """
                INSERT INTO edges
                    (subject, predicate, object, chunk_id, evidence, confidence, extraction_run)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (subject, predicate, object, chunk_id) DO NOTHING
                """,
                edge_rows,
            )
            inserted_edges = cursor.rowcount
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return inserted_entities, inserted_edges


def expand_kg_id(value: str) -> str:
    if not value.startswith("kg:"):
        raise ValueError(f"kg: IRI가 아닙니다: {value}")
    return KG_BASE + value[3:]


def export_rdf(connection, path: Path, rdf_format: str) -> int:
    """DB의 그래프를 직렬화한다. 근거와 chunk_id는 의도적으로 제외한다."""
    try:
        from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
    except ImportError as exc:  # pragma: no cover - 설치 오류 안내 경로
        raise RuntimeError(
            "rdflib가 필요합니다. python3 -m pip install -r requirements.txt 를 실행하세요."
        ) from exc

    graph = Graph()
    kg = Namespace(KG_BASE)
    graph.bind("kg", kg)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)

    with connection.cursor() as cursor:
        cursor.execute("SELECT entity_id, type, label FROM entities ORDER BY entity_id")
        for entity_id, entity_type, label in cursor.fetchall():
            subject = URIRef(expand_kg_id(entity_id))
            graph.add((subject, RDF.type, kg[entity_type]))
            graph.add((subject, RDFS.label, Literal(label)))

        cursor.execute("SELECT subject, predicate, object FROM edges ORDER BY id")
        for subject, predicate, obj in cursor.fetchall():
            rdf_object = URIRef(expand_kg_id(obj)) if predicate in IRI_PREDICATES else Literal(obj)
            graph.add((URIRef(expand_kg_id(subject)), kg[predicate], rdf_object))

    path.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=path, format=rdf_format, encoding="utf-8")
    return len(graph)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="추출 결과를 정규화해 Postgres에 적재하고 Turtle/JSON-LD로 내보냅니다."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dsn", default=os.environ.get("POSTGRES_DSN", DEFAULT_DSN))
    parser.add_argument("--mode", choices=("all", "load", "export"), default="all")
    parser.add_argument("--extraction-run", default=f"v0-{date.today().isoformat()}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not re.fullmatch(r"v0-\d{4}-\d{2}-\d{2}", args.extraction_run):
        print("오류: --extraction-run은 v0-YYYY-MM-DD 형식이어야 합니다.", file=sys.stderr)
        return 2

    data: NormalizedData | None = None
    if args.mode in {"all", "load"}:
        try:
            data = normalize_records(load_jsonl(args.input))
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"오류: 입력 정규화 실패: {exc}", file=sys.stderr)
            return 1
        log_path = args.output_dir / "entity-normalization.jsonl"
        write_mapping_log(log_path, data.mappings)
        changed = sum(
            mapping["old_id"] != mapping["new_id"]
            or clean_label(mapping["old_label"]) != mapping["new_label"]
            for mapping in data.mappings
        )
        summary_path = args.output_dir / "entity-normalization-summary.json"
        write_summary(summary_path, data, changed)
        print(
            f"정규화: 원본 엔티티 {data.source_entity_count}개 -> "
            f"고유 엔티티 {len(data.entities)}개 "
            f"(병합 {data.merged_count}개, 변경 {changed}개)"
        )
        print(
            f"엣지 {len(data.edges)}개, 오류 청크 제외 {data.skipped_errors}개, "
            f"관계 부족 TechnologyUse 제외 {data.dropped_uses}개"
        )
        print(f"매핑 로그: {log_path}")
        print(f"정규화 요약: {summary_path}")

    try:
        with connect(args.dsn) as connection:
            if args.mode in {"all", "load"}:
                ensure_schema(connection)
                assert data is not None
                inserted_entities, inserted_edges = load_postgres(
                    connection, data, args.extraction_run
                )
                print(
                    f"Postgres 적재: 엔티티 {inserted_entities}개, "
                    f"엣지 {inserted_edges}개 추가 ({args.extraction_run})"
                )

            if args.mode in {"all", "export"}:
                ttl_path = args.output_dir / "my-kg.ttl"
                jsonld_path = args.output_dir / "my-kg.jsonld"
                ttl_count = export_rdf(connection, ttl_path, "turtle")
                jsonld_count = export_rdf(connection, jsonld_path, "json-ld")
                print(f"RDF 내보내기: {ttl_path} ({ttl_count} triples)")
                print(f"RDF 내보내기: {jsonld_path} ({jsonld_count} triples)")
    except Exception as exc:
        print(f"오류: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
