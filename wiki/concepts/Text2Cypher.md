---
title: Text2Cypher — 생성됨 · 실행됨 · 맞았음은 서로 다른 상태다
type: concept
tags: [concept, pitfall]
status: draft
created: 2026-10-18
updated: 2026-10-20
members: [heebindev, kdyann, sunghyun, dldusgh318, Yeongeunn, e0ng]
weeks: [6]
---

> 자연어 질문과 그래프 스키마를 LLM에 주고 Cypher를 생성하게 한 뒤, 검증을 거쳐 Neo4j에서 실행하는 방식이다. Top-k 검색으로는 답할 수 없는 **집계 질문**을 푸는 유일한 수단으로 6주차에 네 멤버가 실측했다. 공통 교훈은 하나다. **문법이 맞고 실행이 돼도 관계 방향·라벨·집계 범위·값 조건이 틀리면 오답이다.** 오류 없이 0건이 나오면 "없다"는 그럴듯한 오답이 된다.

## 정의

- LLM은 질의문을 쓰고, 실제 조회는 Neo4j가 한다(Yeongeunn). 모델이 올바른 질의를 쓰려면 노드 라벨, 관계 이름과 **방향**, 속성 이름을 알아야 한다. 그래서 미니 온톨로지의 의미와 실제 Neo4j 라벨·관계 타입을 연결해서 설명하는 일이 핵심이다 → [[폐쇄-스키마-설계]].
- [[GraphRAG]]의 세 패턴 중 하나다. 다만 축이 다르다. 로컬·글로벌이 근거의 **범위**를 말한다면, Text2Cypher는 질의를 **누가 만드느냐**를 말한다(sunghyun). 고정 질의로도 그래프 리트리버를 만들 수 있으므로 Text2Cypher가 필수는 아니다.
- sunghyun은 상태를 셋으로 나눴다. **생성 완료 · 실행 성공 · 의미상 정답**은 서로 다른 상태다. 생성을 보류(`answerable:false`)하는 것은 넷째 상태이며, 오류가 아니다.

## 강점 · 약점

- **강점: 전체 범위 집계.** heebindev의 "관계가 가장 많은 엔티티"는 v1·v2(로컬 서치)가 모두 답하지 못했지만, Text2Cypher는 `count()`와 `ORDER BY`로 SJF 4개를 반환했다. kdyann의 집계 2문항(야구 게시물 7개 · 최다 주제 야구 7개)과 dldusgh318의 A1·X03·T01~T03도 Text2Cypher가 맞혔다.
- **약점: 그래프에 없는 것은 못 찾는다.** heebindev의 "SJF 평균 처리 시간은 몇 초?"에서 Cypher는 `평균 Turnaround time` 노드를 찾았지만, 노드에 수치가 저장돼 있지 않아 답하지 못했다.
- **약점: 그래프 원본을 그대로 믿는다.** 리트리버에서 제외해 둔 검토 대기 관계까지 집계에 들어갔다(heebindev).

## 멤버들이 확인한 것

| 멤버 | 조건 | 결과 |
|---|---|---|
| **dldusgh318** | 7문항 × 3회 = 21회. 생성문을 고치지 않고 재생성도 없이 실행. 그래프 노드 69개(Project 3 · Technology 25 · TechnologyUse 41) | 실행 에러 0. correct 17 · partial 1 · wrong 3. A1·X03·T01~T03은 3/3, A2는 2/3. 실패는 X01 3회(값 불일치로 0건)와 A2 1회(의미 오류) |
| **kdyann** | 8문항, `gpt-4.1-mini` 자유 생성 → 허용 문법 검증 → 매개변수 질의로 변환해 실행 | 실행 성공 2(집계) · 검증 거절 4(다중 홉·추천) · 지원 불가 2(단순 이름 질문). "rejected가 전부 문법 오류라는 뜻은 아니다", "실행에 성공했다고 의미를 정확히 반영한다고 볼 수도 없다" |
| **heebindev** | 3문항, `MATCH`로 시작하고 `RETURN`이 있는 읽기 질의만 허용 | 집계 1문항 성공(검토 대상 관계 포함). 1-hop 질의는 방향 없는 `-[r]-` 때문에 방향을 오해할 수 있었다. 수치 질문은 답할 수 없었다 |
| **sunghyun** | 실제 클래스·관계·속성 예시와 few-shot을 주고 생성문과 결과를 정답과 대조. Qwen 7B | "관련 커밋이 있으니 수정 완료인가?" → `answerable:false`로 생성 보류(15.1초, 입력 1,999 · 출력 58토큰). "v0.2.0 실패 Case Run 수"는 생성됐지만 오류 5개(아래), `execution:null` |

## 함정 · 주의

실패 유형을 멤버 실측에서 모았다.

