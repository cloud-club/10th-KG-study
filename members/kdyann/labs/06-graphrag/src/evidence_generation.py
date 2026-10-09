"""LLM은 근거 ID만 고르고, 인용문은 검증된 컨텍스트에서 코드가 복원한다."""
from __future__ import annotations

from typing import Any

from rag_agent import EvidenceError

SCHEMA = {"type": "object", "properties": {
    "claims": {"type": "array", "items": {"type": "object", "properties": {
        "text": {"type": "string"}, "evidence_ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["text", "evidence_ids"], "additionalProperties": False}},
    "unresolved": {"type": "array", "items": {"type": "string"}}},
    "required": ["claims", "unresolved"], "additionalProperties": False}


def catalog_for(context: dict[str, Any]) -> list[dict[str, str]]:
    return [{"evidence_id": f"E{index:02d}", "source_id": source["source_id"],
             "provenance": source["corpus"], "text": source["excerpt"]}
            for index, source in enumerate(context["sources"], 1)]


def prompt_input(context: dict[str, Any]) -> dict[str, Any]:
    return {"question": context["question"], "evidence_catalog": catalog_for(context)}


def assemble_answer(raw: Any, context: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != {"claims", "unresolved"}:
        raise EvidenceError("근거 ID 답변 JSON 형식이 올바르지 않습니다.")
    catalog = {item["evidence_id"]: item for item in catalog_for(context)}
    if not isinstance(raw["claims"], list) or not isinstance(raw["unresolved"], list):
        raise EvidenceError("근거 ID 답변 목록 형식이 올바르지 않습니다.")
    claims = []
    for claim in raw["claims"]:
        if (not isinstance(claim, dict) or set(claim) != {"text", "evidence_ids"}
                or not isinstance(claim["text"], str) or not claim["text"].strip()
                or not isinstance(claim["evidence_ids"], list)
                or not 1 <= len(claim["evidence_ids"]) <= 10):
            raise EvidenceError("주장과 근거 ID 형식이 올바르지 않습니다.")
        selected = []
        for identifier in claim["evidence_ids"]:
            if not isinstance(identifier, str) or identifier not in catalog:
                raise EvidenceError("컨텍스트에 없는 근거 ID입니다.")
            item = catalog[identifier]
            selected.append({"source_id": item["source_id"], "quote": item["text"]})
        claims.append({"text": claim["text"], "evidence": selected})
    return {"claims": claims, "unresolved": raw["unresolved"]}
