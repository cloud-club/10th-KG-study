"""질문 → BM25/HNSW → RRF → 컨텍스트 → 로컬 LLM 답변."""
import argparse
import importlib.util
import json
import os
import re
import time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', required=True)
    parser.add_argument('--cache', type=Path, help='04에서 적재한 벡터 캐시 파일')
    parser.add_argument('--candidates', type=int, default=20)
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--ef-search', type=int, default=40)
    parser.add_argument('--operator', choices=['or', 'and'], default='or')
    parser.add_argument('--mode', choices=['local', 'openrouter'], default='local')
    parser.add_argument('--search-mode', choices=['hnsw', 'exact'], default='hnsw')
    parser.add_argument('--model', help='답변 모델 ID. 기본 local=qwen2.5:7b, openrouter=z-ai/glm-5.2')
    parser.add_argument('--preview', action='store_true', help='검색/컨텍스트까지만 실행')
    args = parser.parse_args()
    if not args.query.strip() or min(args.candidates, args.top_k) < 1:
        parser.error('질문과 양수 후보/Top-k가 필요합니다.')
    if args.top_k > args.candidates:
        parser.error('top-k는 candidates 이하로 지정하세요.')
    if args.ef_search < 1 or (args.search_mode == 'hnsw' and args.ef_search < args.candidates):
        parser.error('HNSW ef-search는 candidates 이상이어야 합니다.')
    if args.mode == 'openrouter' and not args.preview and not os.environ.get('OPENROUTER_API_KEY', '').strip():
        parser.error('OPENROUTER_API_KEY 환경변수를 설정하세요. 키를 코드에 넣지 마세요.')
    hybrid = load('hybrid', '05_hybrid_rrf.py')
    answer = load('answer', '06_rag_answer.py')
    started = time.perf_counter()
    print('질문:', args.query, flush=True)
    print('BM25와 벡터 검색 → RRF 결합 중…', flush=True)
    report = hybrid.retrieve(args.query, args.operator, args.candidates, 60,
                             args.search_mode, args.ef_search, track_total_hits=False, cache=args.cache)
    selected = report['results'][:args.top_k]
    if not selected:
        raise ValueError('검색 근거가 없습니다. LLM 호출을 생략합니다.')
    print(f"검색 범위: {report['count']} / BM25={args.operator.upper()} / 벡터={args.search_mode} / 답변={args.mode}")
    print('후보:', {name: len(hits) for name, hits in report['lists'].items()})
    print('HNSW 실제 사용:', report['used_hnsw'], '/ 인덱스:', report['indexes'])
    print(f"계획 측정 DB 실행 시간: {report['db_execution_ms']:.3f} ms (질문 임베딩 제외)")
    for n, hit in enumerate(selected, 1):
        row = hit['record']
        print(f"[{n}] {row.get('title')} / {' / '.join(row.get('section_path') or [])}")
        print('  chunk_id:', hit['chunk_id'], '/ RRF:', round(hit['rrf'], 6),
              '/ 순위:', hit['ranks'])
    context = answer.build_context([hit['record'] for hit in selected])
    if args.preview:
        print('\n컨텍스트:\n' + context)
        return
    result = answer.generate_answer(args.query, context, args.mode, args.model)
    content = result['message']['content']
    print('\nLLM 답변:\n' + content)
    refs = sorted({int(n) for n in re.findall(r'\[(\d+)\]', content)})
    invalid = [n for n in refs if n < 1 or n > len(selected)]
    print('\n인용 번호:', refs, '/ 범위 밖 번호:', invalid)
    print('인용 번호 검사만 수행했습니다. 문장과 근거의 일치는 직접 확인하세요.')
    print('생성 종료 이유:', result.get('done_reason', '미제공'))
    elapsed = time.perf_counter() - started
    path = ROOT / 'outputs' / ('rag_run_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
    saved = {'query': args.query, 'settings': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}, 'retrieval': report,
             'selected': selected, 'context': context, 'llm': result,
             'elapsed_seconds': elapsed, 'citation_numbers': refs,
             'invalid_citations': invalid}
    with path.open('x', encoding='utf-8') as stream:
        json.dump(saved, stream, ensure_ascii=False, indent=2)
    print(f'전체 소요 시간: {elapsed:.2f}초 / 실행 기록: {path}')


if __name__ == '__main__':
    main()
