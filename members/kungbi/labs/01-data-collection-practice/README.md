---
title: "Knowledge Graph 데이터 수집, 어떻게 실습할까?"
date: 2026-09-12
tags: [knowledge-graph, data-collection, provenance]
status: in-progress
---

# 01. Knowledge Graph 데이터 수집, 어떻게 실습할까?

> 관련 노트: [OpenViking: 무엇을 기억하고 무엇을 다시 확인할까?][openviking-note]

## 목표

Knowledge Graph 구축에 필요한 데이터를 무작정 많이 모으기보다, 작은 공개 데이터
하나로 **수집 → 원문 보존 → 정규화 → 관계 생성 → 근거 확인**의 전체 경로를
검증한다.

## 문서 상태

이 문서는 수집을 완료한 결과 보고서가 아니다. 준비한 발표 자료를 바탕으로 어떤
순서와 기준으로 수집 실습을 진행할지 정의한 계획이며, 실제로 확인한 결과와 아직
구현하지 않은 부분을 구분한다.

## 실습에서 답할 질문

> 수집한 사실에서 출발해 그 사실을 만든 원본과 수집 시점까지 다시 추적할 수 있는가?

첫 실습은 공개 Git 저장소 하나를 대상으로 다음 질문에 답하는 것을 목표로 한다.

- 특정 파일은 어떤 commit에서 변경되었는가?
- 해당 commit은 어떤 이전 상태를 기준으로 만들어졌는가?
- 정규화한 파일·commit 관계에서 실제 diff까지 돌아갈 수 있는가?
- 같은 범위를 다시 수집해도 중복 row가 생기지 않는가?
- 일부 수집이 실패했을 때 완료된 범위와 누락된 범위를 구분할 수 있는가?

## 범위

### 첫 번째 대상

- 공개 Git 저장소 1개
- 기본 브랜치의 commit과 변경 파일
- 실습에 필요한 최소 메타데이터와 diff

Git을 먼저 선택한 이유는 commit SHA와 blob ID라는 안정적인 식별자가 있고, 이력과
변경 근거를 로컬에서 재현할 수 있으며, Slack·Notion·AWS보다 개인정보와 인증정보를
통제하기 쉽기 때문이다.

### 이후 확장 대상

- Slack: channel → thread → message → revision
- Notion: data source → page → block tree → revision
- GitHub: PR → review → commit → diff
- AWS: account → resource → observation → relation observation

처음부터 네 원천을 동시에 구현하지 않는다. Git 수집의 end-to-end 경로가 검증된 뒤 같은 수집 계약을 원천별로 확장한다.

## 공개 데이터와 제외 데이터

- 저장소에는 공개 저장소에서 재현 가능한 최소 샘플만 포함한다.
- 실제 Slack 메시지, 비공개 Notion 페이지, 운영 AWS 응답은 포함하지 않는다.
- 토큰, 쿠키, 이메일, 로컬 경로, 계정명, 내부 저장소 이름은 커밋하지 않는다.
- 원문 payload는 민감정보를 제거한 fixture만 공개한다.
- 실제 수집 데이터는 Git 밖의 로컬 저장소에서 관리한다.

## 사전 예상

- 최신 상태만 저장하면 어떤 변경이 언제 일어났는지 복원하기 어렵다.
- 원문만 적재하면 파일·commit·PR 사이의 관계를 반복해서 계산해야 한다.
- 현재 상태, 시간 이력, 검색 문서, 관계, provenance를 분리하면 질의와 재처리를 함께 다룰 수 있다.
- 실시간 event부터 시작하는 것보다 정확한 backfill을 먼저 만드는 편이 누락과 중복을 발견하기 쉽다.

## 실습 순서

### 1. 질문과 수집 계약 고정

먼저 수집량이 아니라 검증할 질문을 정한다. 이어서 source, scope, native ID,
관측 시각, redaction 규칙, 완전성 상태를 수집 계약으로 기록한다.

```text
source        git
scope         repository + default branch
native ID     commit SHA / blob ID / file path
observed_at   수집기가 실제로 관측한 시각
completeness  complete / partial / denied / error
```

### 2. 작은 Backfill 수행

공개 저장소의 기본 브랜치에서 commit과 변경 파일을 읽는다. 첫 실행은 전체 운영
데이터를 가져오는 대신, 전체 흐름을 확인할 수 있는 제한된 범위로 시작한다.

예정 산출물:

```text
data/
├── raw/                  # API·CLI 원문 fixture
└── processed/            # 정규화한 공개 샘플
```

원문에는 payload hash를 남기고, 정규화 row에는 어떤 ingestion run과 payload에서 만들어졌는지 연결한다.

### 3. 원문·현재·이력·검색·관계 분리

```text
원문 payload
  → 현재 commit / file 상태
  → commit과 변경 이력
  → 검색 가능한 document / chunk
  → commit -[CHANGED]-> file 관계
```

