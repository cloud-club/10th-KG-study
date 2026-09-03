---
title: 리랭커
date: 2026-09-03
tags: [rag, reranker, cross-encoder, colbert, late-interaction]
status: done
---

# 05. 리랭커

> 참고 자료:
> - Khattab & Zaharia, ColBERT (2020)
> - RankGPT, RankZephyr (LLM listwise)
> - jina-reranker-v3, BGE-Reranker-v2-M3, ms-marco-MiniLM

## 한 줄 요약

bi-encoder로 top-50~100을 회수하고 cross-encoder로 재정렬하는 게 표준이며, 도입 여부는 recall@100과 recall@5의 격차로 판단한다.

## 핵심 개념

- Bi-encoder → late interaction → cross-encoder → LLM listwise 순으로 정확도와 비용이 함께 올라간다
- recall@100이 recall@5보다 유의미하게 높을 때만 리랭커가 벌어줄 여지가 있다
- QPS가 올라가면 cross-encoder의 꼬리 지연이 급격히 악화 → QPS 예산 기준으로 아키텍처 선택
- 제로샷 LLM 리랭커는 도메인 밖에서 파인튜닝된 리랭커보다 못한 경우가 많다

## 상세 정리

### 구조 계보

| 방식 | 동작 | 특성 |
|---|---|---|
| Bi-encoder | 쿼리·문서 따로 인코딩, 벡터 유사도 | 사전 계산 가능, 빠름, 세밀한 상호작용 손실 |
| Late interaction (ColBERT) | 따로 인코딩 후 토큰 단위 MaxSim | 중간 지점, 저장 비용 증가 |
| Cross-encoder | 쿼리+문서를 한 번에 인코딩 | 가장 정확, 쌍마다 forward pass |
| LLM listwise (RankGPT, RankZephyr) | 후보 목록을 한 번에 순위화 | 품질 높으나 비용·지연 큼 |

**최신 지점**: jina-reranker-v3의 "last but not late interaction" —
ColBERT처럼 인코딩 후 상호작용하는 대신, 쿼리와 모든 문서를 같은 컨텍스트 윈도 안에서 causal attention으로 처리.

### 실무 판단 기준

**① 표준 패턴**
```
bi-encoder로 top-50~100 회수 → cross-encoder로 재정렬 → top-5~10
```

**② 도입 여부는 감이 아니라 지표로**
- 대표 평가셋에서 `recall@100`이 `recall@5`보다 유의미하게 높으면 → 리랭커가 벌어줄 여지 있음
- 격차가 없으면 → 리랭커가 아니라 **회수 단계**를 고쳐야 함

**③ 지연 감각**
- ms-marco-MiniLM: 쌍당 5ms 미만 (L40S), BEIR 약 60%
- BGE-Reranker-v2-M3: 쌍당 약 35ms, BEIR 약 73%
- QPS가 올라가면 cross-encoder의 꼬리 지연이 급격히 악화
  → 정확도 요구사항만이 아니라 **QPS 예산** 기준으로 아키텍처 선택

**④ "그냥 큰 LLM 쓰면 되지"는 자동 승리가 아님**
- 제로샷 LLM 리랭커는 도메인 밖 데이터에서 파인튜닝된 리랭커보다 못한 경우가 많음

## 궁금한 점 / 더 알아볼 것

- [ ] ColBERT 논문 — late interaction의 저장 비용과 2024년 부활 배경
- [ ] jina-reranker-v3의 "last but not late interaction" 구조

## 스터디에서 나눌 이야기

- 리랭커 없이 회수 단계를 고치는 편이 나은 상황을 어떻게 구분할 것인가

---

*지연 수치와 모델명은 2026년 중반 기준.*
