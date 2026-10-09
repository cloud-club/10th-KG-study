"""Curated exact literal HTTP contracts, revalidated against PR diffs and pinned git.

Retrieval code chunks contain symbol locators, not source bodies: read the exact
commit/file from the local mirror, and cite only matching commit/file chunks.
No deployment, baseURL resolution, or runtime request is asserted.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def validate_endpoint_proof(*, method, prefix, suffix, path, backend_patch,
                            backend_source, openapi_patch, caller_patches,
                            caller_source):
    # This deliberately narrow proof does not normalize parameters or evaluate JS.
    if method not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}:
        raise ValueError('api_method_unsupported')
    if not all(re.fullmatch(r'[A-Za-z0-9_/-]+', s or '') for s in (prefix, suffix)):
        raise ValueError('api_dynamic_route_unsupported')
    resolved = '/' + prefix.strip('/') + '/' + suffix.strip('/')
    if path != resolved:
        raise ValueError('api_route_scope_mismatch')
    # Tokenize quoted literals first so comment removal cannot consume a URL/string.
    def code(text):
        return re.sub(r'''('(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`)|//[^\n]*|/\*.*?\*/''',
                      lambda m: m.group(1) or '', text, flags=re.S)
    backend_source, caller_source = code(backend_source), code(caller_source)
    controller = r'@Controller\(\s*([\'\"])' + re.escape(prefix) + r'\1\s*\)'
    decorator = r'@' + method.title() + r'\(\s*([\'\"])' + re.escape(suffix) + r'\1\s*\)'
    if len(re.findall(r'@Controller\(', backend_source)) != 1 or not re.search(controller, backend_source):
        raise ValueError('api_controller_prefix_mismatch')
    if not re.search(decorator, backend_source):
        raise ValueError('api_snapshot_method_path_mismatch')
    added = lambda patch: code('\n'.join(l[1:] for l in patch.splitlines() if l.startswith('+') and not l.startswith('+++')))
    if not re.search(decorator, added(backend_patch)):
        raise ValueError('api_authored_method_missing')
    # PR OpenAPI corroborates the historical full route; snapshot prefix alone is not historical proof.
    openapi = r'"' + re.escape(path) + r'"\s*:\s*\{\s*"' + method.lower() + r'"\s*:\s*\{'
    if not re.search(openapi, added(openapi_patch)):
        raise ValueError('api_authored_openapi_mismatch')
    call = r'\bclient\.' + method.lower() + r'(?:<[^;\n]+?>)?\(\s*([\'\"])' + re.escape(path) + r'\1\s*[,)]'
    if not caller_patches or any(not re.search(call, added(p)) for p in caller_patches):
        raise ValueError('api_authored_caller_mismatch')
    if not re.search(call, caller_source):
        raise ValueError('api_snapshot_caller_mismatch')
    if not re.search(r'\bconst\s+client\s*=\s*axios\.create\(\s*\{[^}]*\bbaseURL\s*:\s*API_URL\b', caller_source, re.S):
        raise ValueError('api_caller_base_scope_unsupported')
    return resolved


def add_api_contracts(source_paths: dict[str, Path], nodes: dict, edges: dict,
                      selected_pr_cases: dict[str, set[str]]) -> dict:
    from graph.build_graph import ROOT, _jsonl, _node, _edge, _opaque, normalize_repository

    bindings_path = source_paths['api_bindings']
    if bindings_path.stat().st_mode & 0o077:
        raise ValueError('api_bindings_permissions_invalid')
    bindings = json.loads(bindings_path.read_text())['bindings']
    git_chunks = list(_jsonl(source_paths['git_chunks']))
    github_chunks = {}
    for c in _jsonl(source_paths['github_chunks']):
        cite = c.get('citation') or {}
        if cite.get('item_type') == 'pull_request':
            k = normalize_repository(cite.get('repository', '')) + '#' + str(cite.get('item_number'))
            github_chunks.setdefault(k, set()).add(c['retrieval_chunk_id'])

    def key(pr):
        repo, number = pr.rsplit('#', 1)
        return normalize_repository(repo) + '#' + str(int(number))

    def patch(pr, path):
        repo, number = pr.rsplit('#', 1)
        matches = []
        for d in source_paths['github_payload_root'].iterdir():
            if d.is_dir() and normalize_repository(d.name) == normalize_repository(repo):
                for row in _jsonl(d / 'pull-files.jsonl'):
                    raw = row.get('raw') or {}
                    if row.get('pull_number') == int(number) and raw.get('filename') == path:
                        matches.append(raw.get('patch', ''))
        if len(matches) != 1 or not matches[0] or not github_chunks.get(key(pr)):
            raise ValueError('api_selected_patch_or_chunk_missing')
        return matches[0]

    def snapshot(pr, path, mirror):
        repo = normalize_repository(pr.rsplit('#', 1)[0])
        chunks = [c for c in git_chunks if normalize_repository(c['citation'].get('repository', '')) == repo
                  and c['citation'].get('file_path') == path]
        commits = {c['citation'].get('commit_sha') for c in chunks}
        if len(commits) != 1:
            raise ValueError('api_snapshot_revision_ambiguous_or_missing')
        sha = next(iter(commits))
        if not re.fullmatch(r'[0-9a-f]{40}', sha or '') or path.startswith('/') or '..' in Path(path).parts:
            raise ValueError('api_snapshot_locator_invalid')
        mirror_path = (ROOT / mirror).resolve()
        if not mirror_path.is_relative_to((ROOT.parent / 'git/mirrors').resolve()):
            raise ValueError('api_snapshot_mirror_outside_local_scope')
        try:
            text = subprocess.check_output(['git', '--git-dir', str(mirror_path), 'show', sha + ':' + path],
                                           text=True, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            raise ValueError('api_snapshot_source_missing') from None
        return text, {c['retrieval_chunk_id'] for c in chunks}, sha

    endpoint_ids, caller_pr_keys = set(), set()
    for b in bindings:
        backend, caller = b['backend'], b['caller']
        case_id, backend_key = b['case_id'], key(backend['pull_request'])
        caller_keys = [key(p) for p in caller['pull_requests']]
        if not caller_keys or len(caller_keys) != len(set(caller_keys)):
            raise ValueError('api_caller_selection_invalid')
        for pr_key in [backend_key] + caller_keys:
            if case_id not in selected_pr_cases.get(pr_key, set()):
                raise ValueError('api_binding_outside_selected_case')
        backend_repo = backend_key.rsplit('#', 1)[0]
        caller_repo = caller_keys[0].rsplit('#', 1)[0]
        if any(k.rsplit('#', 1)[0] != caller_repo for k in caller_keys):
            raise ValueError('api_caller_repository_ambiguous')
        backend_file = f"file:{backend_repo}:{backend['file_path']}"
        caller_file = f"file:{caller_repo}:{caller['file_path']}"
        if backend_file not in nodes or caller_file not in nodes or case_id not in nodes:
            raise ValueError('api_binding_source_node_missing')
        backend_text, backend_ids, backend_sha = snapshot(backend['pull_request'], backend['file_path'], backend['mirror'])
        caller_text, caller_ids, caller_sha = snapshot(caller['pull_requests'][0], caller['file_path'], caller['mirror'])
        path = validate_endpoint_proof(method=b['method'], prefix=b['prefix'], suffix=b['suffix'], path=b['path'],
                                      backend_patch=patch(backend['pull_request'], backend['file_path']),
                                      backend_source=backend_text,
                                      openapi_patch=patch(backend['pull_request'], backend['openapi_file']),
                                      caller_patches=[patch(p, caller['file_path']) for p in caller['pull_requests']],
                                      caller_source=caller_text)
        api_id = _opaque('api', '\0'.join((b['service'], b['method'], path)))
        implementation_ids = backend_ids | github_chunks[backend_key]
        calls_ids = caller_ids | set().union(*(github_chunks[k] for k in caller_keys)) | implementation_ids
        _node(nodes, api_id, 'APIContract', service=b['service'], service_role='backend', method=b['method'], path=path,
              path_scope='controller_relative', caller_path_scope='axios_baseURL_relative',
              global_prefix_status='unknown', runtime_deployment_proven=False,
              evidence_chunk_ids=sorted(implementation_ids | caller_ids),
              source_system='selected_pr_patch_and_pinned_git_snapshot',
              source_record_id=_opaque('api_source', backend_key + '\0' + backend_sha),
              route_prefix_basis='pinned_snapshot_controller_literal_and_authored_openapi')
        endpoint_ids.add(api_id); caller_pr_keys.update(caller_keys)
        _edge(edges, case_id, 'INCLUDES', api_id, case_ids={case_id}, source_system='curated_manifest',
              source_record_id=case_id, evidence_chunk_ids=implementation_ids,
              evidence_quote='Exact source-grounded HTTP contract in selected investigation scope.',
              extraction_method='curated_manifest', basis='study_scope_membership')
        for source_id, basis in [('github:' + backend_key, 'authored_route_addition_and_openapi'),
                                 (backend_file, 'pinned_snapshot_route_implementation')]:
            _edge(edges, source_id, 'IMPLEMENTS', api_id, case_ids={case_id},
                  source_system='selected_pr_patch_and_pinned_git_snapshot',
                  source_record_id=_opaque('api_implementation', backend_key + '\0' + backend_sha),
                  evidence_chunk_ids=implementation_ids,
                  evidence_quote='Selected PR adds the method decorator and exact OpenAPI route; pinned snapshot confirms literal controller prefix and handler. Global runtime prefix and deployment unknown.',
                  extraction_method='revalidated_exact_literal_http_route', basis=basis)
        _edge(edges, caller_file, 'CALLS_WITH', api_id, case_ids={case_id},
              source_system='selected_pr_patch_and_pinned_git_snapshot',
              source_record_id=_opaque('api_call', '\0'.join(caller_keys) + '\0' + caller_sha),
              evidence_chunk_ids=calls_ids,
              evidence_quote='Selected frontend PR patches add an exact method/path call on an axios client; pinned snapshot confirms it. Path is relative to unresolved API_URL baseURL; runtime requests are not observed.',
              extraction_method='revalidated_exact_literal_http_call', basis='authored_call_and_pinned_snapshot_exact_contract')
    return dict(binding_count=len(bindings), endpoint_count=len(endpoint_ids), service_roles=['backend', 'frontend'],
                authored_caller_pr_count=len(caller_pr_keys), path_scope='controller_relative',
                caller_path_scope='axios_baseURL_relative', global_prefix_proven=False,
                runtime_deployment_proven=False, parameter_normalization_used=False)
