"""실행별 의미 판정 파일에서 다수결 비교표를 생성한다. 추가 LLM 호출 없음."""
import json
from statistics import mean

from common import LAB
from run_w6_compare import majority


def main():
    destination = LAB/'results'
    raw = [json.loads(l) for l in (destination/'w6_runs.jsonl').read_text().splitlines()]
    config,rows = raw[0],raw[1:]
    judgments = json.loads((destination/'w6_judgments.json').read_text())
    grades = {(j['id'],j['variant'],j['round']):j for j in judgments['judgments']}
    if len(rows)!=42 or len(grades)!=42:
        raise ValueError('42회 실행 및 42개 개별 판정 필요')
    lines = ['# W6 v1 / v2 비교 — 7문항 × 각각 3회', '',
             'A1·A2의 expected는 **현재 그래프에 들어간 20개 청크 표본 기준**이다. 전체 문서 답과 범위가 다르다.',
             'X03은 질문에 TEAMFICIAL 지원자 수라는 **2홉째 검색 단서가 있어 v1도 맞히는 질문**으로 분류한다.', '',
             '각 실행을 의미 비교한 뒤 3회 다수결. 셋 다 다르면 partial. 예전 1회 결과는 이번 집계에 재사용하지 않았다.',
             'recall은 실제 컨텍스트의 gold/동등 청크 적중률이다. v2는 top-5+회수 청크 기준이므로 순수 top-5 지표와 구분한다.',
             '토큰·latency는 3회 산술평균, 각 셀은 **v1 / v2** 순서. latency는 ms.', '',
             '| 질문 | v1 판정 | v2 판정 | v1 recall | v2 recall | 그래프 경유 gold | 토큰 (v1/v2) | latency (v1/v2) |',
             '|---|---|---|---:|---:|---|---:|---:|']
    final = {}; metrics = {}
    for id_ in ('S01','M01','X01','X03','H01','A1','A2'):
        groups = {v: sorted([r for r in rows if r['id']==id_ and r['variant']==v],key=lambda r:r['round']) for v in ('v1','v2')}
        for v,rs in groups.items():
            if len(rs)!=3 or {r['round'] for r in rs}!={1,2,3}:
                raise ValueError('질문별 라운드 누락')
            final[id_,v] = majority([grades[id_,v,r['round']]['grade'] for r in rs])
        a,b = groups['v1'],groups['v2']
        rec = lambda rs: 'null' if rs[0]['recall_at_5'] is None else f"{mean(r['recall_at_5'] for r in rs):.3f}"
        gold = sorted({c for r in b for c in r['graph_gold_chunks']})
        label = id_+(' (20개 표본)' if id_ in ('A1','A2') else ' (2홉째 단서 있음)' if id_=='X03' else '')
        lines.append(f"| {label} | {final[id_,'v1']} | {final[id_,'v2']} | {rec(a)} | {rec(b)} | {', '.join(gold) or '없음'} | {mean(r['tokens'] for r in a):.1f} / {mean(r['tokens'] for r in b):.1f} | {mean(r['latency_ms'] for r in a):.1f} / {mean(r['latency_ms'] for r in b):.1f} |")
    lines += ['', '## 관찰 결과', '',
              '- 이번 다수결에서 달라진 항목은 X01의 wrong → partial뿐이다. Redis 공통 기술과 캐싱 인프라는 찾았으나 지원자 수 집계의 구체적 설계는 빠졌다.',
              '- 실제 컨텍스트의 추가 gold는 모든 문항에서 0건이다. 그래프 확장 성공과 gold 회수 성공을 같은 말로 쓰지 않는다.',
              '- X01의 회수 원문은 직행 청크 2개와 TEAMFICIAL 인프라 소개 청크다. 지원자 수 캐시의 상세 청크는 예산 때문에 제외됐다.',
              '- X03은 기존 1회 실험에서는 v1 correct였지만 이번 3회에서는 partial 다수결이다. 그래프 우월성보다 답변 구성 변동도 함께 드러난다.',
              '', '## 채점 민감도', '', *judgments.get('notes',[]), '', '## 해석상 제한', '',
              '- 그래프 경유 gold는 확장 후보가 아니라 예산 내 실제 포함된 청크만 센다.',
              '- seed가 없는 S01/H01/A1/A2는 양쪽 컨텍스트가 동일하다. 이 경우 답변 차이는 그래프 개선 증거가 아니라 생성 변동이다.',
              '- 현재 회수 순서는 chunk_id 정렬이며 질문 관련도 재랭킹이 없다. 2,200자 예산이 먼저 들어온 원문으로 소진될 수 있다.',
              '- v1 청크 예산도 v2에서 8,000→5,000자로 줄어든다. 기존 근거 손실 가능성까지 포함한 리트리버 변형 비교다.',
              '- 인용 검증 통과는 원문 부분 문자열 검증이지 의미적 정답 보증이 아니다.',
              '- A2: 전체 문서에서는 사실인 검토 의향도 20개 표본 DB expected와 일치하지 않으면 wrong이다. 범위 불일치를 결과 해석에 남긴다.',
              '- model/reasoning/verbosity/시스템 프롬프트/스키마/인용 검증은 동일하며, temperature는 양쪽 요청에서 생략했다.', '',
              '## 실행별 판정과 답변', '']
    for id_ in ('S01','M01','X01','X03','H01','A1','A2'):
        lines += [f'### {id_}', '']
        for row in sorted([r for r in rows if r['id']==id_],key=lambda r:(r['variant'],r['round'])):
            j=grades[id_,row['variant'],row['round']]
            lines += [f"#### {row['variant']} / {row['round']}회 — {j['grade']}", '',
                      f"이유: {j['reason']}", '', row['answer'], '',
                      f"인용 검증: {row['citation_valid']}; 옛 캐시 메모 컨텍스트 포함: {row['stale_cache_in_context']}", '']
    lines += ['## 재현 설정', '', '```json',json.dumps(config,ensure_ascii=False,indent=2),'```','']
    (destination/'w6_compare.md').write_text('\n'.join(lines),encoding='utf-8')
    print('비교표 저장: results/w6_compare.md')


if __name__ == '__main__':
    main()
