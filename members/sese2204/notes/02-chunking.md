---
title: 청킹 전략
date: 2026-09-03
tags: [rag, chunking, late-chunking, contextual-retrieval]
status: done
---

# 02. 청킹 전략

> 참고 자료:
> - Jina, Late Chunking 포스트
> - Anthropic, Contextual Retrieval 블로그 포스트
> - arXiv 2504.19754 "Reconstructing Context" — late chunking과 contextual retrieval을 통제 비교한 논문

## 한 줄 요약

재귀적 문자 분할 512 토큰 + 10~20% 오버랩이 기본값이고, 컨텍스트 손실 문제는 분할 단계보다 임베딩 단계(late chunking / contextual retrieval)에서 푸는 쪽이 유리하다.

## 핵심 개념

- 재귀적 문자 분할이 대부분의 경우 최선의 기본값
- 512 토큰 + 10~20% 오버랩이 표준 출발점
- 시맨틱 청킹은 정확도가 오르지만 컴퓨팅·지연 비용이 크다
- late chunking을 적용하면 고정 윈도와 시맨틱 청킹의 성능 차이가 거의 사라진다

## 상세 정리

### 계보

```
고정 크기
  → 재귀적 문자 분할 (recursive)
    → 문서 구조 인식 (마크다운/HTML 헤더)
      → 시맨틱 청킹 (임베딩 유사도로 주제 전환 탐지)
        → 계층적 (parent-child, small-to-big)
          → LLM / proposition 기반
            → late chunking / contextual retrieval
```

### 실무 기준선

- **재귀적 문자 분할이 대부분의 경우 최선의 기본값**
- **512 토큰 + 10~20% 오버랩**이 표준 출발점
  - 128 토큰 → 너무 파편화
  - 1,000+ 토큰 → 임베딩 신호 희석

### 시맨틱 청킹에 대한 유보

정확도는 오르지만 컴퓨팅·지연 비용이 크다.
**late chunking을 적용하면 고정 윈도와 시맨틱 청킹의 성능 차이가 거의 사라진다**는 결과도 있음
→ 문제를 임베딩 단계에서 풀면 분할 단계를 정교하게 할 이유가 줄어든다.

### late chunking vs contextual retrieval

| | late chunking | contextual retrieval |
|---|---|---|
| 방식 | 문서 전체 인코딩 후 분할·풀링 | LLM으로 맥락 요약 생성 후 프리픽스 |
| 비용 | 임베딩 모델만 사용 (저렴) | LLM 호출 추가 (비쌈) |
| 의미 일관성 | 상대적으로 약함 | 더 우수 |
| 트레이드오프 | 효율적이나 관련성·완결성 다소 희생 | 자원 소모 큼 |
| 요구사항 | 롱컨텍스트 임베딩 모델 필요 | 임베딩 모델 무관 |

📄 **arXiv 2504.19754** "Reconstructing Context" — 두 기법을 통제 비교한 논문

## 궁금한 점 / 더 알아볼 것

- [ ] arXiv 2504.19754 — 청킹 전략 통제 비교 논문 읽기
- [ ] Jina Late Chunking / Anthropic Contextual Retrieval 원문 읽기

## 스터디에서 나눌 이야기

- 시맨틱 청킹을 정교하게 하는 대신 late chunking으로 대체할 수 있다면, 분할 단계에 얼마나 투자해야 하는가
