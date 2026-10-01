"""비공개 평가 JSONL을 검증하고 코퍼스 변경을 감지한다."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from models import SearchFilters

_SHA1 = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class EvidenceGroup:
    evidence_id: str
    acceptable_content_hashes: tuple[str, ...]


@dataclass(frozen=True)
class EvalQuestion:
    qid: str
    question: str
    category: str
    filters: SearchFilters
    answerable: bool
    retrieval_evaluable: bool
    gold_evidence: tuple[EvidenceGroup, ...]
    reference_answer: str | None
    failure_tags: tuple[str, ...]

    @property
    def evidence_groups(self) -> tuple[tuple[str, ...], ...]:
        return tuple(group.acceptable_content_hashes for group in self.gold_evidence)

    @property
    def all_gold_hashes(self) -> set[str]:
        return {
            content_hash
            for group in self.gold_evidence
            for content_hash in group.acceptable_content_hashes
        }


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def parse_question(data: dict) -> EvalQuestion:
    if data.get("schema_version") != 1:
        raise ValueError("schema_version은 1이어야 합니다.")
    qid = str(data.get("qid", "")).strip()
    question = str(data.get("question", "")).strip()
    category = str(data.get("category", "")).strip()
    if not qid or not question or not category:
        raise ValueError("qid, question, category는 필수입니다.")

    raw_filters = data.get("filters") or {}
    filters = SearchFilters(
        room=raw_filters.get("room") or None,
        date_from=_parse_datetime(raw_filters.get("date_from")),
        date_to=_parse_datetime(raw_filters.get("date_to")),
    )
    if filters.date_from and filters.date_to and filters.date_from >= filters.date_to:
        raise ValueError(f"{qid}: date_from은 date_to보다 앞서야 합니다.")

    groups: list[EvidenceGroup] = []
    seen_ids: set[str] = set()
    for raw_group in data.get("gold_evidence") or []:
        evidence_id = str(raw_group.get("evidence_id", "")).strip()
        hashes = tuple(dict.fromkeys(raw_group.get("acceptable_content_hashes") or []))
        if not evidence_id or evidence_id in seen_ids:
            raise ValueError(f"{qid}: evidence_id가 비었거나 중복됐습니다.")
        if not hashes or any(not _SHA1.fullmatch(value) for value in hashes):
            raise ValueError(f"{qid}/{evidence_id}: content_hash는 40자 소문자 SHA-1이어야 합니다.")
        seen_ids.add(evidence_id)
        groups.append(EvidenceGroup(evidence_id, hashes))

    answerable = bool(data.get("answerable", True))
    retrieval_evaluable = bool(data.get("retrieval_evaluable", True))
    if not answerable and groups:
        raise ValueError(f"{qid}: answerable=false 질문에는 gold_evidence를 둘 수 없습니다.")
    if answerable and retrieval_evaluable and not groups:
        raise ValueError(f"{qid}: 검색 평가 대상에는 gold_evidence가 필요합니다.")

    return EvalQuestion(
        qid=qid,
        question=question,
        category=category,
        filters=filters,
        answerable=answerable,
        retrieval_evaluable=retrieval_evaluable,
        gold_evidence=tuple(groups),
        reference_answer=data.get("reference_answer"),
        failure_tags=tuple(data.get("failure_tags") or []),
    )


def load_eval_set(path: Path) -> list[EvalQuestion]:
    questions: list[EvalQuestion] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                question = parse_question(json.loads(line))
            except Exception as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
            if question.qid in seen:
                raise ValueError(f"{path}:{line_number}: 중복 qid {question.qid}")
            seen.add(question.qid)
            questions.append(question)
    return questions


def corpus_manifest(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT content_hash FROM chunks ORDER BY content_hash")
        hashes = [row[0] for row in cur.fetchall()]
    digest = hashlib.sha256("\n".join(hashes).encode("utf-8")).hexdigest()
    return {"chunk_count": len(hashes), "content_hash_fingerprint": digest}


def assert_gold_exists(conn, questions: list[EvalQuestion]) -> None:
    gold = sorted({value for question in questions for value in question.all_gold_hashes})
    if not gold:
        return
    with conn.cursor() as cur:
        cur.execute("SELECT content_hash FROM chunks WHERE content_hash = ANY(%s)", (gold,))
        found = {row[0] for row in cur.fetchall()}
    missing = sorted(set(gold) - found)
    if missing:
        raise RuntimeError(
            f"평가셋의 gold hash {len(missing)}개가 현재 코퍼스에 없습니다. "
            "0점 처리하지 말고 코퍼스/청킹 버전을 확인해 다시 라벨링하세요."
        )
