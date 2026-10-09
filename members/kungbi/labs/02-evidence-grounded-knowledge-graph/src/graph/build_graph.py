"""Publication copy: generic code; demo/test data are synthetic, not measured results."""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from graph.validate_graph import load_identity_approvals, materialize_identity_graph
from graph.api_contract import validate_endpoint_proof

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "fixtures/synthetic-manifest.json"
DATASET_ID = "synthetic-demo-v1"
PR_URL = re.compile(r"https?://(?:www\.)?github\.com/[^/]+/([^/]+)/pull/(\d+)", re.I)


def normalize_repository(repository: str) -> str:
    return repository.casefold().replace("-", "_")


def normalize_pr_link(value: str) -> tuple[str, int] | None:
    match = PR_URL.search(value)
    if not match:
        return None
    return normalize_repository(match.group(1)), int(match.group(2))


from graph.ids import make_identity_id


def unique_slack_threads(records: list[dict]) -> list[dict]:
    threads: dict[tuple[str, str], dict] = {}
    for record in records:
        key = (str(record["channel_id"]), str(record["thread_ts"]))
        threads.setdefault(key, record)
    return list(threads.values())


def _opaque(kind: str, key: str) -> str:
    return f"{kind}:{hashlib.sha256(key.encode()).hexdigest()}"


def _jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _read_jsonl(path: Path) -> list[dict]:
    return list(_jsonl(path))


def load_evidence_ids(source_paths: dict[str, Path]) -> set[str]:
    return {str(row['retrieval_chunk_id'])
            for key in ('slack_chunks', 'github_chunks', 'git_chunks', 'aws_chunks') if key in source_paths
            for row in _jsonl(source_paths[key]) if row.get('retrieval_chunk_id')}


def _pr_key(repo: str, number: int) -> tuple[str, int]:
    return normalize_repository(repo), int(number)


def _case_pr(value: str) -> tuple[str, int]:
    repo, number = value.rsplit("#", 1)
    return _pr_key(repo, int(number))


def _node(nodes: dict[str, dict], node_id: str, node_label: str, **properties: Any) -> None:
    candidate = {"id": node_id, "labels": [node_label], "properties": {"dataset_id": DATASET_ID, **properties}}
    current = nodes.get(node_id)
    if current is not None and current != candidate:
        raise ValueError(f"conflicting_node:{node_id}")
    nodes[node_id] = candidate


def _edge(edges: dict[tuple[str, str, str], dict], source: str, rel: str, target: str, *,
          case_ids: set[str], source_system: str, source_record_id: str,
          evidence_chunk_ids: set[str], evidence_quote: str, extraction_method: str,
          basis: str, review_status: str = "approved", confidence: str = "high") -> None:
    key = (source, rel, target)
    row = {
        "edge_id": _opaque("edge", "\0".join(key)), "source_id": source,
        "type": rel, "target_id": target,
        "properties": {
            "dataset_id": DATASET_ID, "case_ids": sorted(case_ids),
            "source_system": source_system, "source_record_id": source_record_id,
            "evidence_chunk_ids": sorted(evidence_chunk_ids),
            "evidence_quote": " ".join(evidence_quote.split())[:240],
            "extraction_method": extraction_method, "basis": basis,
            "review_status": review_status, "confidence": confidence,
        },
    }
    existing = edges.get(key)
    if existing is None:
        edges[key] = row
        return
    props = existing["properties"]
    props["case_ids"] = sorted(set(props["case_ids"]) | case_ids)
    props["evidence_chunk_ids"] = sorted(set(props["evidence_chunk_ids"]) | evidence_chunk_ids)


