---
title: Index
type: source
tags: [map]
status: maintained
created: 2026-09-16
updated: 2026-10-02
---

# Index

스터디 위키 전체 카탈로그. 질문에 답할 때 먼저 여기서 관련 페이지를 찾고 들어간다. 모든 ingest마다 갱신한다.
구조: 페이지 종류별 폴더 — `concepts/`(개념·방법) · `entities/`(도구·인프라·기수 같은 고유명사) · `comparisons/`(비교표) ·
`sources/`(소재 대응표·원문) · `inbox/`(분류 전 메모). 규칙은 루트 `CLAUDE.md`.
소재(`members/`)는 여기 개별로 싣지 않고 [[스터디-노트-지도]]에서 찾는다. 밀린 소재는 `python3 scripts/wiki_backlog.py`.

## Inbox (`inbox/`)

- 분류 전 메모. 정리 요청 시 아래로 분류하고 삭제한다. 현재 비어 있음.
- 머지 대기 소재(2026-10-02): PR #6 sese2204 카카오톡 실습 · PR #11 ur2e 옵시디언 검색 · PR #19 yujeong430 3~4주차 노트·40문항 평가 · PR #34·#36 e0ng 5주차 노트·그래프 적재. 전부 ingest됨, 출처에 `(PR #n 미머지)` 표시. 머지되면 주간 자동 ingest가 표시를 지운다.

## Concepts (`concepts/`)

### 검색 (2주차)
- [[grep-문자열-매칭]] — 0세대. 표현 불일치·순위 없음·줄 단위, 열두 멤버의 0건 사례(자연어 질문 전체 10/10 실패 등).
- [[역색인과-BM25]] — 역색인, TF-IDF(DF≠CF), BM25 수식과 k1·b, OR/AND는 후보 조건이고 점수는 순위(OR 709 vs AND 1), 제목 vs 본문 색인.
- [[한국어-토크나이징-nori와-n-gram]] — nori(`decompound_mode`, 사용자 사전)와 n-gram 병행, "분석기가 만든 토큰이 검색의 입력", bigram 두 뜻 혼동, stopword·title 부스트 함정.
- [[임베딩과-벡터-검색]] — 임베딩 공간, 코사인/pgvector `<=>`, 잘 잡는 것과 놓치는 것, 임베딩에 무엇을 넣느냐(경로·제목 결합의 부작용), 코드·스펙 텍스트의 약점.
- [[HNSW와-pgvector-인덱스]] — ANN과 recall 교환, 파라미터, 플래너가 안 타는 경우와 강제하는 법, exact vs HNSW 10.2배·일치율 1.0 실측, 필터+ANN, recall의 두 뜻.
- [[청킹-전략]] — 문헌 기준선 512토큰 vs 대화 데이터의 세션 경계, 열세 멤버의 경계 규칙 표, heading vs fixed 실측, 청킹 길이와 임베딩 입력 길이의 불일치.

### 하이브리드·RAG·평가 (3주차)
- [[하이브리드-검색과-RRF]] — 왜 합치나, 정규화 융합이 이긴 반례(do-dop), RRF 수식·k·ES 파라미터, **열한 평가셋**의 RRF 성적표(승·동률·패), 공통 패배 메커니즘, 후보 수 가설.
- [[리랭커]] — 회수와 재정렬 분업, 구조 계보, recall@100 vs @5 격차로 도입 판단, nDCG와의 관계, 상시 vs 조건부 모순. 실측 0.
- [[쿼리-재작성]] — Multi-query·HyDE·Step-back·분해·Adaptive 카탈로그, 분해의 독립 vs 순차 의존 실측, 재검색 모델 크기별 실측, Self-RAG ≠ CRAG ≠ Agentic.
- [[RAG-루프와-근거-인용]] — 5단계, Context 조립, Citation 3단계 사다리(Existence·Relevance·Entailment), 인용 자동 검증 강도 5단계 표, 열 멤버의 생성 실측(검토자 LLM, 약어 환각, temperature), 정직한 거절의 채점 문제.
- [[RAG-실패-유형]] — 네 분류 축의 대응표, Oracle Context 실험(X01–X03, Oracle도 틀린 사례), 코드가 없는 실패들(융합 탈락·엔티티 귀속·연결 실패·라벨 누락), 멀티홉 7유형(확인 2·미확인 5), 부정 질문과 OWA.
- [[멀티홉-질문과-Bridge-Entity]] — 왜 한 번의 검색으로 안 되나, 브릿지 숨김 실험 X01, 세 갈래 처방(재검색·분해·그래프)의 실측, "다중 홉이라고 그래프가 필요한 건 아니다"(세 반례), 5칸 템플릿, 시간 조건.
- [[RAG-평가-지표]] — 지표 정의표(검색·생성·추출·시스템 4층), 골든셋 만들기(pooling·evidence group·content_hash·개발/테스트 분리), **누가 정답을 정했나** 5갈래, 열세 멤버 평가셋 현황, 엄격도가 수치를 지배.
- [[챗봇-평가-층위와-심판]] — 검색·생성·대화·시스템 4층, 기준 5종(reference-free는 근거가 틀리면 만점), 심판 4종과 LLM-as-judge 편향 3종·보정, RGB·MTRAG·RAGChecker.
- [[LLM-위키의-한계와-비판]] — 이 위키가 따르는 패턴의 비용 오해(아끼는 건 검색이 아니라 advanced RAG 호출), 비판 7종과 대응, Joi Ito의 "모순은 누가 이기나" 공백.

