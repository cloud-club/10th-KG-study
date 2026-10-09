"""수동 의미 검토 결과를 Text2Cypher 실행 원본에 결합한다. LLM 재호출 없음."""
import json
from collections import Counter

from common import LAB


def main():
    destination=LAB/'results'
    raw=[json.loads(l) for l in (destination/'text2cypher.jsonl').read_text().splitlines()]
    judgments=json.loads((destination/'text2cypher_judgments.json').read_text())['judgments']
    by_key={(j['id'],j['round']):j for j in judgments}
    if len(raw)!=22 or len(by_key)!=21: raise ValueError('21회 실행·판정 필요')
    rows=[{**r,**by_key[r['id'],r['round']]} for r in raw[1:]]
    (destination/'text2cypher_scored.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in [raw[0],*rows])+'\n')
    counts=Counter(r['judgment'] for r in rows)
    failures=Counter(r['failure_type'] for r in rows if r['failure_type'])
    lines=['# Text2Cypher — 20개 청크 표본 Neo4j', '',
           '7문항 × 3회 = 21회. 모델이 생성한 Cypher를 수정하지 않고 읽기 실행했다. 실패 시 자동 재생성·수정은 하지 않았다.',
           f"실행 에러: {sum(r['error'] is not None for r in rows)}건. 판정: {dict(counts)}. 주 실패 유형: {dict(failures)}.",
           'wrong_value 3건은 모두 zero_rows를 함께 기록한다. 유형은 중복 집계하지 않고 주 원인과 결과를 분리한다.', '',
           '## 실제 스키마', '',
           '- Project 3개: id, label. Technology 25개: id, label. TechnologyUse 41개: id, purpose, status.',
           '- 실제 추가 속성(entity_id/label/ingested_from 등)은 실행 메타데이터에 기록했다.',
           '- (TechnologyUse)-[:PART_OF]->(Project) 48개, (TechnologyUse)-[:USES_TECHNOLOGY]->(Technology) 48개. REPLACES는 현재 0개라 프롬프트의 실제 관계에 추가하지 않았다.',
           '- status: implemented 22, proposed 3, 미기재 16. not_implemented는 허용값이지만 실제 저장값은 0개.',
           '- 같은 노드 사이에 청크별 근거 관계가 여러 개 있으므로 기술·프로젝트·사용례 집계는 DISTINCT 식별자가 필요하다.', '',
           '## 질문별 3회 결과', '',
           '| 질문 | 1회 | 2회 | 3회 |', '|---|---|---|---|']
    for id_ in ('A1','A2','X01','X03','T01','T02','T03'):
        rs=sorted([r for r in rows if r['id']==id_],key=lambda r:r['round'])
        lines.append('| '+rs[0]['question']+' | '+' | '.join(r['judgment'] for r in rs)+' |')
    lines += ['', '## 의미 오류 — 핵심', '',
              '### A2 1회: 실행 성공, 질문 범위는 틀림', '',
              '사용례의 proposed를 찾은 뒤 같은 기술에 implemented 사용례가 하나라도 존재하면 기술 전체를 제외하는 NOT EXISTS를 추가했다. 결과는 메시지 큐와 outbox 패턴 2개뿐이다.',
              'Redis는 TEAMFICIAL/SeCause뿐 아니라 직행의 다른 목적에도 implemented 사용례가 있다. 이것이 직행의 통근시간 캐시 proposed를 없애지는 않는다. 기술 단위와 사용례 단위를 혼동한 semantic_wrong이다.',
              '현재 expected는 proposed 사용례 기준이므로 partial로 판정했다. 모든 프로젝트에서 한 번도 구현하지 않은 기술만 찾는 다른 질문이라면 결과 해석이 달라진다.', '',
              '### X01 3회: 데이터가 없는 것이 아니라 조건 값이 맞지 않음', '',
              '생성 조건은 purpose CONTAINS "분석 작업 큐" 또는 "분석" AND "큐"였다. 실제 SeCause Redis purpose는 "큐 기반 비동기 처리", "분석 작업을 백그라운드로 분리", NULL이다. 한 노드의 문자열에 질문의 모든 단어가 함께 들어 있지 않아 0건이 됐다.',
              '진단용으로 purpose CONTAINS "큐"를 조회하면 공통 Redis와 TEAMFICIAL의 "지원자 수 집계 성능 개선"(implemented), "Redis 캐싱 인프라"(상태 미기재), 목적 NULL(상태 미기재) 3개가 나온다. 이 진단 결과로 원래 생성 쿼리를 고치거나 성공 처리하지 않았다.', '',
              '### X03: 결과는 맞지만 과소제약 위험이 남음', '',
              '현재 표본은 직행 proposed Redis와 TEAMFICIAL implemented 지원자 수 캐시를 반환하므로 correct다. 그러나 질문의 통근시간/지원자 수 목적은 WHERE에 없다. 다른 목적의 사용례가 추가되면 무관한 행도 나올 수 있다. 현재 관측 semantic_wrong과 향후 위험을 혼동해 집계하지 않는다.', '',
              '### T02: "제안만"의 범위', '',
              'proposed Redis 사용례가 있는 프로젝트는 직행이다. 직행의 테스트 결과 저장 Redis는 implemented다. 따라서 "직행은 Redis를 어떤 용도로도 구현하지 않았다"라고 답하면 틀린다. 이번 판정은 해당 proposed 사용례가 있는 프로젝트를 묻는 것으로 해석한다.', '',
              '### T03: 목적 결측', '',
              '목적 미기재 TechnologyUse는 18개다. 관계 수가 아니라 노드 식별자 기준이다. 현재 데이터에서는 빈 문자열이 없으므로 IS NULL과 빈 문자열까지 포함한 조건의 결과가 같다.', '',
              '## 전체 기록', '',
              '| 질문 / 회차 | 생성된 Cypher | 실행 결과 행 | 에러 | 판정 | 실패 유형 |',
              '|---|---|---|---|---|---|']
    cell=lambda value: str(value).replace('|','\\|').replace('\n','<br>')
    for r in rows:
        lines.append('| '+' | '.join([cell(f"{r['id']} {r['round']}회: {r['question']}"),
            '`'+cell(r['cypher'])+'`',cell(json.dumps(r['rows'],ensure_ascii=False)),
            cell(json.dumps(r['error'],ensure_ascii=False)),r['judgment'],cell(', '.join(r['failure_types']) or '없음')])+' |')
    lines += ['', '## 0건 응답 — 생성 조건을 숨기지 않음', '']
    for r in rows:
        if not r['rows'] and not r['error']:
            lines += [f"### {r['id']} / {r['round']}회", '', r['response'], '']
    lines += ['## 실행 및 보안', '',
              '```bash', '.venv/bin/python src/text2cypher.py', '.venv/bin/python src/report_text2cypher.py', '```', '',
              '- 키는 .env에서 읽고 출력·기록하지 않는다. 질문과 스키마/예시만 OpenAI로 보내며 실행 결과를 다시 LLM에 보내지는 않는다.',
              '- 정적 단일 쿼리 검사, EXPLAIN의 읽기 query_type, execute_read, 트랜잭션 10초 제한을 적용했다. CALL/APOC/LOAD CSV/쓰기/다중 문장은 차단한다.',
              '- 현재 로컬 계정은 관리자이므로 운영 환경에서는 별도 읽기 전용 권한 계정을 추가해야 한다. 정규식 가드를 일반 Cypher 보안 샌드박스로 주장하지 않는다.',
              '- 실행 전후 그래프 전체 스냅샷 해시가 같음을 확인했다.',
              '- 원본: text2cypher.jsonl. 판정 결합본: text2cypher_scored.jsonl. 원본의 null 판정은 결합본에서 채운다.',
              '- 실제 DB 스냅샷: text2cypher_schema.json. 모델·reasoning_effort·verbosity·프롬프트·few-shot·스키마는 JSONL 첫 줄에 저장했다.', '',
              '## 실제 프롬프트', '', '```text',raw[0]['prompt'],'```','']
    (destination/'text2cypher_report.md').write_text('\n'.join(lines))
    print('보고서 및 채점 결합본 저장 완료')


if __name__=='__main__': main()
