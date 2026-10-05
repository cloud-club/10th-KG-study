---
title: RAGAS — 지표는 표준, 라이브러리는 정체
type: entity
tags: [tool, pitfall]
status: draft
created: 2026-10-02
updated: 2026-10-02
members: [sese2204, lys0611, Yeongeunn]
weeks: [3]
---

> RAG 평가 라이브러리. 공통 뼈대는 **진술 분해 + NLI 판정**(faithfulness·context recall·factual correctness)이고 answer relevancy만 역질문 + 임베딩 코사인이다. "어떤 정답 데이터를 만들 수 있는지가 어떤 지표를 쓸 수 있는지를 결정한다" — 카탈로그의 절반 이상은 `reference`(정답 문장)나 `reference_context_ids`가 필요하므로 **"정답 레이블 없이"는 논문 원형 3지표에만 해당**한다. sese2204가 2026-09 기준으로 소스·릴리스까지 확인했다: 지표 정의는 업계 표준이지만 **라이브러리 유지보수는 멈춰 있다.** 평가 층위·심판 일반론은 [[챗봇-평가-층위와-심판]], 멤버 실측은 [[RAG-평가-지표]].

## 개요

| 정답 필드 | 비용 | 쓸 수 있는 지표 |
|---|---|---|
| (없음) | 0 | Faithfulness, AnswerRelevancy, ContextUtilization, ResponseGroundedness, AspectCritic |
| `reference_context_ids` | 낮음 (청크에서 질문을 역생성하면 자동) | **IDBasedContextRecall = 우리가 아는 recall@k** |
| `reference_contexts` | 낮음 | NonLLM 계열 |
| `reference` (정답 문장) | 중간 | ContextRecall, NoiseSensitivity, AnswerCorrectness, FactualCorrectness, SemanticSimilarity, BLEU/ROUGE/CHRF |
| `rubrics` | 높음 | InstanceRubrics |
| `reference_tool_calls`, `reference_topics` | — | ToolCallAccuracy, TopicAdherence |

- 논문 3축: Faithfulness = 지지된 진술 / 전체 진술, Answer Relevance = 역생성 질문과 원 질문의 코사인 평균, Context Relevance = 답에 필요한 문장 / 문맥 전체 문장. **같은 이름 다른 정의**: 라이브러리의 NVIDIA `ContextRelevance`(0/1/2 등급 평균)는 논문의 문장 비율과 다르다. 지표명만 옮기면 틀린다.
- 주요 정의: ContextPrecision = Σ(Precision@k·v_k)/관련 청크 수. ContextRecall은 `reference`를 claim으로 쪼개 `retrieved_contexts`에 귀속되는 비율 — **정답 문장을 정답 근거의 프록시로 쓴다.** NoiseSensitivity = 응답 claim 중 틀린 claim 비율(낮을수록 좋음, RAGChecker 유래). AnswerCorrectness = 사실 F1(`TP/(TP+0.5(FP+FN))`) + 의미 유사도, LLM 3회 호출. `FaithfulnesswithHHEM` = Vectara HHEM-2.1-Open(T5 분류기), 로컬·저렴 — lys0611의 "인용 P/R을 NLI로 근사" TODO의 후보.
- **합성 테스트셋은 지식그래프 기반**(0.2부터): 문서 → 청크 노드 → NER·키프레이즈·요약 추출 → 엔티티 Jaccard·임베딩 코사인으로 관계 → Persona × Scenario → QuerySynthesizer. 합성기 3종 SingleHopSpecific / **MultiHopSpecific(엔티티 겹침 엣지 → bridge 질문)** / MultiHopAbstract(의미 유사 엣지). 출력에 정답 근거와 정답 문장이 동시에 생긴다. 기본 분포는 **균등 1/3**(문서 예시 0.5/0.25/0.25는 낡음 — 소스 확인). 답 가능 여부(unanswerable)는 **못 만든다.**
- WikiEval 검증(논문 보고): 위키피디아 50페이지, 어노테이터 2명 일치율 약 95%/90%. 사람 판단 쌍대 일치도 RAGAS 0.95 / 0.78 / 0.70 vs GPT Score 0.72 / 0.52 / 0.63 — context relevance가 "가장 어렵다"고 논문 스스로 인정 → 검색 층은 골든셋 IR 지표로 따로.
- 심판 정렬(문서 보고): 160개 사람 라벨에 기본 프롬프트 일치율 75.6%(오정렬 39건 전부 false positive — 심판이 관대) → v2 86.9%. 필요 라벨 100~200개. 이 숫자는 골든셋 크기(sese2204 "200개면 충분")와 **다른 용도**(캘리브레이션 라벨)다.

## 타임라인

