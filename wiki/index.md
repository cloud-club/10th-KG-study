---
title: Index
type: resource
tags: [methodology]
status: maintained
created: 2026-09-16
updated: 2026-09-16
---

# Index

스터디 위키 전체 카탈로그. 질문에 답할 때 먼저 여기서 관련 페이지를 찾고 들어간다. 모든 ingest마다 갱신한다.
구조: PARA(끝이 있으면 project · 반복이면 area · 찾아보려 두면 resource · 안 열면 archive). 규칙은 루트 `CLAUDE.md`.
소재(`members/`)는 여기 개별로 싣지 않고 [[스터디-노트-지도]]에서 찾는다.

## Pending (`0-pending/`)

- 분류 전 메모. 정리 요청 시 아래로 분류하고 삭제한다. 현재 비어 있음.
- 머지 대기 소재(2026-09-16): PR #6 sese2204 인프라·카카오톡 실습 · PR #11 ur2e 옵시디언 검색 · PR #12 heebindev 공용 인프라 이전 · PR #15 lys0611 W1~W3. 전부 ingest됨, 출처에 `(PR #n 미머지)` 표시. 머지되면 표시를 지운다.

## Projects (`1-projects/`)

- [[10기-KG-스터디]] — 기수 운영 허브. 타임라인, 주차별 주제(재구성), 멤버 14명과 반, 의사결정, 남은 일.
- 공용 골든셋 — 제안 단계(sese2204 07 스터디 질문). 결정되면 여기 페이지. 현황은 [[RAG-평가-지표]] 열린 질문.

## Areas (`2-areas/`)

- [[로컬-인프라]] — 공용 docker compose(PG17+pgvector, ES9+nori, Neo4j 5.26+APOC) 사용 기준, 겪은 문제, 자체 compose를 쓴 멤버들의 구성.
- [[현황판]] — GitHub Pages 현황판의 빌드·배포 루틴, 스캔 범위, 놓치는 경로.

## Resources (`3-resources/`)

### 검색 (2주차)
- [[검색의-세-세대]] — grep·BM25·벡터 한 표 비교, 아홉 멤버의 실측, 검색 단위·질의 통일에 관한 모순.
- [[grep-문자열-매칭]] — 0세대. 표현 불일치·순위 없음·줄 단위, 멤버별 0건 사례.
- [[역색인과-BM25]] — 역색인, TF-IDF(DF≠CF), BM25 수식과 k1·b, 점수는 절대값이 아님, OR 매치 함정.
- [[한국어-토크나이징-nori와-n-gram]] — nori(`decompound_mode`, 사용자 사전)와 n-gram 병행, "분석기가 만든 토큰이 검색의 입력", stopword·title 부스트 함정.
- [[임베딩과-벡터-검색]] — 임베딩 공간, 코사인/pgvector `<=>`, 잘 잡는 것과 놓치는 것, "의미로 이긴 게 아니었다"(ur2e).
- [[HNSW와-pgvector-인덱스]] — ANN과 recall 교환, 파라미터 기본값, 플래너가 인덱스를 안 타는 경우, 필터+ANN.
- [[청킹-전략]] — 문헌 기준선 512토큰 vs 대화 데이터의 세션 경계, 멤버별 경계 규칙 표, heading vs fixed 실측.
- [[임베딩-모델-선택]] — MTEB의 함정, 고르는 축 6개, 멤버들이 쓴 모델 표(ko-sroberta·KURE·bge-m3·e5).

### 하이브리드·RAG (3주차)
- [[하이브리드-검색과-RRF]] — 왜 합치나, 정규화가 안 되는 이유, RRF 수식 k=60, dldusgh318·lys0611 Recall 표, R@10에서 BM25가 이기는 비용.
- [[리랭커]] — 회수와 재정렬 분업, 구조 계보, recall@100 vs @5 격차로 도입 판단, 상시 vs 조건부 모순.
- [[쿼리-재작성]] — Multi-query·HyDE·Step-back·분해·Adaptive 카탈로그, 재검색의 한계, "회수율 충분하면 순손해".
- [[RAG-루프와-근거-인용]] — 5단계, Context 조립, Citation/Grounding, lys0611 34문항(생성 실패 12 vs 검색 실패 2), Ollama 함정.
- [[RAG-실패-유형]] — 네 분류 축의 대응표, Oracle Context 실험, "Gold 누락 ≠ 검색 실패", R0~G4 코드.
- [[멀티홉-질문과-Bridge-Entity]] — 왜 한 번의 검색으로 안 되나, 집계 한계, 세 갈래 처방(재검색·분해·그래프), 4주차 스키마 후보.
- [[RAG-평가-지표]] — 지표 정의표, 골든셋 만들기(pooling·evidence group·content_hash), 멤버별 평가셋 현황, Recall≠Answerability.
- [[RAG-변천사]] — sese2204 4기 vs kdyann 6기 연표, Adaptive RAG 자리와 BEIR 강도의 모순, 논문 링크 11편.

### 지식그래프·데이터 (1주차, 4주차~)
- [[지식그래프와-온톨로지]] — 용어표, Neo4j vs RDF+온톨로지, 왜 검색 다음이 그래프인가, 정본 아키텍처 모순.
- [[OpenViking-컨텍스트-데이터베이스]] — Resource·Memory·Skill, L0/L1/L2, Retrieval≠Validation, KG와의 경계.
- [[데이터-수집과-출처-추적]] — kungbi 수집 계약·provenance 경로(미구현), 카카오톡 실습들의 정본/파생물 원칙.
- [[카카오톡-대화-내보내기-파싱]] — 기기별 형식, 날짜 구분선·시스템 줄·첨부 파일명·초 없음, 내보내기 함정, 멤버별 결과.
- [[개인-데이터-가명화와-공개-범위]] — 공통 규칙, 가명화를 임베딩 앞에 두는 파이프라인과 법적·약관 근거, 로컬 vs 외부 API 표.

### 도구 함정·비교
- [[PostgreSQL과-pgvector-함정]] — pg_trgm 로케일·word_similarity·GIN 미사용, HNSW 플래너·COPY·필터, pg18 볼륨 경로, 포트.
- [[Elasticsearch-운영-함정]] — nori 설치, 메모리, 버전 불일치, 기본 OR, best_fields, refresh.
- [[저장-구조-LSM과-B-tree]] — DDIA 3장을 Postgres·ES에 대입(lys0611 단독), 실행 계획을 보라.
- [[실습-비교표]] — 열한 실습의 데이터·인프라·임베딩·청킹·검색기·평가 한 표, 갈리는 지점.
- [[스터디-노트-지도]] — 모든 소재 → 위키 페이지 대응표. 린트의 기준.
- [[LLM-위키-패턴]] — 이 위키가 따르는 방법론 원문(Karpathy). 편집하지 않는다.

## Archives (`4-archives/`)

- 비어 있음.
