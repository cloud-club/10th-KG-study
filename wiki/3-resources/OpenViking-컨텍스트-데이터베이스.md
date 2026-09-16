---
title: OpenViking — Resource·Memory·Skill과 L0/L1/L2
type: resource
tags: [concept, tooling]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [kungbi]
weeks: [2]
---

> volcengine의 OpenViking은 에이전트의 컨텍스트를 Resource(현재 확인할 자료)·Memory(이전 경험과 판단)·Skill(반복 절차)로 나누고 L0/L1/L2 계층으로 필요한 만큼만 불러오는 Context Database다. kungbi의 발표 요약이며, 핵심 주장은 "과거 결론은 현재 사실이 아니라 **재검증의 출발점**"이라는 것.

## 정의

- 에이전트의 context에는 현재 질문뿐 아니라 최근 대화, 검색한 문서, 도구 실행 결과, 과거 Memory, 작업 Skill이 함께 들어간다. 대화 전체를 계속 넣으면 비용이 커지고, 작은 청크만 저장하면 문장의 배경과 적용 범위를 잃는다. 중요한 건 많이 저장하는 게 아니라 **정보의 역할을 구분하고 필요한 만큼만 불러오는 것**.

| 종류 | 무엇 | 예 |
|---|---|---|
| Resource | 현재 확인할 자료 | 문서, 코드, runbook, 최신 관측값 |
| Memory | 이전 경험과 판단 | 결정, 사건, 가설, 미확정 범위 |
| Skill | 반복 가능한 수행 절차 | 장애 분석, 검증, 리뷰 절차 |

같은 장애 회고라도 원문은 Resource, 거기서 추출한 경험은 Memory, 반복 검증된 조사 순서는 Skill이 된다. URI 네임스페이스는 `viking://resources/`, `memories/`, `skills/`.

| 층 | 역할 |
|---|---|
| L0 Abstract | 관련 범위를 판단하는 짧은 설명 |
| L1 Overview | 핵심 내용과 하위 탐색 경로 |
| L2 Detail | 최종 판단에 쓸 원문과 상세 |

검색 흐름은 질문 → L0에서 범위 → L1에서 후보와 구조 → 필요한 L2 원문. 이 레포의 위키가 `index.md`를 먼저 읽고 페이지로 내려가는 방식과 같은 구조다([[LLM-위키-패턴]]).

## 핵심 주장

- **Retrieval ≠ Validation.** Retrieval은 조사할 후보를 찾는 과정, Validation은 현재 원문과 관측값으로 후보를 검증하는 과정. 벡터 검색과 리랭킹은 질문과 가까운 과거 기록을 찾지만 그 기록이 지금도 사실인지는 판단하지 못한다. 과거 경험을 재사용하되 최신 Resource로 다시 검증해야 확증편향이 준다.
- Memory에는 결론만이 아니라 조사 구조를 남긴다: 무엇을 어떤 데이터로 확인했는가, 당시 가설과 미확정 사항, 조사 순서와 기준, 적용 범위(서비스·기간·환경), 재확인 조건. "Memory는 정답 저장소라기보다 판단 근거와 재검증 경로를 보존하는 장치."
- 공식: 과거에 확인한 사실 + 이전 판단과 미확정 범위 + 재검증 절차 + 현재 원문과 관측값 = 현재 시점의 결론. 과거와 현재가 충돌하면 숨기지 않고 Memory를 갱신한다. 출처·시간·상태·적용 범위를 함께 남긴다.
- **OpenViking ≠ Knowledge Graph.** OpenViking은 자료·기억·절차를 찾고 상세 수준을 고르는 것, [[지식그래프와-온톨로지|Knowledge Graph]]는 엔티티와 관계를 명시하고 관계 경로를 질의하는 것. 가치는 새 검색 알고리즘이 아니라 서로 다른 컨텍스트와 탐색 경로를 하나의 데이터베이스에서 관리하는 데 있다.

## 다른 노트와의 관계

- "검색 결과가 곧 현재의 근거는 아니다"는 kdyann이 정리한 CRAG(검색 결과를 항상 옳다고 가정하지 않음)와 같은 문제의식, 다른 해법이다(모델 내부 평가 vs 저장 계층 설계). sese2204의 "검색 실패 vs 생성 실패" 분해와는 **축이 다르다**(프로세스 단계 vs 실패 원인). 셋을 섞어 쓰면 용어가 꼬인다 → [[RAG-실패-유형]].
- sese2204의 [[RAG-변천사]]가 던진 "검색을 도구로 노출할지 메모리로 자동 주입할지"에서 이 노트는 메모리 쪽 설계안이다.
- 열린 질문 "원본과 추출된 Memory 사이의 provenance를 어디까지 보존할까"는 같은 저자의 [[데이터-수집과-출처-추적]]으로 구체화됐다.

## 멤버들이 확인한 것

- kungbi 본인의 한정: 발표 사례는 Memory 중심으로 쓰며 얻은 문제의식이고, Resource·Skill까지 연결해 운영하는 건 아니며 실제 연결과 검색 평가는 다음 단계다. 성능 수치 없음.

## 열린 질문 (kungbi)

- 오래된 Memory의 만료·갱신 기준, Memory와 최신 Resource 충돌 시 우선순위, 계층형 검색의 효과를 잴 지표([[RAG-평가-지표]]), 반복된 경험을 Skill로 승격할 시점.

## 관련

- [[지식그래프와-온톨로지]] · [[데이터-수집과-출처-추적]] · [[RAG-변천사]] · [[RAG-실패-유형]] · [[LLM-위키-패턴]]

## 출처

- kungbi · OpenViking: 무엇을 기억하고 무엇을 다시 확인할까? — [members/kungbi/notes/01-openviking-context-database.md](../../members/kungbi/notes/01-openviking-context-database.md) (상세는 같은 폴더의 `presentation.html`)
- 외부: https://github.com/volcengine/OpenViking · https://docs.openviking.ai/en/concepts/01-architecture · …/02-context-types · …/03-context-layers · …/07-retrieval
