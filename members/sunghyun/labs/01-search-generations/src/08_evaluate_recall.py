"""고정한 초기 정답셋으로 BM25/HNSW/RRF의 청크 Recall을 비교한다."""
import argparse
import csv
import importlib.util
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = [
    ('Q6', 'CodeCenter에서 서버의 모델을 가져와 선택하는 방법은?', [
        '939045cab738cdbea348369ce1cf8974b649821a24d7aa3e2ddbc92adf8ed9bc',
        '0e75812d485ca6f7c7fbb48b9b3fd9862cd1d2b349eec538a82a1e084439f581',
    ]),
    ('Q1', 'URX에서 Unlink하면 ALM의 실제 아이템도 삭제되나요?', ['4a5263de']),
    ('Q2', 'URX에서 두 시스템의 연결만 끊고 원래 항목은 남겨둘 수 있나요?', ['4a5263de']),
    ('Q3', 'URX에서 Send Items로 다른 ALM에 전송하면 어떤 정보가 복사되나요?',
     ['4f1ce695', 'c4a62fbe']),
    ('Q4', 'URX에서 한쪽 시스템의 항목을 다른 쪽에 만들 때 제목과 설명도 같이 옮길 수 있나요?',
     ['4f1ce695', 'c4a62fbe']),
    ('Q5', '회의록에서 Eclipse를 개발환경으로 사용하는 회사는 어디인가요?', [
        '48342bcee9fbb3e9e4dba1d9ec6f46fb9a9a296c3d9b073fcc8ab0673df61037',
        'e5b1f12de86a12bbe4f2821be191e0c9275ad3d36b7ba2267d2f5a624fc9798a',
        '79f31024b53b409930493203e6a029141756d0fdb7d9fd3b1849509417b8a04a',
        '8af183a81f23b9cbc24364a92fdc3c84216f5b674ef8d32fd9a98358cde7db8f',
    ]),
]


def recall_at_k(ranked_ids, gold, k):
    if not gold:
        raise ValueError('정답 근거가 비어 있습니다.')
    found = set(ranked_ids[:k]) & set(gold)
    return len(found) / len(set(gold)), sorted(found)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator', choices=['or', 'and'], default='or')
    parser.add_argument('--candidates', type=int, default=20)
    parser.add_argument('--ef-search', type=int, default=40)
    parser.add_argument('--ks', nargs='+', type=int, default=[1, 3, 5])
    parser.add_argument('--question', choices=[c[0] for c in CASES], help='특정 질문만 실행')
    args = parser.parse_args()
    if min(args.ks) < 1 or args.candidates < max(args.ks) or args.ef_search < args.candidates:
        parser.error('k는 양수, candidates는 최대 k 이상, ef-search는 candidates 이상이어야 합니다.')
    ks = sorted(set(args.ks))
    chunks = [json.loads(l) for l in (ROOT / 'outputs/chunked_documents_v1.jsonl').read_text().splitlines() if l.strip()]
    spec = importlib.util.spec_from_file_location('hybrid', ROOT / '05_hybrid_rrf.py')
    hybrid = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hybrid)
    summary, detail = [], []
    for qid, query, prefixes in CASES:
        if args.question and qid != args.question:
            continue
        gold = []
        for prefix in prefixes:
            matches = [r for r in chunks if r['chunk_id'].startswith(prefix)]
            if len(matches) != 1:
                raise ValueError(f'정답 ID {prefix}가 유일하지 않습니다.')
            gold.append(matches[0]['chunk_id'])
        print(f'\n{qid}: {query}\n정답 근거 수: {len(gold)}', flush=True)
        report = hybrid.retrieve(query, args.operator, args.candidates, 60,
                                 'hnsw', args.ef_search, track_total_hits=False)
        rankings = {**report['lists'], 'hybrid': report['results']}
        ranked_details = {}
        for method, hits in rankings.items():
            ids = [h['chunk_id'] for h in hits]
            row = {'question_id': qid, 'method': method}
            parts = []
            for k in ks:
                score, found = recall_at_k(ids, gold, k)
                row[f'recall@{k}'] = score
                parts.append(f'R@{k}={len(found)}/{len(gold)}={score:.2f}')
            summary.append(row)
            print(method.ljust(8), ' | '.join(parts))
            ranks = {cid: (ids.index(cid) + 1 if cid in ids else None) for cid in gold}
            print('  정답 청크 순위:', {cid[:8]: rank for cid, rank in ranks.items()})
            for cid in gold:
                record = next(r for r in chunks if r['chunk_id'] == cid)
                print('   ', ' / '.join(record.get('document_path') or []),
                      '→ 순위:', ranks[cid])
            ranked_details[method] = {'gold_ranks': ranks, 'results': [
                {'rank': n, 'chunk_id': h['chunk_id'], 'title': h['record'].get('title'),
                 'section_path': h['record'].get('section_path'), 'is_gold': h['chunk_id'] in gold}
                for n, h in enumerate(hits, 1)]}
        detail.append({'question_id': qid, 'query': query, 'gold_ids': gold,
                       'rankings': ranked_details, 'used_hnsw': report['used_hnsw']})
    averages = {}
    print('\n질문별 Recall의 평균 (macro average)')
    for method in ['bm25', 'vector', 'hybrid']:
        rows = [r for r in summary if r['method'] == method]
        averages[method] = {f'recall@{k}': sum(r[f'recall@{k}'] for r in rows) / len(rows) for k in ks}
        print(method, averages[method])
    stem = ROOT / 'outputs' / ('recall_eval_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    with stem.with_suffix('.json').open('x', encoding='utf-8') as out:
        json.dump({'settings': vars(args), 'gold_scope': '원문을 검토해 고정한 초기 정답셋; 전체 관련 근거의 완전성은 미검증',
                   'summary': summary, 'macro_average': averages, 'questions': detail}, out, ensure_ascii=False, indent=2)
    with stem.with_suffix('.csv').open('x', encoding='utf-8-sig', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=['question_id', 'method'] + [f'recall@{k}' for k in ks])
        writer.writeheader()
        writer.writerows(summary)
    print('결과 저장:', stem.with_suffix('.json'), stem.with_suffix('.csv'))
    print('정답이 후보 목록에 없으면 순위는 None입니다. LLM 호출은 수행하지 않았습니다.')


if __name__ == '__main__':
    main()