### 지식그래프 이론 (1주차, 4주차)
- [[지식그래프와-온톨로지]] — **KG 허브.** 용어표(엔티티·트리플·온톨로지·RDF·RDFS/OWL·추론·OWA·SPARQL/Cypher), 역사와 방향, 모델·저장소 결정표, 다섯 멤버가 만든 그래프 요약, 열린 질문.
- [[RDF와-트리플]] — 세 칸(IRI·Literal·Blank Node), 타입·언어 태그, 네임스페이스, Turtle, n항 관계와 reification(중간 노드·Wikidata statement·대출 반례), 직렬화와 내보내기(Turtle·JSON-LD, evidence 위치, 사실 수≠트리플 수).
- [[온톨로지와-추론]] — RDF/RDFS/OWL 세 층, TBox/ABox, 추론≠탐색, `domain`/`range`는 검증이 아니다(일곱 멤버 수렴, SHACL), OWL로 안 되는 것, 열린 세계 가정과 부정 질문, 닫힌 스키마≠닫힌 세계, 스키마 vs 온톨로지 세 입장.
- [[SPARQL]] — 트리플 패턴, 변수 공유=조인=멀티홉, OPTIONAL·Property Path, 여섯 멤버의 공개 endpoint 실행표, label 서비스·LIMIT 함정, "잘못된 관계를 정확히 조회할 뿐".
- [[데이터-수집과-출처-추적]] — kungbi 수집 계약·provenance, 카카오톡 실습의 정본/파생물 원칙, 수집 대상 선정(네 멤버), Citation vs Provenance(6질문·PROV), 5주차 엣지 단위 근거·검토 상태 표, 정본 3단(원문→검토 파일→저장소).
- [[카카오톡-대화-내보내기-파싱]] — 기기별 형식, 날짜 구분선·시스템 줄·첨부 파일명·초 없음, 내보내기 함정, 멤버별 결과.
- [[개인-데이터-가명화와-공개-범위]] — 공통 규칙, 가명화를 임베딩 앞에, 로컬 vs 외부 API 표, 3~5주차의 경계 변화(임베딩 로컬·추출 외부), 평가셋 공개 가능성, 공개 범위 규칙 사례.
- [[저장-구조-LSM과-B-tree]] — DDIA 3장을 Postgres·ES에 대입(lys0611·Yeongeunn), 실행 계획을 보라, DDIA 2장의 자리.

### 그래프 구축 (5주차)
- [[폐쇄-스키마-설계]] — 역량 질문에서 역으로, 설계 방법론 5종(e0ng), 여섯 멤버의 스키마 표(클래스 5·술어 7 수렴), 닫힌 스키마의 억지 매핑 실측(8건 중 3건 오류), 문자열 속성은 자유 텍스트.
- [[LLM-트리플-추출]] — 출력은 후보다: Structured Outputs·빈 배열 게이트·evidence 완전일치·ID 정규화·탈락 저장, NER/개체 연결/RE 분해와 평가, 다섯 멤버 실측(통과율 99.38% vs 의미 오류 3/8), JSON 절단·ID 공백·과잉 생성·NULL, extraction_run.
- [[엔티티-신원해소]] — IRI·Q ID·sameAs는 판단을 대신하지 않는다, 과잉 분리(45노드→32쌍, 병합 키 5규칙) vs 과잉 병합(회귀 테스트), 넓은 단어 동일시 금지, IRI 규칙 비교(음차 vs 번역).
- [[그래프-적재-Postgres와-Neo4j]] — 세 저장소의 역할(Triplestore 0명), PG 테이블 다섯 설계, MERGE와 멱등성(`edge_key` SHA-256, 리터럴↔속성 변환), Cypher vs SQL 줄 수, 가변 경로 제한, 0건 진단 순서, 비밀번호 평문 주의.

## Entities (`entities/`)