| 날짜 | 구분 | 이벤트 | 상태 |
|---|---|---|---|
| 2023-09 | 이벤트 | 논문 (arXiv 2309.15217), 3지표 | — |
| 0.2 | 이벤트 | 지식그래프 기반 합성 테스트셋 | — |
| 0.4 | 이벤트 | API 세대 교체 (v0.3→v0.4 마이그레이션 문서) | — |
| 2026-01-13 | 이벤트 | `ragas 0.4.3` PyPI (sese2204 직접 확인) | — |
| 2026-02-24 | 이벤트 | main 마지막 커밋. 저장소 `vibrantlabsai/ragas`로 이전, 15.7k★ | — |
| 2026-03~ | 관측 | **머지 PR 0건**, 열린 PR 221·이슈 372 (2026-09 sese2204 확인) | 정체 |

## 겪은 문제 · 함정

- **정직한 거절이 감점된다.** AnswerRelevancy는 noncommittal 답("I don't know")이면 점수를 0으로 만든다(`score = cosine_sim.mean() * int(not all_noncommittal)`, sese2204 소스 확인). 근거가 없어 정직하게 회피한 답과 과잉 거절이 같은 0점이다 — lys0611의 거절 성공률 0.500·과잉 거절 3건을 RAGAS로 재면 구분이 사라진다 → [[RAG-루프와-근거-인용]]. 대응: `reference`를 "해당 정보 없음"으로 두고 FactualCorrectness / AspectCritic·RubricsScore로 직접 정의 / 그 항목에서 AnswerRelevancy를 집계에서 뺀다. RGB의 negative rejection 능력은 RAGAS에 없다.
- **한국어 함정 4** (sese2204): ① `adapt_instruction=False` 기본이면 few-shot만 번역되고 지시문은 영어로 남는다 ② `adapt()`는 LLM 호출이고 0.4.x에서 save/load 미구현 → 캐싱 필수 ③ BLEU 대신 CHRF ④ 한국어 성능 수치가 공식 문서에 없다. 지표마다 프롬프트 1~2개를 각각 adapt(Faithfulness는 `statement_generator_prompt` + `nli_statement_prompt`).
- 비결정성을 문서가 명시한다 → 온도 고정·캐시·**동일 골든셋의 상대 변화**로 읽는다. claim 하나뿐인 짧은 답은 faithfulness가 0 또는 1로 양자화된다. 토큰은 기본으로 안 센다. 호출 수 AnswerCorrectness 3 > AnswerAccuracy 2 > RubricsScore 1.
- Yeongeunn 08의 요약: "고정 골드셋이 아니며 평가 모델의 오류·편향이 존재한다."

## 의사결정 · 남은 일

- 스터디에서 RAGAS를 실제로 돌린 멤버는 없다(2026-10-02). sese2204의 골든셋 200개 배분안(single-hop specific 40% / multi-hop specific 20% / multi-hop abstract 10% / **unanswerable 15%, AnswerRelevancy 집계 제외** / multi-turn non-standalone 15%)은 제안 단계 → [[RAG-평가-지표]] 열린 질문.
- 대안 도구 (sese2204 정리): DeepEval(G-Eval, pytest) / TruLens(RAG Triad) / ARES(합성 데이터로 경량 심판 파인튜닝) / Phoenix(OTel, RAGAS 공식 트레이싱 파트너) / LangSmith / promptfoo(YAML assertion, CI). "지표 정의는 RAGAS가 표준, 도구는 관측 플랫폼·CI 러너로 이동 중."

## 관련

- [[RAG-평가-지표]] · [[챗봇-평가-층위와-심판]] · [[RAG-루프와-근거-인용]] · [[멀티홉-질문과-Bridge-Entity]] · [[지식그래프와-온톨로지]] (합성기의 그래프)

## 출처

- sese2204 · RAGAS — [members/sese2204/notes/10-ragas.md](../../members/sese2204/notes/10-ragas.md); RAG 평가와 실습 로드맵 (2026-09-16 보정) — [07-rag-evaluation.md](../../members/sese2204/notes/07-rag-evaluation.md); readings 3주차 — [members/sese2204/readings.md](../../members/sese2204/readings.md)
- Yeongeunn · 생성 모델 노트 (§벤치마크 Ragas) — [members/Yeongeunn/notes/08-generative-models.md](../../members/Yeongeunn/notes/08-generative-models.md)
- 외부: Es et al., RAGAS https://arxiv.org/abs/2309.15217 · Metrics overview https://docs.ragas.io/en/stable/concepts/metrics/overview/ · Available metrics https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/ · Testset generation https://docs.ragas.io/en/stable/concepts/test_data_generation/rag/ · Align LLM-as-judge https://docs.ragas.io/en/stable/howtos/applications/align-llm-as-judge/ · Language adaptation https://docs.ragas.io/en/stable/howtos/customizations/metrics/metrics_language_adaptation/ · v0.3→v0.4 migration https://docs.ragas.io/en/stable/howtos/migrations/migrate_from_v03_to_v04/ · 저장소 https://github.com/vibrantlabsai/ragas · WikiEval https://huggingface.co/datasets/explodinggradients/WikiEval
