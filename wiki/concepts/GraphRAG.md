---
title: GraphRAG — 검색에 그래프를 붙이면 언제 이기고 언제 지나
type: concept
tags: [concept, methodology]
status: draft
created: 2026-10-18
updated: 2026-10-18
members: [e0ng, heebindev, kdyann, sunghyun, Yeongeunn, dldusgh318, kungbi]
weeks: [6]
---

> 만들어 둔 그래프를 RAG의 리트리버로 쓰는 방식이다. 질문에서 시작 대상을 찾고, 관계를 따라가 근거를 모은 뒤, 원문 청크와 함께 LLM에 넘긴다. 6주차에는 다섯 멤버가 같은 질문을 v1(청크 하이브리드)과 v2(그래프 결합)에 던져 비교했다. 결론은 하나로 모였다. **그래프는 관계·다중 홉·집계 질문에서만 이기고, 그것도 맞는 경로를 골랐을 때만 이긴다.** 설명형 질문은 청크 검색으로 충분했다. 모델에게 경로 선택을 맡기면(에이전틱) 오히려 점수가 떨어진 사례도 있다(sunghyun 4/9 → 3/9).

## 정의

- **GraphRAG는 특정 모델이나 제품의 이름이 아니다.** 그래프에서 얻은 정보를 답변의 근거로 쓰는 접근 전체를 가리킨다(Yeongeunn, heebindev). Microsoft GraphRAG는 이 접근을 구현한 프로젝트 하나일 뿐이다. 멤버들의 구현은 모두 Neo4j 위의 간단한 로컬 조회였고, Microsoft 구현을 그대로 쓴 멤버는 없다(sunghyun이 명시).
- 질문의 축이 바뀐다. 3주차까지는 "무엇을 찾을까"였고, 6주차에는 "찾은 시작점에서 **어떤 관계를 따라** 근거를 모을까"가 됐다.

### 세 패턴

| 패턴 | 흐름 | 맞는 질문 | 6주차 구현 |
|---|---|---|---|
| **로컬 서치** | 엔티티 링킹(질문 속 표현 → 그래프 노드) → 주변 서브그래프 탐색 → 원문 근거와 함께 컨텍스트 조립 | 특정 대상과 그 관계 ("SRTN은 SJF와 어떤 관계인가") | heebindev · kdyann · sunghyun · dldusgh318 |
| **글로벌 서치** | 커뮤니티 탐지(Leiden·Louvain) → 커뮤니티별 요약을 미리 생성 → 관련 요약을 Map-Reduce로 종합 | 데이터 전체의 주제·경향 ("노트에서 주로 다룬 주제는") | **0명.** 모두 "그래프가 작아 의미 있는 커뮤니티가 안 나온다"는 이유로 공부만 했다 |
| **Text2Cypher** | 질문 + 그래프 스키마 → LLM이 Cypher 생성 → 읽기 전용으로 검증 → 실행 → 결과로 답변 | 조건·집계 ("관계가 가장 많은 엔티티는") | heebindev · kdyann · sunghyun · dldusgh318 → [[Text2Cypher]] |

- 세 패턴은 차례로 거치는 단계도 아니고 서로 배타적인 분류도 아니다(Yeongeunn). sunghyun의 구분이 정확하다. 로컬·글로벌은 **근거의 범위**를, Text2Cypher는 **질의를 누가 만드느냐**를 말한다. 그래서 특정 노드 주변을 조회하는 Cypher를 모델이 만들면 로컬 서치와 Text2Cypher가 함께 쓰인 것이다.
- 커뮤니티는 경로를 묶은 것이 아니다. 연결 구조로 나눈 노드 그룹이다. Neo4j에 적재한다고 `communityId`가 저절로 생기지 않으며, GDS 같은 도구로 탐지를 따로 돌려야 한다(sunghyun, heebindev). "노드의 communityId → 같은 그룹의 다른 노드"를 조회하는 것은 탐색 확장일 뿐이고, 요약을 종합하는 글로벌 서치와는 다르다(sunghyun).

### 하이브리드 리트리버 — 벡터로 시작점을 찾고 그래프로 넓힌다