def build_graph(manifest_path: Path = MANIFEST_PATH) -> tuple[list[dict], list[dict], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_paths = {k: (ROOT / v).resolve() for k, v in manifest["source_paths"].items()}
    for key, path in source_paths.items():
        if not path.exists():
            raise FileNotFoundError(f"missing_source:{key}:{path.name}")

    cases = manifest["cases"]
    pr_cases: dict[tuple[str, int], set[str]] = defaultdict(set)
    thread_cases: dict[tuple[str, str], set[str]] = defaultdict(set)
    for case in cases:
        for value in case["pull_requests"]:
            pr_cases[_case_pr(value)].add(case["id"])
        for channel, timestamp in case["slack_threads"]:
            thread_cases[(str(channel), str(timestamp))].add(case["id"])

    nodes: dict[str, dict] = {}
    edges: dict[tuple[str, str, str], dict] = {}
    evidence_ids: set[str] = set()
    for case in cases:
        _node(nodes, case["id"], "Case", label=case["label"])

    slack_chunks: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for chunk in _jsonl(source_paths["slack_chunks"]):
        cite = chunk.get("citation") or {}
        key = (str(cite.get("channel_id", "")), str(cite.get("thread_ts", "")))
        if key in thread_cases:
            slack_chunks[key].append(chunk)
            evidence_ids.add(str(chunk["retrieval_chunk_id"]))

    github_chunks: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for chunk in _jsonl(source_paths["github_chunks"]):
        cite = chunk.get("citation") or {}
        if cite.get("item_type") != "pull_request" or cite.get("item_number") is None:
            continue
        key = _pr_key(str(cite.get("repository", "")), int(cite["item_number"]))
        if key in pr_cases:
            github_chunks[key].append(chunk)
            evidence_ids.add(str(chunk["retrieval_chunk_id"]))

    raw_slack = source_paths["slack_payload_root"]
    slack_users = {str(row.get("user_id", "")): row for row in _jsonl(raw_slack / "users.jsonl")}
    slack_messages: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for key in thread_cases:
        for path in sorted((raw_slack / "messages" / key[0]).glob("*.jsonl")):
            for row in _jsonl(path):
                if str(row.get("thread_ts", "")) == key[1]:
                    slack_messages[key].append(row)

    for thread_key, case_ids in thread_cases.items():
        if not slack_chunks.get(thread_key):
            raise ValueError(f"missing_slack_thread:{thread_key[0]}:{thread_key[1]}")
        thread_id = f"slack:{thread_key[0]}:{thread_key[1]}"
        _node(nodes, thread_id, "SlackThread", channel_id=thread_key[0], thread_ts=thread_key[1])
        for case_id in case_ids:
            _edge(edges, case_id, "INCLUDES", thread_id, case_ids={case_id}, source_system="curated_manifest",
                  source_record_id=case_id, evidence_chunk_ids=set(), evidence_quote="",
                  extraction_method="curated_manifest", basis="study_scope_membership")

    payload_root = source_paths["github_payload_root"]
    metadata: dict[tuple[str, int], dict] = {}
    commits: dict[tuple[str, int], list[dict]] = defaultdict(list)
    files: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for repo_dir in payload_root.iterdir():
        if not repo_dir.is_dir():
            continue
        for filename, target in (("pull-requests.jsonl", metadata),
                                 ("pull-commits.jsonl", commits),
                                 ("pull-files.jsonl", files)):
            path = repo_dir / filename
            if not path.exists():
                continue
            for row in _jsonl(path):
                number = row.get("item_number") if filename == "pull-requests.jsonl" else row.get("pull_number")
                if number is None:
                    continue
                key = _pr_key(str(row.get("repository", repo_dir.name)), int(number))
                if key in pr_cases:
                    if filename == "pull-requests.jsonl":
                        target[key] = row
                    else:
                        target[key].append(row)

    pr_authors: dict[str, set[str]] = defaultdict(set)
    for key, case_ids in pr_cases.items():
        if key not in metadata or not commits.get(key) or not files.get(key):
            raise ValueError(f"incomplete_pr_payload:{key}")
        repo, number = key
        pr_id = f"github:{repo}#{number}"
        _node(nodes, pr_id, "PullRequest", repository=repo, number=number)
        chunks = github_chunks.get(key, [])
        chunk_ids = {str(c["retrieval_chunk_id"]) for c in chunks if c.get("retrieval_chunk_id")}
        for case_id in case_ids:
            _edge(edges, case_id, "INCLUDES", pr_id, case_ids={case_id}, source_system="curated_manifest",
                  source_record_id=case_id, evidence_chunk_ids=set(), evidence_quote="",
                  extraction_method="curated_manifest", basis="study_scope_membership")

        author = ((metadata[key].get("raw") or {}).get("user") or {})
        github_id = str(author.get("id", ""))
        if github_id:
            pr_authors[github_id].add(pr_id)

        # These edges are directly supported by the selected GitHub collaboration payload.
        for row in commits[key]:
            raw = row.get("raw") or {}
            sha = str(raw.get("sha", ""))
            if not sha:
                continue
            commit_id = f"commit:{repo}:{sha}"
            _node(nodes, commit_id, "Commit", repository=repo, sha=sha)
            _edge(edges, pr_id, "INCLUDES_COMMIT", commit_id, case_ids=case_ids,
                  source_system="github_collaboration", source_record_id=f"{repo}:pull/{number}",
                  evidence_chunk_ids=chunk_ids, evidence_quote="Selected pull request includes this commit.",
                  extraction_method="github_payload", basis="pull_commits_payload")
            for role in ("author", "committer"):
                account = raw.get(role) or {}
                account_id = str(account.get("id", ""))
                if not account_id:
                    continue
                identity_id = make_identity_id(f"github_commit_{role}", account_id)
                _node(nodes, identity_id, "Identity", source_system=f"github_commit_{role}")
                relation = "COMMITTED_AS_AUTHOR" if role == "author" else "COMMITTED_AS_COMMITTER"
                _edge(edges, identity_id, relation, commit_id, case_ids=case_ids,
                      source_system="github_collaboration", source_record_id=f"{repo}:pull/{number}",
                      evidence_chunk_ids=chunk_ids, evidence_quote=f"GitHub payload marks a commit {role}.",
                      extraction_method="github_payload", basis=f"commit_{role}")

        for row in files[key]:
            path = str((row.get("raw") or {}).get("filename", ""))
            if not path or path.startswith("/") or ".." in Path(path).parts:
                continue
            file_id = f"file:{repo}:{path}"
            _node(nodes, file_id, "CodeFile", repository=repo, path=path)
            _edge(edges, pr_id, "CHANGES_FILE", file_id, case_ids=case_ids,
                  source_system="github_collaboration", source_record_id=f"{repo}:pull/{number}",
                  evidence_chunk_ids=chunk_ids, evidence_quote="Selected pull request lists this changed file.",
                  extraction_method="github_payload", basis="pull_files_payload")

    # Direct Slack PR URLs link separate source threads to their corresponding pull requests.
    for thread_key, messages in slack_messages.items():
        case_ids = thread_cases[thread_key]
        thread_id = f"slack:{thread_key[0]}:{thread_key[1]}"
        thread_evidence = {str(c["retrieval_chunk_id"]) for c in slack_chunks[thread_key] if c.get("retrieval_chunk_id")}
        for message in messages:
            text = str(message.get("text", ""))
            message_ts = str(message.get("message_ts", ""))
            user_id = str(message.get("user_id", ""))
            if not message_ts:
                continue
            for match in PR_URL.finditer(text):
                key = _pr_key(match.group(1), int(match.group(2)))
                if key not in pr_cases:
                    continue
                pr_id = f"github:{key[0]}#{key[1]}"
                source_record = f"{thread_key[0]}:{message_ts}"
                _edge(edges, thread_id, "LINKS_TO", pr_id, case_ids=case_ids,
                      source_system="slack_message", source_record_id=source_record,
                      evidence_chunk_ids=thread_evidence,
                      evidence_quote="Slack message contains an explicit selected pull-request URL.",
                      extraction_method="exact_url_match", basis="explicit_permalink")
                user = slack_users.get(user_id, {})
                if user_id and not user.get("is_bot") and not user.get("is_deleted"):
                    identity_id = make_identity_id("slack", user_id)
                    _node(nodes, identity_id, "Identity", source_system="slack")
                    _edge(edges, identity_id, "CONTRIBUTED_TO", pr_id, case_ids=case_ids,
                          source_system="slack_message", source_record_id=source_record,
                          evidence_chunk_ids=thread_evidence,
                          evidence_quote="Slack message author posted an explicit pull-request URL.",
                          extraction_method="message_author_with_permalink",
                          basis="explicit_message_author_and_permalink")

    # Only user-approved Slack ↔ GitHub PR-author identity pairs are merged as Person.
    approvals = load_identity_approvals(source_paths["identity_approvals"])
    identity_nodes, identity_edges = materialize_identity_graph(approvals, DATASET_ID)
    for node in identity_nodes:
        nodes[node["id"]] = node
    for edge in identity_edges:
        edges[(edge["source_id"], edge["type"], edge["target_id"])] = edge

    approved_github_ids = {str(row["github_account_id"]) for row in approvals}
    for github_id, pr_ids in pr_authors.items():
        if github_id not in approved_github_ids:
            continue
        identity_id = make_identity_id("github", github_id)
        _node(nodes, identity_id, "Identity", source_system="github")
        for pr_id in pr_ids:
            pr_num = int(pr_id.rsplit("#", 1)[1])
            pr_repo = pr_id.split(":", 1)[1].rsplit("#", 1)[0]
            key = (pr_repo, pr_num)
            case_ids = pr_cases[key]
            chunk_ids = {str(c["retrieval_chunk_id"]) for c in github_chunks.get(key, []) if c.get("retrieval_chunk_id")}
            _edge(edges, identity_id, "AUTHORED", pr_id, case_ids=case_ids,
                  source_system="github_collaboration", source_record_id=f"{pr_repo}:pull/{pr_num}",
                  evidence_chunk_ids=chunk_ids, evidence_quote="GitHub pull-request metadata identifies its author.",
                  extraction_method="github_pr_author_field", basis="selected_pr_author")

    aws_report = {}
    if 'aws_bindings' in source_paths:
        from graph.aws_snapshot import add_aws_snapshot
        aws_report = add_aws_snapshot(source_paths, nodes, edges,
                                      {f'{repo}#{num}': ids for (repo, num), ids in pr_cases.items()})
        evidence_ids.update(chunk for node in nodes.values() if 'AWSResource' in node['labels']
                            for chunk in node['properties']['evidence_chunk_ids'])
    api_report = {}
    if 'api_bindings' in source_paths:
        from graph.api_contract import add_api_contracts
        api_report = add_api_contracts(source_paths, nodes, edges,
                                      {f'{repo}#{num}': ids for (repo, num), ids in pr_cases.items()})
        evidence_ids.update(chunk for node in nodes.values() if 'APIContract' in node['labels']
                            for chunk in node['properties']['evidence_chunk_ids'])
    node_rows, edge_rows = list(nodes.values()), list(edges.values())
    report = {
        "dataset_id": DATASET_ID,
        "aws_snapshot": aws_report,
        "api_contracts": api_report,
        "source_snapshot": manifest["source_snapshot"],
        "case_count": len(cases),
        "selected_pr_count": len(pr_cases),
        "selected_thread_count": len(thread_cases),
        "threads_with_retrieval_evidence": len(slack_chunks),
        "selected_prs_with_metadata": len(metadata),
        "selected_prs_with_commits": len(commits),
        "selected_prs_with_changed_files": len(files),
        "approved_identity_mapping_count": len(approvals),
        "identity_nodes_added": len(identity_nodes),
        "identity_approval_edges_added": len(identity_edges),
        "evidence_chunk_count": len(evidence_ids),
        "node_count": len(node_rows),
        "edge_count": len(edge_rows),
    }
    return node_rows, edge_rows, report


def write_candidates(output_dir: Path | None = None) -> dict[str, Any]:
    from graph.validate_graph import validate_graph

    output_dir = output_dir or ROOT / "graph/candidates"
    nodes, edges, report = build_graph()
    schema = json.loads((ROOT / "graph/schema.json").read_text(encoding="utf-8"))
    allowed = set(schema["relationships"])
    manifest = json.loads(MANIFEST_PATH.read_text())
    evidence_ids = load_evidence_ids({key: (ROOT / value).resolve()
                                    for key, value in manifest['source_paths'].items()})
    validation = validate_graph(nodes, edges, allowed, evidence_ids)
    report["validation"] = validation
    if not validation["valid"]:
        raise ValueError(json.dumps(validation, sort_keys=True))
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, rows in (("nodes.jsonl", nodes), ("edges.jsonl", edges)):
        (output_dir / filename).write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(write_candidates(), ensure_ascii=False, indent=2))
