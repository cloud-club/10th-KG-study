"""SYNTHETIC demo: invented fixture, not real measured graph results.

Run from src: python3 synthetic_demo.py
No network, live database, private source, or output files are used.
"""
import json
from graph.build_graph import ROOT, MANIFEST_PATH, build_graph, load_evidence_ids
from graph.loader import build_node_cypher, build_relationship_cypher
from graph.validate_graph import validate_graph


def run_demo():
    nodes, edges, report = build_graph()
    manifest = json.loads(MANIFEST_PATH.read_text())
    sources = {k: (ROOT / v).resolve() for k, v in manifest['source_paths'].items()}
    schema = json.loads((ROOT / 'graph/schema.json').read_text())
    validation = validate_graph(nodes, edges, set(schema['relationships']), load_evidence_ids(sources))
    if not validation['valid']:
        raise ValueError(validation['errors'])
    node_query, node_params = build_node_cypher(nodes)
    edge_query, edge_params = build_relationship_cypher(edges)
    return {
        'label': 'SYNTHETIC DEMO ONLY — NOT REAL MEASURED RESULTS',
        'network_or_database_used': False,
        'runtime_delivery_or_http_requests_proven': False,
        'build': report,
        'validation': validation,
        'parameterized_query_rows': {'nodes': len(node_params['rows']), 'edges': len(edge_params['rows'])},
    }


if __name__ == '__main__':
    print(json.dumps(run_demo(), indent=2))
