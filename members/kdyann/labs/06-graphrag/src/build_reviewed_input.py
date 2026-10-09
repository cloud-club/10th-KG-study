"""W5의 내 글 13건과 W6에서 검토한 참고 글만 추출 입력으로 묶는다."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
LAB = Path(__file__).resolve().parents[1]
W5 = LAB.parent / "05-content-graph"
sys.path.insert(0, str(W5 / "src"))
from pipeline import ValidationError, _read_jsonl, validate  # noqa: E402
from language_policy import validate_language


def build(own_documents: list[dict], old_facts: list[dict], reference_documents: list[dict],
          reviewed: dict, current_own_documents: list[dict] | None = None,
          own_additions: dict | None = None) -> tuple[list[dict], list[dict]]:
    own = [row for row in own_documents if row.get("corpus") == "own"]
    if len(own) != 13 or len({row["id"] for row in own}) != 13:
        raise ValidationError("기존 검토본의 내 글 13건을 확인해 주세요.")
    additions = own_additions or {}
    available_own = {row["id"]: row for row in (current_own_documents or [])}
    baseline_ids = {row["id"] for row in own}
    new_ids = set(additions) - baseline_ids
    if new_ids - set(available_own):
        raise ValidationError(f"새 내 글 수집 파일에 없는 검토 게시물: {sorted(new_ids - set(available_own))}")
    for source_id in additions:
        item = additions[source_id]
        if (not isinstance(item, dict) or set(item) != {"review_note", "facts"}
                or not isinstance(item["review_note"], str) or not item["review_note"].strip()
                or not isinstance(item["facts"], list) or not item["facts"]):
            raise ValidationError("내 글의 주제 보강에는 검토 사유와 사실이 필요합니다.")
    for source_id in sorted(new_ids):
        own.append({**available_own[source_id], "corpus": "own"})
    available = {row["id"]: row for row in reference_documents}
    if not reviewed or any(not isinstance(key, str) or not isinstance(value, dict)
                           or set(value) != {"language", "review_note", "facts"}
                           or value["language"] not in ("ko", "en")
                           or not isinstance(value["review_note"], str) or not value["review_note"].strip()
                           or not isinstance(value["facts"], list) or not value["facts"]
                           for key, value in reviewed.items()):
        raise ValidationError("검토한 참고 글의 ID·사유·사실 목록이 필요합니다.")
    missing = sorted(set(reviewed) - set(available))
    if missing:
        raise ValidationError(f"수집 파일에 없는 검토 게시물: {missing}")
    own_ids = {row["id"] for row in own}
    if own_ids & set(reviewed):
        raise ValidationError("내 글과 참고 글의 ID가 겹칩니다.")
    for source_id, item in reviewed.items():
        try:
            validate_language(available[source_id]["text"], item["language"], source_id)
            for fact in item["facts"]:
                if not isinstance(fact, dict):
                    raise ValueError(f"{source_id}: 사실은 JSON 객체여야 합니다.")
                for field in ("subject_name", "object_name", "evidence"):
                    value = fact.get(field)
                    if isinstance(value, str):
                        validate_language(value, item["language"], source_id)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
    by_source = {source_id: [] for source_id in own_ids}
    for fact in old_facts:
        source_id = fact.get("source_id")
        if source_id in own_ids:
            by_source[source_id].append({key: fact[key] for key in
                                         ("subject_type", "subject_name", "predicate", "object_type",
                                          "object_name", "evidence")})
    for source_id, item in additions.items():
        by_source[source_id].extend(item["facts"])
    docs = own + [{**available[source_id], "corpus": "reference",
                   "reviewed_language": reviewed[source_id]["language"]} for source_id in reviewed]
    predictions = [{"source_id": row["id"], "facts": by_source[row["id"]] if row["id"] in own_ids
                    else reviewed[row["id"]]["facts"]} for row in docs]
    for doc, prediction in zip(docs, predictions):
        validate(doc, {"facts": prediction["facts"]})
    return docs, predictions


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data/kdyann/processed/instagram_topic_documents.jsonl")
    parser.add_argument("--review", type=Path, default=LAB / "reviewed_references.json")
    parser.add_argument("--own-source", type=Path,
                        default=ROOT / "data/kdyann/processed/instagram_documents_w6.jsonl")
    parser.add_argument("--own-additions", type=Path, default=LAB / "reviewed_own_additions.json")
    parser.add_argument("--baseline", type=Path,
                        default=ROOT / "data/kdyann/processed/content_graph/reviewed-100likes-ai")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/kdyann/processed/content_graph/w6-reviewed-input")
    args = parser.parse_args()
    reviewed = json.loads(args.review.read_text(encoding="utf-8"))
    own_additions = json.loads(args.own_additions.read_text(encoding="utf-8"))
    documents, predictions = build(_read_jsonl(args.baseline / "documents.jsonl"),
                                   _read_jsonl(args.baseline / "facts.jsonl"),
                                   _read_jsonl(args.source), reviewed,
                                   _read_jsonl(args.own_source), own_additions)
    write_jsonl(args.output / "documents.jsonl", documents)
    write_jsonl(args.output / "predictions.jsonl", predictions)
    print(json.dumps({"own": len(documents) - len(reviewed), "reviewed_reference": len(reviewed),
                      "facts": sum(len(row["facts"]) for row in predictions)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
