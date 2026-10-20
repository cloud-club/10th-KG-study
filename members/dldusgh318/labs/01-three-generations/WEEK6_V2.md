# W6: v1에 그래프 리트리버만 추가

## 실행

```bash
.venv/bin/python -m unittest discover -s tests -p test_graph_retriever.py
.venv/bin/python src/run_w6_compare.py --dry-run
.venv/bin/python src/run_w6_compare.py
.venv/bin/python src/report_w6_compare.py
.venv/bin/python src/agent_v2.py "SeCause에서 분석 작업 큐에 사용한 기술을 TEAMFICIAL에서는 어떤 용도로 사용했나?"
```

`.env`의 키를 사용하며 키는 기록하지 않는다. 생성된 `results/w6_runs.jsonl`은
첫 줄 고정 설정, 이후 v1/v2 × 7문항 × 3회 = 42개 실행이다. 기존 1회 실험은
덮어쓰지 않는다. 같은 설정·평가셋·그래프 해시일 때 완료된 실행은 건너뛴다.
`results/w6_judgments.json`에 실행별 의미 판정을 기록한 후 report 명령으로
`results/w6_compare.md`를 재생성한다. 판정 이유와 경계 사례도 원본과 함께 남긴다.
질문/원문은 사용자가 승인한 OpenAI API로 전송된다.

## 고정 설정

`agent.py`는 수정하지 않는다. 기존 결과의 모델, reasoning_effort=low,
verbosity=low, 시스템 프롬프트, JSON 스키마, 원문 부분 문자열 인용 검증을 그대로
사용한다. BM25/벡터 각각 top-50, RRF k=60, v1 top-5, 8,000자 예산이다.
temperature는 기존 요청처럼 생략하고 실제 응답 temperature도 기록한다.

## 그래프 확장

Postgres의 entities/edges를 읽기 전용 일관 스냅샷으로 읽는다. 질문 문자열이나
expected로 노드를 찾지 않는다. v1 top-5 chunk_id의 엣지에 등장한 TechnologyUse와
Technology로만 진입한다. TechnologyUse → Technology → 다른 TechnologyUse가
최대 2홉이며, Project는 확장된 사용례의 소속 연결 조회다. RDF 경로 전체에서
Project 연결까지 모두 세는 4홉이라는 뜻과 구분한다.

degree는 근거 중복을 제외한 서로 다른 IRI 이웃 수다. 20을 초과하는 노드에서
다음 노드로 확장하지 않는다. seed가 없으면 `agent.assemble_context`로 v1과
완전히 동일한 컨텍스트를 만든다.

## 컨텍스트와 근거

- v1 청크 5,000자: 기존 조립 함수를 사용하므로 마지막 청크는 잘릴 수 있다.
- 그래프 파생 사실 800자: project/technology/status 그룹, 대표 purpose와 근거 번호.
- 회수 원문 2,200자: chunk_id 정렬, v1 top-5 제외, 넘치면 청크 통째 제외.
- 구분자·헤더도 예산에 포함해 합계 8,000자를 넘지 않는다.
- 사실은 컨텍스트에 남은 원문 근거가 있을 때만 렌더링한다. 목적이 여러 개면
  하나로 추정하지 않고 목적 목록을 표시한다. NULL 상태는 상태 미기재로 표시한다.
- 회수 후보 `recovered_chunks`와 실제 포함 `included_recovered_chunks`는 다르다.
  `gold_reached_via_graph`는 실제 컨텍스트에 포함된 gold/동등 청크만 인정한다.
- 생성된 사실은 독립적인 인용 source가 아니다. source 번호는 원문만 가리킨다.
  파생 사실 문장 자체를 snippet으로 복사하면 기존 원문 인용 검증에서 탈락한다.

## 비교·채점

매 질문을 v1/v2 각각 3번 실행하고 2라운드는 순서를 뒤집는다. 모델을 사전 로딩해
latency에서 초기 임베딩 로딩 비용을 제외한다. 공통 그래프 스냅샷 로딩도 제외하며,
각 실행의 검색·확장·조립·LLM·인용 검증 시간은 포함한다.

각 답변은 expected의 핵심 사실과 의미 비교해 correct/partial/wrong으로 판정한다.
최종은 3회 다수결, 셋 다 다르면 partial이다. 인용 검증 통과만으로 정답 처리하지 않는다.
recall은 실제 컨텍스트에 들어간 gold 기준이고 gold가 있는 equivalent_groups는
대체 정답으로 인정한다. v2 recall은 원래 top-5 + 예산 내 회수 청크의 recall이지
회수 후보 전체의 recall이 아니다.

A1/A2 expected는 **현재 그래프의 20개 청크 표본 기준**이며 v1 전체 문서 검색과
정답 범위가 다르다. X03은 질문에 TEAMFICIAL 지원자 수라는 2홉째 단서가 있어
v1도 맞힐 수 있는 질문이다. 이 질문 성공을 그래프만의 효과로 주장하지 않는다.
