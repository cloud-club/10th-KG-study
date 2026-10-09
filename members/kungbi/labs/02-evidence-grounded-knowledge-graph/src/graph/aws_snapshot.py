"""Curated, re-validated local snapshot bindings; never infer runtime delivery."""
from __future__ import annotations

import json
import re
from pathlib import Path


def add_aws_snapshot(source_paths: dict[str, Path], nodes: dict, edges: dict,
                     selected_pr_cases: dict[str, set[str]]) -> dict:
    from graph.build_graph import _jsonl, _node, _edge, _opaque, normalize_repository

    resources = {r['resource_id']: r for r in _jsonl(source_paths['aws_resources'])}
    relations = list(_jsonl(source_paths['aws_relations']))
    aws_chunks = {}
    for chunk in _jsonl(source_paths['aws_chunks']):
        aws_chunks.setdefault(chunk['source_record_id'], set()).add(chunk['retrieval_chunk_id'])
    github_chunks = {}
    for chunk in _jsonl(source_paths['github_chunks']):
        cite = chunk.get('citation') or {}
        if cite.get('item_type') == 'pull_request':
            key = f"{normalize_repository(cite.get('repository', ''))}#{cite.get('item_number')}"
            github_chunks.setdefault(key, set()).add(chunk['retrieval_chunk_id'])
    bindings = json.loads(source_paths['aws_bindings'].read_text(encoding='utf-8'))['bindings']
    materialized = set()
    unresolved = set()
    for binding in bindings:
        case_id = binding['case_id']
        repo, number_text = binding['pull_request'].rsplit('#', 1)
        pr_key = f'{normalize_repository(repo)}#{int(number_text)}'
        file_id = f"file:{normalize_repository(repo)}:{binding['file_path']}"
        if case_id not in selected_pr_cases.get(pr_key, set()) or case_id not in nodes or file_id not in nodes:
            raise ValueError('aws_binding_outside_case')
        patches = []
        for repo_dir in source_paths['github_payload_root'].iterdir():
            if normalize_repository(repo_dir.name) != normalize_repository(repo):
                continue
            for row in _jsonl(repo_dir / 'pull-files.jsonl'):
                raw = row.get('raw') or {}
                if int(row.get('pull_number', -1)) == int(number_text) and raw.get('filename') == binding['file_path']:
                    patches.append(str(raw.get('patch', '')))
        # Require the actual selected PR patch to declare the exact event literals.
        if not any(all(re.search(r"\b" + symbol + r"\s*=\s*(['\"])" + re.escape(binding[field]) + r"\1", patch)
                       for symbol, field in [('SOURCE', 'source'), ('DETAIL_TYPE', 'detail_type')])
                   and 'Source: SOURCE' in patch and 'DetailType: DETAIL_TYPE' in patch
                   for patch in patches):
            raise ValueError('aws_code_contract_mismatch')
        if not github_chunks.get(pr_key):
            raise ValueError('aws_code_chunk_missing')
        rule = resources.get(binding['rule_resource_id'])
        bus = resources.get(binding['bus_resource_id'])
        if not rule or not bus or rule['resource_type'] != 'rule' or bus['resource_type'] != 'event_bus':
            raise ValueError('aws_resource_binding_missing')
        pattern = rule['configuration'].get('EventPattern', {})
        if isinstance(pattern, str):
            pattern = json.loads(pattern)
        # Exact simple contract only; richer/nested filtering needs separate review.
        expected = {'source': [binding['source']], 'detail-type': [binding['detail_type']]}
        if pattern != expected:
            raise ValueError('aws_event_contract_mismatch')
        same_bus = [r for r in resources.values() if r['resource_type'] == 'event_bus'
                    and r['resource_name'] == rule['configuration'].get('EventBusName')
                    and r['account_id'] == rule['account_id'] and r['region'] == rule['region']]
        if len(same_bus) != 1 or same_bus[0]['resource_id'] != bus['resource_id']:
            raise ValueError('aws_bus_scope_mismatch')
        for resource in (rule, bus):
            resource_id = resource['resource_id']
            if not aws_chunks.get(resource_id):
                raise ValueError('aws_snapshot_chunk_missing')
            node_id = _opaque('aws', resource_id)
            _node(nodes, node_id, 'AWSResource', resource_type='events.' + resource['resource_type'],
                  anonymous_label='AWS ' + resource['resource_type'] + ' ' + node_id.split(':')[1][:8],
                  source_system='aws_snapshot', source_record_id=_opaque('aws_record', resource_id),
                  evidence_chunk_ids=sorted(aws_chunks[resource_id]))
            materialized.add(resource_id)
            _edge(edges, case_id, 'INCLUDES', node_id, case_ids={case_id}, source_system='curated_manifest',
                  source_record_id=case_id, evidence_chunk_ids=aws_chunks[resource_id],
                  evidence_quote='AWS snapshot resource included in the curated case scope.',
                  extraction_method='curated_manifest', basis='study_scope_membership')
        rule_id = _opaque('aws', rule['resource_id'])
        bus_id = _opaque('aws', bus['resource_id'])
        _edge(edges, file_id, 'RELATED_TO', rule_id, case_ids={case_id}, source_system='github_patch_and_aws_snapshot',
              source_record_id=_opaque('aws_binding', pr_key + '\0' + rule['resource_id']),
              evidence_chunk_ids=github_chunks[pr_key] | aws_chunks[rule['resource_id']],
              evidence_quote='Selected publisher code declares exactly the source and detail type filtered by this snapshot rule; configured bus and runtime delivery are unproven.',
              extraction_method='exact_event_contract_match', basis='exact_event_contract_match')
        _edge(edges, rule_id, 'RELATED_TO', bus_id, case_ids={case_id}, source_system='aws_snapshot',
              source_record_id=_opaque('aws_record', rule['resource_id']),
              evidence_chunk_ids=aws_chunks[rule['resource_id']] | aws_chunks[bus['resource_id']],
              evidence_quote='Snapshot rule declares the exact event bus identifier in the same account and region. This is observed configuration, not runtime delivery.',
              extraction_method='exact_snapshot_bus_identifier', basis='snapshot_event_bus_membership')
        for relation in relations:
            if relation['source_resource_id'] == rule['resource_id'] and relation.get('unresolved_target'):
                unresolved.add(relation.get('relation_id') or json.dumps(relation, sort_keys=True))
    return {'binding_count': len(bindings), 'resource_count': len(materialized),
            'unresolved_target_count': len(unresolved), 'runtime_delivery_proven': False,
            'configured_publisher_bus_proven': False}
