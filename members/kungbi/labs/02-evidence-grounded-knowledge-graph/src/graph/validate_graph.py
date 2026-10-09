"""Publication copy: generic code; demo/test data are synthetic, not measured results."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


from graph.ids import make_identity_id

FORBIDDEN_PROPERTIES = {
    "slack_user_id", "github_account_id", "github_login", "commit_author_name",
    "commit_author_email", "commit_committer_name", "commit_committer_email",
    "canonical_arn", "account_id", "source_resource_id", "raw_message", "raw_body",
    "credential", "email", "real_name", "display_name", "username", "login", "handle",
}
EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


def load_identity_approvals(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("approval", {}).get("status") != "user_approved":
        raise ValueError("identity_approval_missing")
    mappings = data.get("mappings", [])
    if len({row.get("person_id") for row in mappings}) != len(mappings) or any(not row.get("person_id") for row in mappings):
        raise ValueError("identity_approval_count_invalid")
    if any(not row.get("slack_user_id") or not row.get("github_account_id") for row in mappings):
        raise ValueError("identity_mapping_incomplete")
    return mappings


def materialize_identity_graph(approvals: list[dict[str, Any]], dataset_id: str):
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    for row in approvals:
        person_id = row["person_id"]
        nodes[person_id] = {"id": person_id, "labels": ["Person"], "properties": {"dataset_id": dataset_id}}
        for source, source_id in (("slack", row["slack_user_id"]), ("github", row["github_account_id"])):
            identity_id = make_identity_id(source, source_id)
            nodes[identity_id] = {
                "id": identity_id, "labels": ["Identity"],
                "properties": {"dataset_id": dataset_id, "source_system": source},
            }
            edge_key = f"{identity_id}\0IDENTITY_OF\0{person_id}"
            edge_id = "edge:" + hashlib.sha256(edge_key.encode()).hexdigest()
            edges[edge_id] = {
                "edge_id": edge_id, "source_id": identity_id, "type": "IDENTITY_OF", "target_id": person_id,
                "properties": {
                    "dataset_id": dataset_id, "case_ids": [], "source_system": "user_approval",
                    "source_record_id": "conversation", "evidence_chunk_ids": [],
                    "evidence_quote": "User approved identity mapping.",
                    "extraction_method": "user_approval", "basis": "approved_cross_service_mapping",
                    "review_status": "approved", "confidence": "high",
                },
            }
    return list(nodes.values()), list(edges.values())


def validate_graph(nodes: list[dict], edges: list[dict], allowed_relationships: set[str], evidence_ids: set[str]):
    errors: list[str] = []
    node_ids = [row.get("id") for row in nodes]
    if len(node_ids) != len(set(node_ids)):
        errors.append("duplicate_node_id")
    known = set(node_ids)
    edge_ids: set[str] = set()
    endpoints: set[tuple[str, str, str]] = set()
    aws_node_ids = {n['id'] for n in nodes if 'AWSResource' in n.get('labels', [])}
    api_node_ids = {n['id'] for n in nodes if 'APIContract' in n.get('labels', [])}
    node_labels = {n['id']: set(n.get('labels', [])) for n in nodes}
    for node in nodes:
        if node.get('id') in api_node_ids:
            props = node.get('properties') or {}
            if (not props.get('service') or props.get('method') not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}
                    or not re.fullmatch(r'/[A-Za-z0-9_/-]+', props.get('path', ''))
                    or props.get('path_scope') != 'controller_relative'
                    or props.get('caller_path_scope') != 'axios_baseURL_relative'
                    or props.get('global_prefix_status') != 'unknown'
                    or props.get('runtime_deployment_proven') is not False):
                errors.append('api_node_contract_invalid')
            chunks = props.get('evidence_chunk_ids') or []
            if not chunks or not set(chunks) <= evidence_ids:
                errors.append('api_node_evidence_missing_or_unknown')
        if node.get('id') in aws_node_ids:
            props = node.get('properties') or {}
            chunks = props.get('evidence_chunk_ids') or []
            if not chunks or not set(chunks) <= evidence_ids:
                errors.append('aws_node_evidence_missing_or_unknown')
            allowed_aws_props = {'dataset_id', 'resource_type', 'anonymous_label', 'source_system',
                                 'source_record_id', 'evidence_chunk_ids'}
            if not set(props) <= allowed_aws_props or re.search(r'arn:|\b\d{12}\b', json.dumps(node)):
                errors.append('aws_private_value')
        for key in (node.get("properties") or {}):
            if key in FORBIDDEN_PROPERTIES:
                errors.append(f"private_field:{key}")
    for edge in edges:
        edge_id = edge.get("edge_id", "")
        if edge_id in edge_ids:
            errors.append(f"duplicate_edge_id:{edge_id}")
        edge_ids.add(edge_id)
        endpoint = (str(edge.get("source_id")), str(edge.get("type")), str(edge.get("target_id")))
        if endpoint in endpoints:
            errors.append(f"duplicate_edge:{edge_id}")
        endpoints.add(endpoint)
        if edge.get("type") not in allowed_relationships:
            errors.append(f"invalid_relationship:{edge.get('type')}")
        if edge.get("source_id") not in known:
            errors.append(f"dangling_source:{edge.get('source_id')}")
        if edge.get("target_id") not in known:
            errors.append(f"dangling_target:{edge.get('target_id')}")
        props = edge.get("properties") or {}
        if edge.get('source_id') in api_node_ids or edge.get('target_id') in api_node_ids:
            rel = edge.get('type')
            allowed_sources = {'INCLUDES': {'Case'}, 'IMPLEMENTS': {'PullRequest', 'CodeFile'},
                               'CALLS_WITH': {'CodeFile'}}
            if (edge.get('target_id') not in api_node_ids or rel not in allowed_sources
                    or not node_labels.get(edge.get('source_id'), set()) & allowed_sources.get(rel, set())):
                errors.append('api_edge_endpoints_invalid')
            if not props.get('evidence_chunk_ids'):
                errors.append('api_edge_evidence_missing')
        if edge.get('source_id') in aws_node_ids or edge.get('target_id') in aws_node_ids:
            if not props.get('evidence_chunk_ids'):
                errors.append('aws_edge_evidence_missing')
            if re.search(r'arn:|\b\d{12}\b', json.dumps(edge)):
                errors.append('aws_private_value')
        for key in props:
            if key in FORBIDDEN_PROPERTIES:
                errors.append(f"private_field:{key}")
        for field in ("dataset_id", "case_ids", "source_system", "source_record_id", "evidence_chunk_ids",
                      "evidence_quote", "extraction_method", "basis", "review_status", "confidence"):
            if field not in props:
                errors.append(f"missing_provenance_field:{edge_id}:{field}")
        if props.get("extraction_method") != "curated_manifest" and props.get("extraction_method") != "user_approval":
            if not props.get("source_record_id") or not props.get("evidence_quote"):
                errors.append(f"missing_provenance:{edge_id}")
            if props.get("evidence_chunk_ids") and not set(props["evidence_chunk_ids"]) <= evidence_ids:
                errors.append(f"unknown_evidence_chunk:{edge_id}")
        if props.get("confidence") not in {"high", "medium", "low"}:
            errors.append(f"invalid_confidence:{edge_id}")
        if edge.get("type") == "IDENTITY_OF" and props.get("review_status") != "approved":
            errors.append(f"unapproved_identity_merge:{edge_id}")
        if props.get("basis") == "aws_runtime_delivery" and props.get("source_system") not in {"cloudwatch", "xray", "eventbridge_logs", "sqs_logs"}:
            errors.append(f"unsupported_runtime_delivery_claim:{edge_id}")
    return {"valid": not errors, "errors": errors, "node_count": len(nodes), "edge_count": len(edges)}


def write_approved(nodes: list[dict], edges: list[dict], output_dir: Path, allowed_relationships: set[str], evidence_ids: set[str]):
    report = validate_graph(nodes, edges, allowed_relationships, evidence_ids)
    if not report["valid"]:
        raise ValueError(json.dumps(report, sort_keys=True))
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, rows in (("nodes.jsonl", nodes), ("edges.jsonl", edges)):
        (output_dir / filename).write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    (output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
