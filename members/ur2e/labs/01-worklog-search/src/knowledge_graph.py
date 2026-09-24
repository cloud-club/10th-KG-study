"""작업기록 지식 그래프 v1을 읽고 검증·검색·시각화한다."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


GRAPH_PATH = Path(__file__).resolve().parent.parent / "dataset/knowledge_graph.json"
TYPE_COLORS = {
    "Incident": "#ef4444",
    "System": "#3b82f6",
    "Symptom": "#f97316",
    "Cause": "#eab308",
    "Action": "#22c55e",
    "Decision": "#8b5cf6",
    "Todo": "#ec4899",
    "Document": "#64748b",
    "Chunk": "#94a3b8",
}


def load_graph(path: Path = GRAPH_PATH) -> dict[str, list[dict[str, Any]]]:
    graph = json.loads(path.read_text(encoding="utf-8"))
    validate_graph(graph)
    return graph


def validate_graph(graph: dict[str, list[dict[str, Any]]]) -> None:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    ids = [node.get("id") for node in nodes]
    if len(ids) != len(set(ids)):
        raise ValueError("그래프 노드 ID가 중복됩니다.")
    if any(not node_id for node_id in ids):
        raise ValueError("모든 그래프 노드에는 id가 필요합니다.")
    known = set(ids)
    for edge in edges:
        if edge.get("source") not in known or edge.get("target") not in known:
            raise ValueError(f"존재하지 않는 노드를 참조하는 엣지입니다: {edge}")
        if not edge.get("type"):
            raise ValueError(f"type이 없는 엣지입니다: {edge}")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[\w가-힣-]{2,}", text)}


def relevant_subgraph(
    graph: dict[str, list[dict[str, Any]]],
    query: str,
    max_seed_nodes: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """라벨·설명과 질문의 토큰이 겹치는 노드를 찾고 1-hop 이웃을 포함한다."""
    if not query.strip():
        return graph
    query_tokens = _tokens(query)
    scored = []
    for node in graph["nodes"]:
        haystack = " ".join(
            str(node.get(field, ""))
            for field in ("label", "description", "type", "source_path")
        )
        overlap = query_tokens & _tokens(haystack)
        if overlap:
            scored.append((len(overlap), node["id"]))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = {node_id for _, node_id in scored[:max_seed_nodes]}
    if not selected:
        return {"nodes": [], "edges": []}

    for edge in graph["edges"]:
        if edge["source"] in selected or edge["target"] in selected:
            selected.add(edge["source"])
            selected.add(edge["target"])
    return {
        "nodes": [node for node in graph["nodes"] if node["id"] in selected],
        "edges": [
            edge
            for edge in graph["edges"]
            if edge["source"] in selected and edge["target"] in selected
        ],
    }


def graphviz_dot(graph: dict[str, list[dict[str, Any]]]) -> str:
    lines = [
        "digraph worklog {",
        '  graph [rankdir="LR", bgcolor="transparent", pad="0.25"];',
        '  node [shape="box", style="rounded,filled", fontname="Arial", fontcolor="white"];',
        '  edge [fontname="Arial", fontsize="10", color="#94a3b8"];',
    ]
    for node in graph["nodes"]:
        node_id = json.dumps(node["id"], ensure_ascii=False)
        label = json.dumps(f"{node['label']}\n({node['type']})", ensure_ascii=False)
        color = TYPE_COLORS.get(node["type"], "#64748b")
        lines.append(f"  {node_id} [label={label}, fillcolor={json.dumps(color)}];")
    for edge in graph["edges"]:
        source = json.dumps(edge["source"], ensure_ascii=False)
        target = json.dumps(edge["target"], ensure_ascii=False)
        label = json.dumps(edge["type"], ensure_ascii=False)
        lines.append(f"  {source} -> {target} [label={label}];")
    lines.append("}")
    return "\n".join(lines)