- 벡터(또는 BM25+벡터+RRF)는 **어디서 시작할지**를 찾는다. 정확한 엔티티 이름을 몰라도 된다("AI에 관심 있던 사람" → 해당 인물 노드, e0ng). 그래프는 **그 시작점에서 무엇이 이어지는지**를 찾는다.
- ⚠️ 같은 "하이브리드"라는 말이 두 가지 뜻으로 쓰인다(Yeongeunn). 3주차의 하이브리드 검색은 BM25 + 벡터를 RRF로 융합하는 것이고([[하이브리드-검색과-RRF]]), 6주차의 하이브리드 리트리버는 벡터 검색 + 그래프 탐색이다. 그래프 결과를 합칠 때 반드시 RRF를 써야 하는 것도 아니다.
- **시작점을 잇는 두 방법** (Yeongeunn이 정리)
  - ① 노드의 이름·설명을 임베딩해 노드를 직접 찾는다.
  - ② 청크를 검색한 뒤, 그 청크를 근거로 추출된 노드로 건너간다.
  - 6주차 구현은 **전원 ②였다.** heebindev·kdyann·sunghyun은 청크의 `entity_ids`를 썼고, dldusgh318은 5주차에 근거로 저장해 둔 `chunk_id` 엣지를 그대로 진입로로 재활용했다. sunghyun은 "모든 노드를 임베딩할 필요는 없다"고 적었다. 5주차에 [[데이터-수집과-출처-추적]]에서 엣지마다 근거 청크를 남긴 결정이 여기서 진입로 역할로 돌아왔다.
- **확장 제한**
  - dldusgh318: 최대 2홉, degree 20을 넘는 허브 노드에서는 확장을 멈춘다. 예산은 청크 5,000자 + 그래프 사실 800자 + 회수 원문 2,200자. 원칙은 "그래프가 기존 검색 결과를 밀어내면 안 된다".
  - sunghyun 공개 예제: 양방향 3-hop.
  - kdyann이 정리한 토스증권 사례: 무작정 넓히면 3홉에서 후보 경로가 약 4,924만 개로 불어난다. 그래서 홉마다 점수를 매겨 상위 후보만 다음 홉으로 넘긴다. kdyann은 "탐색 깊이를 늘리는 것만으로 품질이 높아지지는 않는다"고 정리했다.

### 그래프 인덱싱 — 빌드 시점 선지불

- 엔티티·관계 추출, 중복 정리, 적재, (글로벌용) 커뮤니티 탐지·요약을 **질문 전에 배치로** 끝내 둔다. 질의 시점의 속도를 위해 빌드 시점에 시간과 비용을 먼저 내는 셈이다(e0ng, heebindev, Yeongeunn, dldusgh318). 미리 만드는 것은 **답이 아니라 나중에 검색할 재료**다(e0ng).
- DDIA 10장(일괄 처리) 관점은 세 멤버가 따로 닿은 결론이다(heebindev, Yeongeunn, dldusgh318). 원문 스냅샷이 입력이고 그래프·임베딩·요약은 다시 만들 수 있는 파생물이다. 그래서 문서 버전·청크 ID·추출 설정·근거를 함께 남겨야 한다. 이 결론은 [[데이터-수집과-출처-추적]]의 "정본/파생물" 원칙과 같다.
- dldusgh318은 여기에 맞바꿈 하나를 더 적었다. 성능과 신선도의 교환이다. 증분 갱신을 하면 [[엔티티-신원해소]] 문제가 다시 생긴다.
- sunghyun은 용어 혼동을 짚었다. 여기서 말하는 빌드는 CI의 Build Job이 아니라 검색용 데이터 준비 단계다. 모든 GraphRAG가 커뮤니티 요약을 요구하지는 않으며, 사전 계산을 해도 질문 임베딩·검색·생성 비용은 남는다.

## 강점 · 약점

| 질문 유형 | 더 맞는 방식 | 근거 |
|---|---|---|
| 원문 설명·장단점·절차 | BM25·벡터 (v1) | heebindev "SJF의 한계"는 v1과 v2가 거의 같았다. sunghyun은 이슈 재현 절차를 그래프로 찾지 못했다(양쪽 모두 실패). dldusgh318의 서술형 S01·M01·H01에서 그래프 이득이 0이었다 |
| 특정 엔티티 주변 관계 | 로컬 GraphRAG | heebindev `SRTN -IS_A-> SJF`. 다만 v1도 맞혔다 |
| 질문에 없는 중간 고리를 건너는 다중 홉 | 그래프 확장 (v2) | kdyann Recall@5 0.00~0.50 → 1.00. dldusgh318 X01 wrong → partial |
| 전체 개수·최댓값 같은 집계 | **Cypher 전체 조회** (Top-k 검색은 불가) | heebindev·kdyann·sunghyun·dldusgh318 넷 다 같다. dldusgh318은 v2(로컬 확장)도 집계에서 졌다(A1·A2 wrong)고 따로 기록했다 |
| 데이터 전체 주제 | 글로벌 GraphRAG | 미구현 |
| 그래프에 추출되지 않은 세부·수치 | 문서 검색 | heebindev "SJF 평균 처리 시간은 몇 초?"는 그래프에 수치가 없어 Text2Cypher로도 답하지 못했다 |