- [[10기-KG-스터디]] — 기수 운영 허브. 타임라인(1~5주차), 주차별 주제, 멤버 14명과 진행, 의사결정, 남은 일(열린 PR·현황판 미스캔 경로·소재 정정 요청).
- [[로컬-인프라]] — 공용 docker compose(PG17+pgvector, ES9+nori, Neo4j 5.26+APOC) 사용 기준, 겪은 문제, 자체 compose 멤버 여섯 구성, 5주차 Neo4j 첫 실사용, 공개 SPARQL endpoint 경로.
- [[현황판]] — GitHub Pages 현황판의 빌드·배포 루틴, 스캔 범위, 놓치는 경로.
- [[PostgreSQL과-pgvector-함정]] — pg_trgm 로케일·word_similarity·GIN 미사용, HNSW 플래너·COPY·필터, exact/HNSW 기준선 만들기, pg18 볼륨, 포트, 그래프 질의의 재귀 CTE.
- [[Elasticsearch-운영-함정]] — nori 설치, 메모리, 버전 불일치(여섯 버전), 기본 OR, best_fields, refresh, 재색인 시 삭제 미반영, 속도 vs 품질 조정 지점.
- [[OpenViking-컨텍스트-데이터베이스]] — Resource·Memory·Skill, L0/L1/L2, Retrieval≠Validation, KG와의 경계(4주차 보강).
- [[Wikidata와-DBpedia]] — 두 공개 KG의 데이터 모델, Q/P·접두어 5종·claim vs statement·rank/truthy, 스터디 그래프로의 번역(review_status·valid_from/to·source_version, 체크리스트 5), 실행 함정.
- [[Palantir-Foundry-Ontology]] — Object·Property·Link·**Action**·Function, Semantic/Kinetic, Writeback 경계, "Action ≠ 추론", RDF·OWL과의 비교. 일곱 멤버 정리.
- [[RAGAS]] — 정답 필드별 쓸 수 있는 지표, 같은 이름 다른 정의, 합성 테스트셋(KG 기반, MultiHopSpecific), 타임라인(2026-03 이후 머지 0건), 정직한 거절 감점·한국어 함정 4·비결정성.
- [[BEIR]] — zero-shot 검색 벤치마크(9태스크·18데이터셋), "BM25는 강한 기준선"의 원문, pooling 편향(TREC-COVID), 결론 강도 모순 판정.
- 공용 골든셋 — 제안 단계(sese2204 200개 배분안). 결정되면 여기 페이지. 현황은 [[RAG-평가-지표]] 열린 질문.

## Comparisons (`comparisons/`)

- [[검색의-세-세대]] — grep·BM25·벡터 한 표 비교, 열한 멤버의 실측(sdunge 동의어·sunghyun OR/AND·Yeongeunn grep 0/10 추가), 검색 단위·질의 통일 모순과 3주차의 해소.
- [[임베딩-모델-선택]] — MTEB의 함정, 고르는 축 6개, 멤버들이 쓴 모델 표(네 계열·열두 멤버), 평가셋≠벤치마크, 고정·기록 7항목, revision 고정.
- [[생성-모델-선택]] — 열 멤버·아홉 모델 레지스트리(로컬 7B vs 외부 API), 선택 기준은 데이터 민감도, 모델 크기로 풀리는 것과 안 풀리는 것, 블라인드 비교 절차.
- [[모델-역할-분담]] — 개체 추출·관계 추출·임베딩·생성·심판 역할별 입출력·평가·모델 종류, 파이프라인 3안, LLM에 맡기는 면적.
- [[RAG-변천사]] — sese2204 4기 vs kdyann 6기 연표, Adaptive RAG 자리 모순, BEIR 강도 판정(완화), Self-RAG/CRAG/Agentic 정밀화, GraphRAG의 자리, 스터디 실측으로 본 변천사.
- [[실습-비교표]] — 스물여섯 실습의 데이터·인프라·임베딩·청킹·검색기·평가 표 + 그래프 실습 표(스키마·추출·PG·Turtle·Neo4j·질의), 갈리는 지점 열 개(라벨러·공개 가능성·도달 단계·재현성).
- [[시맨틱-웹에서-지식그래프까지]] — 2001~현재 연표(얻은 것·남은 문제·멤버별 각도), 조정 문제와 "실패"의 분해, schema.org 반례, 온톨로지라는 말의 계보, 멀티홉 실패의 네 층위, 스터디로의 환류.
- [[RDF와-프로퍼티-그래프]] — 9축 비교표, 용어 충돌·스키마 선택적의 뜻·모델≠세계 가정·성능 신화, 관계형 모델도 관계를 표현한다, Neo4j vs Postgres 시작 판단의 갈림.
- [[기업-지식그래프-사례]] — Google·Amazon AutoKnow·COSMO·LinkedIn·Siemens·AstraZeneca·Apple 표, 각 사례가 보장하지 않는 것, 공통 과제 4, LLM 생성 관계는 후보.
- [[RAG-vs-그래프-질의]] — 같은 질문을 RAG와 그래프에 던진 여섯 사례, RAG로 충분했던 것·안 되는 것, "경로 없음"은 답인가 모름인가(모순), 공정 비교는 아직 없다.

## Sources (`sources/`)

- [[스터디-노트-지도]] — 모든 소재 → 위키 페이지 대응표(14명, 2026-10-02 기준). 린트의 기준.
- [[LLM-위키-패턴]] — 이 위키가 따르는 방법론 원문(Karpathy). 편집하지 않는다.

## Archived

- 비어 있음. 끝난 기수·낡은 페이지는 폴더를 옮기지 않고 `status: archived`로 표시하고 여기로 항목을 옮긴다.
