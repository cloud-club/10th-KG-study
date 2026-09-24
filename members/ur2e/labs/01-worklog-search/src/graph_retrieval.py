"""작업기록 그래프에서 관련 원문 청크를 찾아 RAG 근거로 돌려준다."""

from __future__ import annotations

from typing import Any

from knowledge_graph import relevant_subgraph


def graph_evidence(
    query: str,
    graph: dict[str, list[dict[str, Any]]],
    chunks: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """질문과 관련된 그래프 노드의 출처 문서를 실제 청크로 연결한다."""
    subgraph = relevant_subgraph(graph, query)
    source_paths = {
        node["source_path"]
        for node in subgraph["nodes"]
        if node.get("source_path")
    }
    if not source_paths:
        return []

    # 문서 안에서는 짧은 heading 청크를 먼저 보여 주되 원래 파서 순서는 보존한다.
    matched = [chunk for chunk in chunks if chunk["source_path"] in source_paths]
    matched.sort(key=lambda chunk: (chunk["source_path"], chunk.get("heading") is None))
    return matched[:limit]


def merge_evidence(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """검색 근거를 우선 유지하고 그래프 근거를 중복 없이 보강한다."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in [*primary, *secondary]:
        chunk_id = chunk["chunk_id"]
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        merged.append(chunk)
        if len(merged) == limit:
            break
    return merged