- **그래프 답변은 추출 품질을 넘지 못한다.** 잘못 넣은 관계는 답변에 그대로 섞이고, 빠진 사실은 그래프로 찾을 수 없다(heebindev). dldusgh318도 "그래프의 커버리지가 곧 답할 수 있는 범위"라고 적었다 → [[LLM-트리플-추출]].
- **관련 없는 관계도 끌려온다.** 청크에 연결돼 있다는 이유만으로 `job A -REQUIRES-> A runtime` 같은 관계가 컨텍스트에 섞였다(heebindev). 질문과 관계의 관련성을 따로 판단하는 단계가 필요하다.

## 멤버들이 확인한 것

| 멤버 | 데이터 · 규모 | 비교 조건 | 결과 |
|---|---|---|---|
| **kdyann** | 검토한 인스타그램 캡션 17건(내 글 14 · 참고 글 3), 질문 8 | v1: nori BM25 + multilingual-e5-small + RRF. v2: 같은 검색 결과에서 규칙 기반 라우터가 경로 선택(단순·다중 홉·추천·집계). 2026-10-08 실행 | 단순 2문항: Recall@5 1.00 / 1.00. 다중 홉·추천 4문항: v1 0.33 · 0.50 · 0.00 · 0.00 → v2 전부 1.00. 집계 2문항: v1은 보류, v2는 야구 게시물 7개 · 최다 주제 야구 7개. v2 답변 상태 answered 5 · partial 3 |
| **sunghyun** | 회사 업무·개발·테스트 플랫폼 API 스냅샷 그래프(동기화 기록 240노드 · 389관계 · 372청크, 비교 실험은 346청크 시점) | ① v1/v2 모델 비교 ② 릴리즈 집계 ③ 에이전틱 비교(GLM-5.2, 질문 4, 조회 예산 5회) | ① 사실 항목 점수 Qwen v1 3/9 → v2 9/9, GLM v1 2/9 → v2 9/9. **단 v2 일부는 Neo4j 행으로 만든 템플릿이라 "모델의 자율 추론으로 해석하지 않는다"**, 프롬프트·출력 한도도 완전히 같지 않았다. ② v2는 v0.1.0·v0.2.0 각각 Test Run 2개 · 통과 4 · 실패 0을 집계했고, v1은 검색된 6청크에 있는 일부만 보고 답했다. ③ 아래 |
| **heebindev** | 운영체제 Notion 노트 그래프(5주차, 소규모), 질문 4 | v1: BM25+벡터+RRF. v2: 진입 엔티티 + 주변 관계, 검토 대기(`review_queue`) 관계는 제외 | 관계 1문항은 둘 다 정답이고 v2가 관계를 근거로 덧붙였다. 설명 2문항은 v1로 충분했다. 집계 1문항은 둘 다 답하지 못했다. 결론은 "답변 자체가 크게 좋아지지는 않았다" |
| **dldusgh318** (PR #45 미머지) | 20청크 표본 그래프(Project 3 · Technology 25 · TechnologyUse 41), 질문 7, v1/v2 각 3회 다수결 | v1: BM25·벡터 각 top-50 + RRF k=60, top-5. v2: top-5 청크의 chunk_id로 진입, 최대 2홉, 허브 제외 | v2가 v1보다 나아진 것은 **X01 하나(wrong → partial)**뿐이다. 서술형 S01·M01·H01은 같았다. 집계 A1·A2는 둘 다 wrong. **그래프를 거쳐 컨텍스트에 들어온 정답 청크는 전 문항 0건.** 실험 전 가설은 "X01·X03은 v2가 맞힌다"였지만 X03은 둘 다 partial이었다 |
| **Yeongeunn** | 팀 서비스 Notion 소규모 그래프 | 질문 유형 5종(단일 사실·다중 홉·집계·설명·근거 없음)으로 비교 설계, 고정 입력 비교 코드 | **수치 없음.** 결과는 저장소 밖 `data/`에만 있다 |
| **e0ng** | 가상 예시 그래프 | 이론 정리(로컬·글로벌·Text2Cypher·하이브리드·인덱싱) | 측정 없음 |

### 고정 경로 vs 에이전틱 — 그래프 도구를 줬더니 점수가 떨어졌다 (sunghyun)

- **조건**: 같은 청크 346개, 같은 질문 4개, 같은 출력 한도, 최대 5회 조회 예산. 모델에는 정답을 주지 않았다. 질문마다 1회씩 실행했다.

| 방식 | 사실 항목 정답 | 모델 호출 | 입력 / 출력 토큰 | 총 시간 |
|---|---:|---:|---:|---:|
| 그래프 없이 검색·원문·목록 | 4/9 | 22 | 61,988 / 7,858 | 117.7초 |
| 같은 도구 + 그래프 조회 | 3/9 | 18 | 82,083 / 6,296 | 82.7초 |

- **틀린 원인은 경로 선택이었다.** "Test Case가 연결되지 않은 Task" 질문에서 모델은 실제 경로 Task→Issue→Test Case 대신 Task→Test Case 직접 연결을 조회했다. 직접 관계가 없다는 사실을 "테스트가 없다"로 읽어 18개라고 답했고, 정답은 13개다. 그래프 없는 쪽은 UNKNOWN이었다. sunghyun은 "그래프 조회 횟수가 많다고 경로가 맞는 것은 아니다"라고 적었고, 부족한 근거를 인정한 UNKNOWN과 잘못된 집계를 단정한 답을 구분해서 기록했다.
- 모델 호출은 줄었지만 입력 토큰은 늘었다. 그래서 sunghyun은 "더 저렴하다"고 결론 내리지 않았다.
- 코드가 경로를 정한 고정 v2는 9/9였다. **같은 그래프라도 경로를 누가 고르느냐에 따라 결과가 갈렸다.**
- dldusgh318은 반대 방향에서 같은 결론에 닿았다. "실패 원인이 늘어난다"는 이유로 LLM 라우터를 빼고 규칙 기반 확장만 썼다. kdyann의 라우터도 규칙 기반이었고, kdyann은 "범용 플래너가 아니다"라고 스스로 밝혔다.
- 연결 페이지: [[쿼리-재작성]](Agentic 계열), [[RAG-변천사]].

## 함정 · 주의

- **확장에 성공해도 근거 회수는 실패할 수 있다** (dldusgh318). 회수 예산을 chunk_id 순서대로 채우자 무관한 청크가 먼저 자리를 차지했다. v2.1에서 후보를 질문과의 bge-m3 코사인 유사도 순으로 바꾸자 답이 구체화됐지만, 판정은 여전히 partial이고 recall도 0.5 그대로였다. 정답 청크가 애초에 회수 후보에 없었기 때문이다. 결론은 "확장 결과도 다시 순위를 매겨야 한다"는 것이다 → [[리랭커]].
- **검토 안 된 관계는 리트리버에서 빼고, 집계에서도 빼야 한다** (heebindev). 닫힌 스키마에 억지로 맞춘 관계(`SJF -PREVENTS-> 평균 Turnaround time`)는 `predicate: null`로 `review_queue.json`에 모으고 v2 근거에서 제외했다. 그런데 Text2Cypher는 Neo4j를 직접 조회하기 때문에 그 관계까지 개수에 포함했다. 그래서 필터를 리트리버와 질의 실행 단계 **양쪽에** 둬야 한다 → [[폐쇄-스키마-설계]].
- **관계 이름은 그 이름 이상을 말하지 않는다.** sunghyun의 `relatedCommit`은 관련 커밋일 뿐 수정 완료가 아니고, `forRelease`는 릴리즈 배정일 뿐 검증 통과가 아니다. kungbi의 `CALLS_WITH`도 코드상의 정적 사용일 뿐 실제 요청 성공이 아니다. 그래프에 승인·완료 사실이 저장돼 있지 않으면 LLM이 그것을 만들어 답해서는 안 된다 → [[데이터-수집과-출처-추적]].
- **그래프 범위를 결과와 함께 적어라.** 특정 질문에 맞춰 보완한 작은 그래프의 결과를 전체 데이터의 성능으로 일반화하면 안 된다(Yeongeunn). dldusgh318의 집계 질문 A1·A2는 그래프가 20청크 표본이라 처음부터 답할 수 없었다.
- **단일 실행은 결론을 뒤집는다** (dldusgh318). X03은 1회 실행에서 correct였지만 3회 다수결로는 partial이었다. 2회차 판정 하나만 바꿔도 다수결이 뒤집힌다. sunghyun의 에이전틱 비교도 질문당 1회 실행이다.
- **공개 예제와 실측을 섞지 마라.** sunghyun과 kungbi는 회사 데이터를 쓰지 않고 합성 데이터 공개 예제를 따로 만들었고, 실측 수치를 공개 예제의 성능으로 주장하지 않았다 → [[개인-데이터-가명화와-공개-범위]].

## 열린 질문

- **공정 비교는 여전히 미완이다.**
  - 다섯 멤버 모두 그래프 범위가 청크 검색 범위보다 좁았다(kdyann 17건, dldusgh318 20청크 표본, heebindev 소규모).
  - 같은 Gold로 Recall까지 잰 것은 kdyann과 dldusgh318 둘뿐이다.
  - 전체 코퍼스로 그래프를 만든 뒤 다시 비교하는 일이 남았다. dldusgh318은 전체 1,562청크 추출을 다음 일로 적었다 → [[RAG-vs-그래프-질의]].
- 에이전틱 검색에서 경로 선택 오류를 줄이는 방법은 아직 없다. 스키마의 경로 방향을 프롬프트에 넣는 것(sunghyun의 제안)이 효과가 있는지는 측정되지 않았다.
- 글로벌 서치는 아무도 구현하지 않았다. 그래프가 어느 규모가 되면 커뮤니티 요약이 의미를 갖는지 아는 사람이 없다.
- 그래프 근거와 청크 근거의 인용 형식. heebindev는 `[D번호]`와 `[G번호]`를 나눴고, kdyann은 답변이 그래프 경로를 직접 인용하지 않은 사례를 남겼다 → [[RAG-루프와-근거-인용]].

## 관련

- [[RAG-vs-그래프-질의]] · [[Text2Cypher]] · [[멀티홉-질문과-Bridge-Entity]] · [[하이브리드-검색과-RRF]] · [[그래프-적재-Postgres와-Neo4j]] · [[LLM-트리플-추출]] · [[폐쇄-스키마-설계]] · [[엔티티-신원해소]] · [[데이터-수집과-출처-추적]] · [[RAG-변천사]] · [[쿼리-재작성]] · [[리랭커]] · [[지식그래프와-온톨로지]] · [[실습-비교표]]

## 출처

- e0ng · GraphRAG 패턴 — [members/e0ng/notes/06-1-graphrag-patterns.md](../../members/e0ng/notes/06-1-graphrag-patterns.md); 하이브리드 리트리버 — [06-2-hybrid-retriever.md](../../members/e0ng/notes/06-2-hybrid-retriever.md); 그래프 인덱싱과 빌드 시점 선지불 — [06-3-graph-indexing.md](../../members/e0ng/notes/06-3-graph-indexing.md)
- heebindev · GraphRAG - 검색과 그래프의 결합 — [members/heebindev/notes/06-graphrag.md](../../members/heebindev/notes/06-graphrag.md); GraphRAG 에이전트 v2 실습 — [labs/04-graphrag-agent/README.md](../../members/heebindev/labs/04-graphrag-agent/README.md)
- kdyann · GraphRAG — 검색과 그래프의 결합 (§토스증권 사례) — [members/kdyann/notes/06-graphrag.md](../../members/kdyann/notes/06-graphrag.md); W6 실습 — [labs/06-graphrag/README.md](../../members/kdyann/labs/06-graphrag/README.md)
- sunghyun · 검색에 그래프를 붙이고 같은 질문으로 비교하기 — [members/sunghyun/notes/06-graphrag-and-agentic-search.md](../../members/sunghyun/notes/06-graphrag-and-agentic-search.md); GraphRAG와 에이전틱 검색 비교 — [labs/06-graphrag/README.md](../../members/sunghyun/labs/06-graphrag/README.md) (수치 원본 `measured-summary.json`)
- Yeongeunn · GraphRAG — 검색과 그래프의 결합 — [members/Yeongeunn/notes/13-week6-graphrag.md](../../members/Yeongeunn/notes/13-week6-graphrag.md)
- dldusgh318 · 6주차 GraphRAG·하이브리드 리트리버·그래프 인덱싱 노트, `WEEK6_V2.md`, `results/w6_compare.md`·`v1_w6_score.md`·`v21_x01_report.md`, `labs/WEEK6_result.md` — `members/dldusgh318/` (PR #45 미머지)
- kungbi · 근거 기반 Knowledge Graph 구축 방법과 합성 예제 — [members/kungbi/labs/02-evidence-grounded-knowledge-graph/README.md](../../members/kungbi/labs/02-evidence-grounded-knowledge-graph/README.md)
- Microsoft GraphRAG Query Engine — https://microsoft.github.io/graphrag/query/overview/ · Local Search — https://microsoft.github.io/graphrag/query/local_search/ · Global Search — https://microsoft.github.io/graphrag/query/global_search/ · Indexing — https://microsoft.github.io/graphrag/index/overview/
- 토스증권 추천과 검색은 어떻게 진화하고 있을까? (kdyann 인용) — https://toss.tech/article/tech_talk_talk_3