PostgreSQL을 canonical source로 두고, graph DB와 vector index는 필요할 때 다시
만들 수 있는 projection으로 취급한다.

### 4. Provenance 역추적

정규화된 사실 하나를 선택해 다음 경로가 끊기지 않는지 확인한다.

```text
file relation
  → commit
  → ingestion run
  → source payload
  → 실제 diff
```

성공 기준은 관계가 존재하는 것만이 아니라, 관계를 만든 근거와 관측 시점까지 확인할 수 있는 것이다.

### 5. 동일 범위 재수집

같은 범위를 다시 수집하고 native ID와 unique constraint를 기준으로 중복이 생기지
않는지 확인한다. payload가 같으면 동일 hash로 판별하고, 값이 바뀌면 현재 상태를
갱신하면서 이전 관측은 이력으로 남긴다.

### 6. 증분 수집과 Reconciliation

Backfill이 안정된 뒤 새 commit만 반영하는 증분 수집을 추가한다. event나 cursor로
빠르게 변경을 반영하더라도, 주기적인 전체 비교로 누락·삭제·drift를 검증한다.

```text
Backfill → Enrichment → Incremental → Reconciliation
```

### 7. 질문으로 검증

최소한 다음 검증을 통과해야 첫 수집 실습을 완료로 본다.

| 검증 | 성공 기준 |
| --- | --- |
| 재현성 | 문서의 명령으로 같은 공개 샘플을 다시 만들 수 있음 |
| 멱등성 | 같은 범위를 두 번 수집해도 중복이 생기지 않음 |
| 완전성 | 성공·부분 성공·권한 거부·실패를 구분함 |
| provenance | 정규화한 사실에서 원문과 diff로 돌아갈 수 있음 |
| 관계 질의 | commit과 변경 파일의 연결을 조회할 수 있음 |
| 개인정보 | 비공개 원문·토큰·계정 식별자가 Git에 포함되지 않음 |

## 환경

### 현재 발표 자료

- 실행 환경: 최신 웹 브라우저
- 외부 서비스 및 키: 필요 없음
- 파일: [`presentation.html`](presentation.html)

### 수집 실습 예정 환경

- 기준 저장소: PostgreSQL
- 수집기: source별 API 또는 CLI client
- 선택 projection: vector index, graph database
- 인증정보: `.env`로만 관리하고 Git에서 제외

구체적인 런타임과 버전은 첫 Git 수집기를 구현할 때 고정한다. 아직 실행하지 않은 환경을 완료된 구성처럼 기록하지 않는다.

## 발표 자료 실행 방법

현재 디렉터리에서 다음 명령을 실행한다.

```bash
python3 -m http.server 8000
```

브라우저에서 다음 주소를 연다.

```text
http://localhost:8000/presentation.html
```

방향키, Page Up·Page Down, Space로 이동하고 `F` 키로 전체 화면을 사용할 수 있다.

## 현재 결과

| 항목 | 상태 | 확인 내용 |
| --- | --- | --- |
| 수집 대상과 경계 정의 | 완료 | Slack·Notion·Git/GitHub·AWS의 수집 단위 구분 |
| 저장 계층 설계 | 완료 | 원문·현재·이력·검색·관계 분리 |
| 수집 순서 설계 | 완료 | 계약 → Backfill → Enrichment → Incremental → Reconcile |
| 발표 자료 | 완료 | 질문 중심 17장 HTML |
| Git fixture 수집 | 미구현 | 공개 샘플과 수집기 필요 |
| PostgreSQL 적재 | 미구현 | migration과 멱등성 검증 필요 |
| 증분 수집 | 미구현 | cursor 또는 event 처리 필요 |
| 검색·그래프 평가 | 미구현 | 질의와 정답 기준 필요 |

현재 관찰한 결과는 설계 문서와 발표 자료가 브라우저에서 동작한다는 범위까지다. 실제 데이터를 적재하거나 수집 성능을 측정하지 않았다.

## 구조

```text
01-data-collection-practice/
├── README.md
└── presentation.html
```

수집기를 구현하면 다음 구조를 추가할 예정이다.

```text
01-data-collection-practice/
├── README.md
├── presentation.html
├── .env.example
├── data/
│   └── fixtures/
├── schema/
├── src/
└── tests/
```

## 다음 단계

- [ ] 공개 Git 저장소의 최소 fixture와 예상 질의 작성
- [ ] 원문 payload·ingestion run·commit·file 관계를 저장하는 최소 schema 작성
- [ ] Backfill 수집기와 멱등성 테스트 실행
- [ ] 정규화된 관계에서 실제 diff로 돌아가는 provenance 검증
- [ ] 새 commit을 이용한 증분 수집과 전체 reconciliation 비교
- [ ] Git 실습이 완료되면 Slack·Notion·AWS 중 두 번째 원천 선택

[openviking-note]: ../../notes/01-openviking-context-database.md
