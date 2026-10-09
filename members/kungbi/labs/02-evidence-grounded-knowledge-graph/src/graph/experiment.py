"""Publication copy: generic code; demo/test data are synthetic, not measured results."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from graph.build_graph import normalize_repository


def artifact_key(record: dict[str, Any]) -> str:
    """Stable benchmark-level identity for GitHub artifacts and Slack threads."""
    source = str(record.get("source_system") or "")
    citation = record.get("citation") or {}
    if source == "github" and citation.get("item_number") is not None:
        repository = normalize_repository(str(citation.get("repository") or ""))
        item_type = str(citation.get("item_type") or "unknown")
        return f"github:{repository}:{item_type}:{int(citation['item_number'])}"
    if source == "slack" and citation.get("channel_id") and citation.get("thread_ts"):
        return f"slack:{citation['channel_id']}:{citation['thread_ts']}"
    if source == "git" and citation.get("stable_key"):
        return f"symbol:{citation['stable_key']}"
    if source == "aws" and citation.get("native_resource_id"):
        return f"aws:{citation['native_resource_id']}"
    return str(record.get("retrieval_chunk_id") or record.get("id") or "")


def lucene_or_query(text: str) -> str:
    tokens = re.findall(r"[0-9A-Za-z_]+|[가-힣]+", text)
    return " OR ".join(f'"{token}"' for token in tokens) or '"__no_match__"'


def retrieval_metrics(ranked_ids: list[str], gold_ids: set[str], cutoffs: tuple[int, ...] = (1, 3, 5, 10)) -> dict[str, Any]:
    deduped = list(dict.fromkeys(ranked_ids))
    if not gold_ids:
        return {"hit@1": 0, **{f"hit@{k}": 0 for k in cutoffs},
                **{f"recall@{k}": 0.0 for k in cutoffs}, "mrr": 0.0,
                "gold_count": 0, "unique_ranked_artifacts": len(deduped)}
    first = next((i for i, item in enumerate(deduped, 1) if item in gold_ids), None)
    result: dict[str, Any] = {"hit@1": int(first == 1), "mrr": 1.0 / first if first else 0.0,
                              "gold_count": len(gold_ids), "unique_ranked_artifacts": len(deduped)}
    for k in cutoffs:
        top = set(deduped[:k])
        result[f"hit@{k}"] = int(bool(top & gold_ids))
        result[f"recall@{k}"] = len(top & gold_ids) / len(gold_ids)
    return result


def merge_rrf_graph_results(seed: list[dict[str, Any]], expanded_ids: list[str], *, seed_limit: int = 5, limit: int = 10) -> list[dict[str, Any]]:
    """Keep top RRF seeds first; append novel graph-linked evidence IDs deterministically."""
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in seed[:seed_limit]:
        chunk_id = str(result.get("retrieval_chunk_id") or "")
        if chunk_id and chunk_id not in seen:
            seen.add(chunk_id)
            selected.append({**result, "retrieval_method": "rrf_seed"})
    for chunk_id in expanded_ids:
        identifier = str(chunk_id)
        if identifier and identifier not in seen:
            seen.add(identifier)
            selected.append({"retrieval_chunk_id": identifier, "retrieval_method": "graph_expansion"})
            if len(selected) >= limit:
                break
    return selected[:limit]


def aggregate_metrics(rows: list[dict[str, Any]], field: str = "metrics") -> dict[str, Any]:
    if not rows:
        return {"count": 0}
    keys = [k for k, value in rows[0][field].items() if isinstance(value, (int, float)) and not isinstance(value, bool)]
    summary: dict[str, Any] = {"count": len(rows)}
    for key in keys:
        summary[key] = sum(float(row[field][key]) for row in rows) / len(rows)
    return summary


def top_hit_sources(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("source_system") or "unknown") for row in rows))
