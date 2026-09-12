---
title: "OpenViking: 무엇을 기억하고 무엇을 다시 확인할까?"
date: 2026-09-12
tags: [openviking, rag, retrieval, agentic-rag]
status: done
---

# 01. OpenViking: 무엇을 기억하고 무엇을 다시 확인할까?

> 질문: 에이전트가 과거 경험을 재사용하면서도 현재 상황을 다시 검증하게 하려면
> 컨텍스트를 어떻게 구성해야 할까?
>
> 이 노트는 발표 내용의 요약이다. 구조도와 운영 사례, 상세한 검색 흐름은
> [OpenViking HTML 발표 자료](./01-openviking-context-database/presentation.html)를
> 참고한다.

## 한 줄 요약

OpenViking은 Resource·Memory·Skill을 계층적으로 관리하고 필요한 내용만 불러와,
과거 결론을 현재 사실이 아닌 **재검증의 출발점**으로 활용하게 하는 Context
Database다.

## 핵심 정리

### Context는 모델이 지금 참고하는 입력이다

에이전트의 context에는 현재 질문뿐 아니라 최근 대화, 검색한 문서, 도구 실행
결과, 과거 Memory, 작업 Skill이 함께 들어간다.

대화 전체를 계속 넣으면 불필요한 정보와 비용이 커지고, 작은 chunk만 저장하면
문장이 나온 배경과 적용 범위를 잃기 쉽다. 따라서 중요한 것은 많이 저장하는 것이
아니라 **정보의 역할을 구분하고 필요한 만큼만 불러오는 것**이다.

### 답보다 조사 구조를 기억해야 한다

과거의 결론은 특정 시점과 조건에서만 맞았을 수 있다. Memory에는 결론만 남기기보다
다음 내용을 함께 보존해야 한다.

- 무엇을 어떤 데이터로 확인했는가
- 당시의 가설과 미확정 사항은 무엇이었는가
- 어떤 순서와 기준으로 조사했는가
- 어느 서비스·기간·환경에 적용되는가
- 어떤 조건에서 다시 확인해야 하는가

즉, Memory는 정답 저장소라기보다 **판단 근거와 재검증 경로를 보존하는 장치**에
가깝다.

### 검색 결과가 곧 현재의 근거는 아니다

벡터 검색과 reranking은 질문과 가까운 과거 기록을 찾을 수 있지만, 그 기록이
현재도 사실인지는 판단하지 못한다.

```text
Retrieval = 조사할 후보를 찾는 과정
Validation = 현재 원문과 관측값으로 후보를 검증하는 과정
```

과거 경험을 재사용하되 최신 Resource로 다시 검증해야 확증편향을 줄일 수 있다.

## Resource · Memory · Skill

| 유형 | 역할 | 예시 |
| --- | --- | --- |
| Resource | 현재 확인할 자료 | 문서, 코드, runbook, 최신 관측값 |
| Memory | 이전 경험과 판단 | 결정, 사건, 가설, 미확정 범위 |
| Skill | 반복 가능한 수행 절차 | 장애 분석, 검증, 리뷰 절차 |

같은 장애 회고라도 원문은 Resource, 작업에서 추출한 경험은 Memory, 반복해서
검증된 조사 순서는 Skill이 될 수 있다.

```text
viking://
├─ resources/    문서·코드·외부 자료
├─ memories/     과거 결정·경험·사용자 맥락
└─ skills/       반복 가능한 작업 절차
```

## L0 · L1 · L2

OpenViking은 모든 원문을 한 번에 불러오는 대신 요약에서 상세 내용으로 단계적으로
내려간다.

| 계층 | 역할 |
| --- | --- |
| L0 Abstract | 관련 범위를 판단하는 짧은 설명 |
| L1 Overview | 핵심 내용과 하위 탐색 경로 |
| L2 Detail | 최종 판단에 사용할 원문과 상세 내용 |

```text
질문
  → L0에서 관련 범위 탐색
  → L1에서 후보와 구조 파악
  → 필요한 L2 원문 확인
```

복합 질문에서는 의도를 분석한 뒤 Resource·Memory·Skill별로 검색하고, 계층 탐색과
reranking을 통해 필요한 상세 내용만 선택한다.

## 기억을 사용하는 원칙

```text
과거에 확인한 사실
+ 이전 판단과 미확정 범위
+ 재검증 절차
+ 현재 원문과 관측값
= 현재 시점의 결론
```

- Memory는 이전 결론과 조사 경로를 제공한다.
- Resource는 현재 상태를 다시 확인하게 한다.
- Skill은 두 정보를 어떤 기준으로 비교할지 제공한다.
- 과거와 현재가 충돌하면 충돌을 숨기지 않고 Memory를 갱신해야 한다.
- 출처·시간·상태·적용 범위를 함께 남겨야 한다.

## 현재 이해한 적용 범위

OpenViking의 가치는 새로운 검색 알고리즘 하나보다, 서로 다른 컨텍스트와 탐색
경로를 하나의 Context Database에서 관리하는 데 있다.

현재 발표의 사례는 Memory 중심으로 사용하며 얻은 문제의식을 정리한 것이다.
Resource와 Skill까지 완전히 연결해 운영하고 있다는 뜻은 아니며, 실제 연결과 검색
평가는 다음 단계다.

또한 OpenViking은 Knowledge Graph와 같은 기술이 아니다.

- OpenViking: 필요한 자료·기억·절차를 찾고 상세 수준을 선택한다.
- Knowledge Graph: 엔티티와 관계를 명시하고 관계 경로를 질의한다.

## 궁금한 점 / 더 알아볼 것

- [ ] 오래된 Memory의 만료와 갱신 기준은 어떻게 관리해야 할까?
- [ ] Memory와 최신 Resource가 충돌하면 어떤 우선순위로 처리해야 할까?
- [ ] 계층형 검색의 효과를 어떤 지표로 평가할 수 있을까?
- [ ] 반복된 경험을 언제 Skill로 승격해야 할까?
- [ ] 원본과 추출된 Memory 사이의 provenance를 어디까지 보존해야 할까?

## 참고 자료

- OpenViking, [GitHub](https://github.com/volcengine/OpenViking)
- OpenViking, [Introduction](https://docs.openviking.ai/en/getting-started/01-introduction)
- OpenViking, [Architecture Overview](https://docs.openviking.ai/en/concepts/01-architecture)
- OpenViking, [Context Types](https://docs.openviking.ai/en/concepts/02-context-types)
- OpenViking, [Context Layers](https://docs.openviking.ai/en/concepts/03-context-layers)
- OpenViking, [Retrieval Mechanism](https://docs.openviking.ai/en/concepts/07-retrieval)
- OpenViking, [공식 로고 자산](https://github.com/volcengine/OpenViking/blob/main/docs/images/ov-logo.png)
- Grafana Labs, [Ride share tutorial with Pyroscope](https://grafana.com/docs/pyroscope/latest/get-started/ride-share-tutorial)
