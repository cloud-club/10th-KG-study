"""추출 결과를 RDF Turtle 파일로 내보낸다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote


LAB_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = LAB_ROOT / "outputs/triples.jsonl"
DEFAULT_OUTPUT = LAB_ROOT / "outputs/knowledge_graph.ttl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def escape_literal(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def entity_uri(entity_type: str, name: str) -> str:
    return f"os:{quote(entity_type + '-' + name, safe='')}"


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"추출 결과를 찾지 못했습니다: {args.input}")
    with args.input.open(encoding="utf-8") as input_file:
        rows = [json.loads(line) for line in input_file if line.strip()]

    entity_lookup: dict[str, str] = {}
    triples: list[str] = []
    statements: list[str] = []
    for row in rows:
        for entity in row["entities"]:
            uri = entity_uri(entity["type"], entity["name"])
            entity_lookup[entity["name"]] = uri
            triples.append(
                f'{uri} a os:{entity["type"]} ; '
                f'rdfs:label "{escape_literal(entity["name"])}"@ko .'
            )

        for relation in row["relations"]:
            subject = entity_lookup.get(relation["subject"])
            object_uri = entity_lookup.get(relation["object"])
            if not subject or not object_uri:
                continue
            predicate = f'os:{relation["predicate"].lower()}'
            triples.append(f"{subject} {predicate} {object_uri} .")
            statement_key = "\x1f".join(
                [row["chunk_id"], relation["subject"], relation["predicate"], relation["object"]]
            )
            statement_id = hashlib.sha256(statement_key.encode()).hexdigest()[:16]
            statements.append(
                f"os:statement-{statement_id} a rdf:Statement ;\n"
                f"    rdf:subject {subject} ;\n"
                f"    rdf:predicate {predicate} ;\n"
                f"    rdf:object {object_uri} ;\n"
                f'    os:chunkId "{escape_literal(row["chunk_id"])}" ;\n'
                f'    os:evidence "{escape_literal(relation["evidence"])}"@ko .'
            )

    prefixes = """@prefix os: <https://example.org/os/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    unique_triples = list(dict.fromkeys(triples))
    content = prefixes + "\n".join(unique_triples)
    if statements:
        content += "\n\n" + "\n\n".join(statements)
    args.output.write_text(content + "\n", encoding="utf-8")
    print(f"RDF 트리플: {len(unique_triples)}개")
    print(f"근거 문장: {len(statements)}개")
    print(f"결과: {args.output}")


if __name__ == "__main__":
    main()
