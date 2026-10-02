---
title: BEIR — zero-shot 검색 벤치마크와 그 편향
type: entity
tags: [dataset]
status: draft
created: 2026-10-02
updated: 2026-10-02
members: [do-dop, sese2204, kdyann, Yeongeunn]
weeks: [2, 3]
---

> Thakur et al. (2021)의 zero-shot 텍스트 검색 벤치마크. 9개 태스크 · 18개 데이터셋, 문서 수 3,600~1,500만, 질의 길이 3~192단어, 5개 아키텍처(lexical · sparse · dense · late-interaction · re-ranking)의 10개 방법. 스터디에서 [[하이브리드-검색과-RRF]]의 근거이자 [[RAG-변천사]]의 1기 사건으로 세 멤버가 다른 강도로 인용했고, do-dop이 원문을 직접 읽어 판정을 닫았다.

## 개요

- 검색의 **zero-shot** = "실제로 검색하려는 데이터셋으로 추가 학습을 하지 않은 상태". LLM 프롬프팅의 zero-shot과 결이 다르다 (do-dop).
- 기존 연구의 순환: MS MARCO(53만 건) 학습 → 같은 분포에서 평가 → "Dense > BM25". BEIR는 그 밖으로 나갔다.
- 결론 둘: ① 모든 데이터셋에서 1등인 방식은 없다 ② **in-domain 성능이 generalization을 보장하지 않는다.** 원문: *"BM25 remains a strong baseline for zero-shot text retrieval."* late-interaction·cross-attention re-ranking은 좋지만 비싸고, 가벼운 sparse/dense는 때로 BM25보다 낮았다.
- **벤치마크 자체의 편향**: 정답은 기존 검색기 top-100 풀에서 사람이 판정하므로 그 검색기가 BM25면 BM25가 못 올린 문서는 평가 기회조차 없다. **TREC-COVID에서 빠진 문서를 추가 annotation하자 non-lexical 방법 점수가 눈에 띄게 올랐다.** 스터디 라벨링의 pooling 편향과 같은 구조 → [[RAG-평가-지표]].
- 평가 구조 corpus / queries / qrels가 BEIR 유래. 지표는 nDCG@10 (Yeongeunn 07). MTEB의 검색 카테고리가 BEIR를 포함한다 → [[임베딩-모델-선택]].

## 겪은 문제 · 함정

> ⚠️ Contradiction (판정): sese2204 "도메인 밖에서는 BM25가 여전히 강하다 → 하이브리드의 근거"(단정) vs kdyann "제로샷 성능이 데이터셋과 도메인에 따라 달라질 수 있음"(완화). do-dop의 원문 인용은 완화 쪽이다. 위키는 kdyann·do-dop 표현을 쓴다.

- do-dop의 소규모 재확인: 같은 10문항에서 57청크일 때 정규화 융합이, 69청크일 때 RRF가 이겼다 — "in-domain ≠ generalization을 작은 규모로 재확인". 평가 질문을 한 종류만 만들면 검색기 특징이 안 보인다 → 팩트·원인·엔티티·관계·다중근거 다섯 유형.

## 관련

- [[하이브리드-검색과-RRF]] · [[RAG-변천사]] · [[RAG-평가-지표]] · [[임베딩-모델-선택]] · [[검색의-세-세대]]

## 출처

- do-dop · BEIR 벤치마크 — [members/do-dop/notes/03-beir-benchmark.md](../../members/do-dop/notes/03-beir-benchmark.md); readings 3주차 — [members/do-dop/readings.md](../../members/do-dop/readings.md)
- sese2204 · 고전 RAG 기술 변천사 — [members/sese2204/notes/01-rag-history.md](../../members/sese2204/notes/01-rag-history.md); kdyann · RAG 기술 변천사 — [members/kdyann/notes/01-rag-history.md](../../members/kdyann/notes/01-rag-history.md); Yeongeunn · 임베딩 모델 노트 (§벤치마크) — [members/Yeongeunn/notes/07-embedding-models.md](../../members/Yeongeunn/notes/07-embedding-models.md)
- 외부: Thakur et al., BEIR (NeurIPS 2021 D&B) https://arxiv.org/abs/2104.08663 · 저장소 https://github.com/beir-cellar/beir · Metrics https://github.com/beir-cellar/beir/wiki/Metrics-available
