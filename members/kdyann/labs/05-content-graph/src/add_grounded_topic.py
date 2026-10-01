"""Add one evidence-backed Post→Topic assertion to an existing W5 export."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

import pipeline


def add_topic(output: Path, source_id: str, topic: str, evidence: str,
              start: int | None = None) -> dict[str, int | bool]:
    documents = pipeline._read_jsonl(output / "documents.jsonl")
    facts = pipeline._read_jsonl(output / "facts.jsonl")
    matches = [document for document in documents if document.get("id") == source_id]
    if len(matches) != 1:
        raise pipeline.ValidationError(f"문서 ID {source_id!r}는 정확히 한 번 있어야 합니다.")
    document = matches[0]
    caption = document["text"]
    if not evidence:
        raise pipeline.ValidationError("근거 문자열을 입력하세요.")
    positions = []
    pos = caption.find(evidence)
    while pos >= 0:
        positions.append(pos)
        pos = caption.find(evidence, pos + 1)
    if start is None and len(positions) != 1:
        raise pipeline.ValidationError("근거가 없거나 여러 번 나옵니다. 정확한 --start 오프셋을 지정하세요.")
    if start is not None and start not in positions:
        raise pipeline.ValidationError("--start 위치의 문자열이 원문 근거와 일치하지 않습니다.")

    assertion = {
        "subject_type": "Post", "subject_name": source_id,
        "predicate": "coversTopic", "object_type": "Topic",
        "object_name": topic, "evidence": evidence,
    }
    checked = pipeline.validate(document, {"facts": [assertion]})[0]
    checked["start"] = positions[0] if start is None else start
    checked["end"] = checked["start"] + len(evidence)
    if any(fact.get("source_id") == source_id and fact.get("predicate") == "coversTopic"
           and fact.get("object_type") == "Topic"
           and pipeline._node_id("Topic", fact.get("object_name", "")) == pipeline._node_id("Topic", topic)
           for fact in facts):
        return {"documents": len(documents), "facts": len(facts), "added": False}

    # Validate the existing export before rewriting any of its files.
    captions = {row["id"]: row["text"] for row in documents}
    for fact in facts:
        source = fact.get("source_id")
        if source not in captions or captions[source][fact["start"]:fact["end"]] != fact["evidence"]:
            raise pipeline.ValidationError("기존 사실에 원문과 일치하지 않는 근거가 있습니다.")
    facts.append(checked)
    triples = pipeline._triples(documents, facts)
    payloads = {
        "facts.jsonl": "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in facts),
        "graph.ttl": pipeline.serialize_turtle(triples),
        "graph.jsonld": pipeline.serialize_jsonld(triples),
    }
    with tempfile.TemporaryDirectory(prefix=".topic-", dir=output) as tmp:
        staging = Path(tmp)
        for name, body in payloads.items():
            (staging / name).write_text(body, encoding="utf-8")
        for name in payloads:
            os.replace(staging / name, output / name)
    return {"documents": len(documents), "facts": len(facts), "added": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="기존 W5 내보내기 폴더")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--evidence", required=True, help="캡션에 등장하는 정확한 연속 문자열")
    parser.add_argument("--start", type=int, help="근거가 여러 번 나올 때의 0 기준 문자 오프셋")
    args = parser.parse_args()
    print(json.dumps(add_topic(args.output, args.source_id, args.topic, args.evidence, args.start),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