| 유형 | 사례 | 대응 |
|---|---|---|
| **관계 방향 반대** | sunghyun: `PART_OF_RUN`을 Test Run→Case Run으로 작성했다(실제는 Case Run→Test Run). heebindev: `-[r]-`로 탐색해 `SRTN -IS_A-> SJF`가 `SJF -IS_A-> SRTN`처럼 보였다 | 방향을 `-[r]->`·`<-[r]-`로 명시하고 반환값에 방향을 포함한다 |
| **없는 라벨** | sunghyun: `tr:TestRun` 라벨을 썼지만 실제 그래프는 `W56Entity` + `kind:'test_run'` 구조였다 | 실제 라벨·`kind` 값을 스키마 설명과 few-shot에 넣는다 |
| **집계 누락** | sunghyun: 개수를 물었는데 `count` 대신 행을 반환하고 `LIMIT 100`으로 잘랐다 | 질문이 개수를 요구하면 `count(DISTINCT …)`인지 확인한다 |
| **속성 위치 혼동** | sunghyun: 실행 차수는 Test Run의 속성인데 Case Run에서 찾았다 | 검토 순서: 범위 → 라벨·kind → 방향 → 속성 위치 → DISTINCT·집계 → 파라미터 값 (sunghyun) |
| **파라미터 값 오류** | sunghyun: 실제 값 대신 문자열 `"$scenario"`를 넣었다 | 실행 전에 파라미터 바인딩을 확인한다 |
| **값 표현 불일치 → 정상 0건** | dldusgh318 X01: `purpose CONTAINS '분석 작업 큐'`처럼 질문 표현을 그대로 조건에 넣었다. 저장값은 다른 표현이라 에러 없이 0건이 나왔고, "없다"는 오답이 됐다 | 0건일 때 생성 Cypher를 함께 보여준다(dldusgh318). 경로 부재 ≠ 거짓 → [[온톨로지와-추론]] |
| **단위 혼동 (의미 오류)** | dldusgh318 A2: `NOT EXISTS`로 "다른 곳에서 구현된 기술"을 통째로 뺐다. 기술 단위와 사용례 단위를 혼동했다. 중간 노드(TechnologyUse)가 표현력을 늘린 대가로, 질문을 그래프의 어느 단위로 읽을지가 모호해졌다 | → [[RDF와-트리플]] (중간 노드), [[엔티티-신원해소]] |
| **과소제약 (잠재 위험)** | dldusgh318 X03: 지금은 맞지만 WHERE에 목적 조건이 없어 데이터가 늘면 무관한 행이 섞일 수 있다 | 정답을 맞힌 질의도 조건을 검토한다 |
| **검토 대기 관계 포함** | heebindev: 리트리버가 제외한 `review_queue` 관계가 집계에 들어갔다 | Neo4j 원본을 정제하거나 실행 단계에도 필터를 둔다 |

- **쓰기 차단은 공통 장치다.** 멤버마다 막는 방식이 달랐다.
  - heebindev: `CREATE`·`MERGE`·`DELETE`·`SET`을 검사한다.
  - kdyann: 쓰기·프로시저 호출·알 수 없는 관계·추가 조건을 거부한다. 여기에 실행계획의 읽기 유형, 5초 제한, 반환 행 상한을 둔다.
  - dldusgh318: `EXPLAIN`으로 읽기 쿼리인지 확인하고 `execute_read`, 10초 제한, CALL·APOC 차단을 건다. 실행 전후 스냅샷 해시가 같은지도 확인한다.
  - sunghyun: 공개 예제에서는 생성문을 자동 실행하지 않는다.
- **생성 보류는 실패가 아니다.** 참조 관계(`relatedCommit`)만으로 완료를 판단할 수 없을 때 `answerable:false`를 돌려준 것은 맞는 동작이다(sunghyun). 사용자는 이것을 '생성 실패'라고 불렀지만, 시스템 오류가 아니라 근거 부족에 따른 보류다.

## 열린 질문

- 의미 정답률을 자동으로 채점하는 방법. 지금은 전부 사람이 정답과 대조했다(dldusgh318 21회, sunghyun 교정 예시).
- 값 표현 불일치(정상 0건)를 줄이는 방법. 후보 값 목록을 스키마와 함께 주는 방법이 있지만 아직 측정되지 않았다.
- kdyann의 "검증 거절 4"가 정당한 거절인지 지나친 제약인지는 구분되지 않았다.

## 관련

- [[GraphRAG]] · [[그래프-적재-Postgres와-Neo4j]] · [[폐쇄-스키마-설계]] · [[SPARQL]] · [[RAG-vs-그래프-질의]] · [[온톨로지와-추론]] · [[RDF와-트리플]] · [[엔티티-신원해소]]

## 출처

- heebindev · GraphRAG 에이전트 v2 실습 (§4 Text2Cypher) — [members/heebindev/labs/04-graphrag-agent/README.md](../../members/heebindev/labs/04-graphrag-agent/README.md); GraphRAG 노트 (§3) — [notes/06-graphrag.md](../../members/heebindev/notes/06-graphrag.md)
- kdyann · W6 실습 (§Text2Cypher 결과) — [members/kdyann/labs/06-graphrag/README.md](../../members/kdyann/labs/06-graphrag/README.md)
- sunghyun · 검색에 그래프를 붙이고 같은 질문으로 비교하기 (§Text2Cypher는 실행만 되면 성공인가) — [members/sunghyun/notes/06-graphrag-and-agentic-search.md](../../members/sunghyun/notes/06-graphrag-and-agentic-search.md); 실습 — [labs/06-graphrag/README.md](../../members/sunghyun/labs/06-graphrag/README.md)
- dldusgh318 · Text2Cypher 리포트 — [text2cypher_report.md](../../members/dldusgh318/labs/01-three-generations/results/text2cypher_report.md); 6주차 노트 — [01-graphRAG.md](../../members/dldusgh318/notes/week6/01-graphRAG.md)
- Yeongeunn · GraphRAG (§6 Text2Cypher) — [members/Yeongeunn/notes/13-week6-graphrag.md](../../members/Yeongeunn/notes/13-week6-graphrag.md)
- e0ng · GraphRAG 패턴 (§Text2Cypher) — [members/e0ng/notes/06-1-graphrag-patterns.md](../../members/e0ng/notes/06-1-graphrag-patterns.md)
- Neo4j GraphRAG Python 사용자 가이드 — https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html
