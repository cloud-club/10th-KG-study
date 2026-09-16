---
title: RAGAS — 방법론, 평가 지표, 정답셋 유형
date: 2026-09-16
tags: [ragas, evaluation, llm-as-judge, faithfulness, golden-set, testset-generation, knowledge-graph]
status: done
---

# 10. RAGAS — 방법론, 평가 지표, 정답셋 유형

> 참고 자료:
> - [Es et al., RAGAS: Automated Evaluation of Retrieval Augmented Generation (arXiv 2309.15217, EACL 2024 Demo)](https://arxiv.org/abs/2309.15217) — 원 논문
> - [docs.ragas.io — Metrics overview](https://docs.ragas.io/en/stable/concepts/metrics/overview/), [Available metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)
> - [docs.ragas.io — RAG testset generation](https://docs.ragas.io/en/stable/concepts/test_data_generation/rag/)
> - [docs.ragas.io — Align LLM-as-judge](https://docs.ragas.io/en/stable/howtos/applications/align-llm-as-judge/), [Language adaptation](https://docs.ragas.io/en/stable/howtos/customizations/metrics/metrics_language_adaptation/)
> - [docs.ragas.io — v0.3 → v0.4 migration](https://docs.ragas.io/en/stable/howtos/migrations/migrate_from_v03_to_v04/)
> - [GitHub vibrantlabsai/ragas](https://github.com/vibrantlabsai/ragas) (구 explodinggradients/ragas)
> - [WikiEval 데이터셋](https://huggingface.co/datasets/explodinggradients/WikiEval)
> - 앞선 노트: [07. RAG 평가와 실습 로드맵](07-rag-evaluation.md), [09. 챗봇 평가 기준](09-chatbot-evaluation.md)

## 한 줄 요약

RAGAS는 **응답을 원자적 진술(claim)로 쪼개 LLM이 근거·정답과 하나씩 대조**하는 방식으로 RAG를 채점하는 프레임워크다. 논문은 정답 없이(reference-free) 세 축을 재는 것으로 출발했지만, 현재 라이브러리의 지표 절반 이상은 정답(reference)이 필요하므로 **어떤 정답 데이터를 만들 수 있는지가 곧 어떤 지표를 쓸 수 있는지를 결정**한다.

## 핵심 개념

- **진술 분해 + NLI 판정**: faithfulness, context recall, factual correctness 모두 "문장을 claim으로 쪼개고 → 각 claim이 근거에 지지되는지 Yes/No → 비율"이라는 같은 뼈대.
- **역질문 + 임베딩**: answer relevancy는 답에서 질문을 거꾸로 생성해 원 질문과 코사인 유사도를 잰다.
- **3축 원형**: 논문의 Faithfulness / Answer Relevance / Context Relevance. 사람과의 일치도 0.95 / 0.78 / 0.70.
- **정답 필드 6종**: `reference`(정답 문장), `reference_contexts`(정답 근거), `reference_context_ids`, `reference_tool_calls`, `reference_topics`, `rubrics`. 지표마다 요구하는 필드가 다르다.
- **합성 테스트셋**: 문서 → 지식그래프(노드·엔티티·관계) → 페르소나 × 시나리오 → single-hop / multi-hop 질문 생성. **우리 스터디 주제(KG)와 직결.**
- **심판 정렬이 먼저**: 사람 라벨 100~200개로 LLM 심판과의 일치율을 확인한 뒤 써야 한다. 문서 자체 실험에서 기본 프롬프트의 일치율은 75.6%, 오답은 전부 "심판이 관대한" 방향.

## 상세 정리

### 0. 2026-09 현재 상태 (먼저 알아둘 것)

| 항목 | 값 |
|---|---|
| 최신 릴리스 | `ragas 0.4.3` (2026-01-13, PyPI에서 직접 확인) |
| 저장소 | `vibrantlabsai/ragas` (explodinggradients에서 이전), 15.7k★ |
| 업스트림 활동 | main 마지막 커밋 2026-02-24, 2026-03 이후 머지된 PR 0건, 열린 PR 221 / 이슈 372 |
| API 세대 | 0.1 (`evaluate(Dataset, metrics=[faithfulness])`) → 0.2 (`SingleTurnSample`, `Faithfulness(llm=…)`) → **0.4 (`ragas.metrics.collections`, `llm_factory`, `ascore(**kwargs)` → `MetricResult`)** |

시사점: **개념과 지표 정의는 사실상 업계 표준**이지만, 라이브러리는 유지보수가 멈춘 상태다. 배우는 건 0.4 API로, 블로그에 흔한 0.1 코드는 구버전으로 분류. 프로덕션 의존성으로 쓰려면 포크 유지 리스크를 고려. 지표 정의 자체는 promptfoo·DeepEval 등이 재구현하고 있어 도구를 바꿔도 개념은 이식된다.

### 1. 논문의 방법론 (2023)

**문제 설정** — RAG 파이프라인을 사람 라벨 없이 자동 평가. 초록: "a framework for reference-free evaluation of RAG pipelines … without having to rely on ground truth human annotations."

**세 축과 계산법**

| 축 | 질문 | 계산 |
|---|---|---|
| **Faithfulness** | 답이 검색된 문맥에 근거하는가 | ① LLM이 답을 진술 집합 S로 분해 ② 각 진술을 문맥과 대조해 Yes/No ③ F = \|지지된 진술\| / \|S\| |
| **Answer Relevance** | 답이 질문에 실제로 답하는가 | ① 답에서 LLM이 질문 n개를 역생성 ② 원 질문과 임베딩 코사인 ③ 평균 |
| **Context Relevance** | 검색 문맥이 군더더기 없이 필요한 것만 담았나 | LLM이 답에 꼭 필요한 문장만 추출 → 추출 문장 수 / 문맥 전체 문장 수 |

논문에 쓰인 프롬프트 원문(faithfulness 2단계): "Consider the given context and following statements, then determine whether they are supported by the information present in the context. Provide a brief explanation for each statement before arriving at the verdict (Yes/No)." — **근거를 먼저 쓰고 판정**하게 한 것이 9번 노트의 심판 규칙 5와 같은 이유.

**검증 (WikiEval)** — 2022년 이후 사건을 다루는 위키피디아 50페이지로 질문·답 생성, 어노테이터 2명이 세 축을 라벨링(일치율 faithfulness·context relevance 약 95%, answer relevance 약 90%). 사람 판단과의 쌍대 비교 일치도:

| 방법 | Faithfulness | Answer Rel. | Context Rel. |
|---|---|---|---|
| **RAGAS** | **0.95** | **0.78** | **0.70** |
| GPT Score (직접 점수) | 0.72 | 0.52 | 0.63 |
| GPT Ranking | 0.54 | 0.40 | 0.52 |

읽는 법: 진술 분해가 "LLM에게 그냥 점수 매기라"보다 훨씬 낫다. 그러나 context relevance는 논문 스스로 "가장 어렵다, 긴 문맥에서 핵심 문장 고르기를 ChatGPT가 자주 실패한다"고 인정. → 검색 층은 골든셋 IR 지표로 따로 재라는 07번 노트의 결론과 일치.

### 2. 데이터 스키마: 무엇이 "정답"인가

`SingleTurnSample` 필드(전부 선택):

```
user_input            질문
retrieved_contexts    파이프라인이 실제로 가져온 청크
response              파이프라인의 답
reference             정답 문장 (0.3까지 ground_truths: list[str])
reference_contexts    정답 근거 청크
retrieved_context_ids / reference_context_ids   청크 ID 버전
rubrics               이 샘플만의 채점 기준
multi_responses, persona_name, query_style, query_length   (합성 테스트셋 메타)
```

`MultiTurnSample`: `user_input`은 `HumanMessage | AIMessage | ToolMessage` 리스트(필수), 그 외 `reference`, `reference_tool_calls`, `rubrics`, `reference_topics`.

**정답셋 유형 6가지와 각각이 여는 지표**

| 정답 필드 | 뜻 | 만드는 비용 | 여는 지표 |
|---|---|---|---|
| (없음) | 로그만 | 0 | Faithfulness, AnswerRelevancy, ContextUtilization, ResponseGroundedness, ContextRelevance(NVIDIA), AspectCritic, RubricsScoreWithoutReference |
| `reference_context_ids` | 질문별 정답 청크 ID | 낮음 (청크에서 질문 역생성하면 자동) | IDBasedContextPrecision / Recall — **07번 노트의 골든셋 IR 지표가 이것** |
| `reference_contexts` | 정답 청크 본문 | 낮음 | NonLLMContextPrecision / Recall (문자열 유사도), SummaryScore |
| `reference` | 모범 답안 | 중간 (LLM 초안 + 사람 검수) | ContextRecall, ContextPrecision, ContextEntityRecall, NoiseSensitivity, AnswerCorrectness, FactualCorrectness, SemanticSimilarity, AnswerAccuracy, BLEU/ROUGE/CHRF/ExactMatch |
| `rubrics` | 샘플별 점수 기준 서술 | 높음 (도메인 전문가) | InstanceRubrics |
| `reference_tool_calls` / `reference_topics` | 기대 툴 호출 시퀀스 / 허용 주제 | 중간 | ToolCallAccuracy, ToolCallF1, TopicAdherence |

**핵심 구분**: 논문의 "reference-free"는 원래 3개 지표에 대한 말이고, 현재 카탈로그는 절반 이상이 `reference`를 요구한다. 그리고 reference-free 지표는 "**근거와 모순 없나**"를 잴 뿐 "**정답이 맞나**"를 재지 않는다. 검색이 엉뚱한 문서를 가져와도 그 문서에 충실하면 faithfulness는 만점이다.

### 3. 지표 카탈로그 (0.4.3 기준)

표기: 입력 `ui`=user_input, `rc`=retrieved_contexts, `resp`=response, `ref`=reference, `refc`=reference_contexts. 엔진 LLM / EMB(임베딩) / — (둘 다 불필요).

#### 3-1. 검색 (Retrieval)

| 지표 | 정의 | 입력 | 엔진 |
|---|---|---|---|
| **ContextPrecision** | 관련 청크가 **위쪽에** 왔나. Σ_k(Precision@k · v_k) / 관련 청크 수. 각 청크의 관련 여부(v_k)는 LLM이 `ref`와 대조 | ui, ref, rc | LLM |
| ContextUtilization (= ContextPrecisionWithoutReference) | 위와 같되 `resp`와 대조 | ui, resp, rc | LLM |
| NonLLMContextPrecisionWithReference | 청크 ↔ `refc` 문자열 유사도(Levenshtein) | rc, refc | — |
| IDBasedContextPrecision | 가져온 ID 중 정답 ID 비율 | id 2종 | — |
| **ContextRecall** | `ref`를 claim으로 분해 → 각 claim이 `rc`에 귀속되는 비율. **정답 문장을 정답 근거의 프록시로 쓴다** | ui, rc, ref | LLM |
| NonLLMContextRecall | 정답 근거 중 검색된 비율 (문자열) | rc, refc | — |
| IDBasedContextRecall | 정답 ID 중 검색된 비율 = 우리가 아는 recall@k | id 2종 | — |
| ContextEntityRecall | `ref`의 엔티티 중 `rc`에 등장한 비율 | ref, rc | LLM |
| **NoiseSensitivity** | 응답의 claim 중 **틀린** claim 비율. `mode=relevant`(관련 문서에 휘둘림) / `irrelevant`. **낮을수록 좋음.** RAGChecker에서 유래 | ui, rc, resp, ref | LLM |

#### 3-2. 생성 (Response)

| 지표 | 정의 | 입력 | 엔진 |
|---|---|---|---|
| **Faithfulness** | 응답 claim 중 `rc`가 지지하는 비율 | ui, resp, rc | LLM |
| FaithfulnesswithHHEM | 2단계 판정을 Vectara HHEM-2.1-Open(T5 분류기)로 대체. 로컬 실행, 저렴 | 동일 | LLM + 로컬 모델 |
| **AnswerRelevancy** (= ResponseRelevancy) | 응답에서 질문 N개(기본 3, `strictness`) 역생성 → 원 질문과 코사인 평균. 코사인이라 이론상 0~1 밖 가능 | ui, resp | LLM + EMB |
| **AnswerCorrectness** | 사실 F1 + 의미 유사도 가중 평균(`weights`). F1 = TP / (TP + 0.5(FP+FN)). LLM 3회 호출로 비쌈 | ui, resp, ref | LLM + EMB |
| SemanticSimilarity | `ref` ↔ `resp` 임베딩 코사인 | ref, resp | EMB |
| **FactualCorrectness** | claim 분해 + NLI로 TP/FP/FN. `mode ∈ {f1, precision, recall}`, `atomicity`·`coverage`로 분해 입도 조절 | resp, ref | LLM |
| AnswerAccuracy (NVIDIA) | 응답/정답 역할을 바꾼 프롬프트 2개가 각각 0/2/4 등급 → 정규화 평균. LLM 2회, 작은 모델에서도 잘 됨 | ui, resp, ref | LLM |
| ContextRelevance (NVIDIA) | 프롬프트 2개가 0/1/2 등급 → 평균. **논문의 Context Relevance(문장 비율)와 정의가 다름** | ui, rc | LLM |
| ResponseGroundedness (NVIDIA) | 응답이 `rc`에 근거하는 정도 0/1/2 → 평균 | resp, rc | LLM |
| QuotedSpansAlignment | 응답의 따옴표 인용 구간이 `rc`에 축자 등장하는 비율 | resp, rc | — |

#### 3-3. 범용 (General purpose)

| 지표 | 정의 | 비고 |
|---|---|---|
| AspectCritic | 자연어로 정의한 기준("유해한가", "간결한가")에 이진 판정. 3회 호출 다수결 | 0.4 collections에서 제거, legacy 경로만 |
| RubricsScore (with/without reference) | `score1_description`~`score5_description` 딕셔너리, 데이터셋 전체 동일 루브릭 | LLM 1회, 가장 저렴한 LLM 지표 |
| InstanceRubrics | 샘플의 `rubrics` 필드로 **샘플마다 다른 루브릭** | |
| BleuScore / RougeScore / CHRFScore / NonLLMStringSimilarity / ExactMatch / StringPresence | 전통 문자열 지표. `ref` 필수 | **한국어는 BLEU보다 CHRF**(문자 n-gram, 형태론 풍부한 언어용) |
| SummaryScore | 문맥에서 키프레이즈 → 질문 생성 → 요약에 질의. QA 점수 × (1−coeff) + 간결성 × coeff | |

#### 3-4. 에이전트·툴 (MultiTurnSample)

| 지표 | 정의 |
|---|---|
| ToolCallAccuracy | 툴 호출 시퀀스 일치(0/1) × 인자 정확도. `strict_order=False`면 순서 무시 |
| ToolCallF1 | 순서 무시, 불필요 호출은 FP·누락은 FN |
| AgentGoalAccuracy (with/without reference) | 대화 종료 상태가 목표를 달성했나 (0/1). without은 목표까지 대화에서 추론 |
| TopicAdherence | `reference_topics` 대비 precision/recall/F1 |

이 밖에 SQL(실행 기반 DataCompyScore, 비실행 SQLSemanticEquivalence), 멀티모달(MultiModalFaithfulness / Relevance)이 있다.

#### 3-5. 층위별로 고르기 (07·09번 노트와 연결)

| 층 | 우리가 쓸 지표 | 정답 필드 |
|---|---|---|
| 검색 | IDBasedContextRecall(=recall@k), IDBasedContextPrecision, + 직접 계산한 NDCG | `reference_context_ids` |
| 생성-근거 | Faithfulness, NoiseSensitivity | (없음) / `reference` |
| 생성-정답 | FactualCorrectness(f1), AnswerAccuracy | `reference` |
| 대화 | TopicAdherence, 턴별 Faithfulness | `reference_topics` |
| 스타일·안전 | RubricsScore, AspectCritic | 루브릭 |

#### 3-6. RAGAS에 없는 것: 거부(negative rejection)와 부재 근거 인지

"근거가 없으면 모른다고 답하는가"는 RAGAS 지표가 아니라 RGB 벤치마크의 negative rejection 축이다([09번 노트](09-chatbot-evaluation.md) 3절). RAGAS는 오히려 **반대로 동작**한다. AnswerRelevancy는 역질문을 만들 때 답이 noncommittal인지("I don't know", "I'm not sure", "It depends")를 같이 판정하고, 전부 noncommittal이면 점수를 0으로 만든다(소스 `_answer_relevance.py`: `score = cosine_sim.mean() * int(not all_noncommittal)`). 즉 근거가 없어 정직하게 회피한 답이 감점된다.

그래서 코퍼스에 답이 없는 질문(unanswerable)을 골든셋에 넣을 때는:
- `reference`를 "해당 정보 없음"으로 두고 FactualCorrectness를 쓰거나,
- AspectCritic / RubricsScore로 "근거가 없으면 모른다고 답했는가"를 직접 정의하고,
- 그 항목에서는 AnswerRelevancy를 집계에서 빼야 한다.

문서의 조언: "약한 신호를 주는 지표를 늘리지 말고, 강하고 신뢰할 수 있는 신호를 주는 지표 몇 개를 골라라." 객관성 기준은 **평가자 간 일치율 80% 이상**.

### 4. 합성 테스트셋 생성 — 지식그래프 기반

0.2부터 테스트셋 생성은 **지식그래프**를 먼저 만든다. KG 스터디 입장에서 가장 흥미로운 부분.

```
문서 ──▶ Node(DOCUMENT) ──▶ Splitter ──▶ Node(CHUNK)
                                  │
                       Extractors (NERExtractor, KeyphraseExtractor, 요약·제목…)
                                  │ 노드 속성: entities, keyphrases, summary, embedding
                       RelationshipBuilder (JaccardSimilarityBuilder on entities,
                                            CosineSimilarityBuilder on embedding …)
                                  │ 엣지: 엔티티 겹침, 의미 유사
                              KnowledgeGraph  ──save/load──▶ knowledge_graph.json
                                  │
        Persona 목록 × Scenario(노드들, 질문 길이, 질문 스타일, 페르소나)
                                  │
                        QuerySynthesizer ──▶ (user_input, reference_contexts, reference)
```

**쿼리 합성기 3종**

| 합성기 | 만드는 질문 | 필요한 그래프 구조 |
|---|---|---|
| `SingleHopSpecificQuerySynthesizer` | 청크 하나의 구체적 사실을 묻는 질문 | 노드 1개 |
| `MultiHopSpecificQuerySynthesizer` | 엔티티로 이어진 청크 2개 이상을 합쳐야 답하는 구체 질문 | 엔티티 겹침 엣지 |
| `MultiHopAbstractQuerySynthesizer` | 여러 청크의 주제를 아우르는 추상적 질문 | 의미 유사 엣지 |

기본 분포는 소스 코드상 균등 1/3씩(문서 예시의 0.5/0.25/0.25는 낡은 값). `query_distribution=[(synth, weight), …]`로 조정.

**페르소나** — `Persona(name, role_description)`을 직접 정의하거나 `generate_personas_from_kg(kg, llm, num_personas=5)`로 그래프에서 자동 생성. 같은 청크라도 "신입 개발자"와 "감사 담당자"가 다른 질문을 하게 만든다.

**출력**: DataFrame 컬럼 `user_input, reference_contexts, reference, synthesizer_name`. 즉 **정답 근거와 정답 문장이 동시에 생긴다** — 검색 지표와 생성 지표를 한 세트로 잴 수 있다.

**우리 실습과의 연결**: 카톡·노션 코퍼스로 KG를 만들면 그 자체가 골든셋 생성기가 된다. 특히 multi-hop 질문은 3주차 멀티홉 RAG 실습(bridge entity)의 정답셋을 자동으로 준다. 0.1 시절의 evolution 타입(simple / reasoning / multi_context / conditional)은 0.2에서 제거됐으니 구버전 자료에서만 볼 것.

#### 4-1. 질문셋 유형 설계표

RAGAS의 시나리오는 (노드, 질문 길이, 질문 스타일, 페르소나)의 조합이다. 여기에 RAGAS 밖의 축(답 가능 여부, 턴 구조)을 합치면 골든셋을 설계할 때 쓸 축이 여섯 개 나온다.

| 축 | 값 | 어디서 온 개념 | 무엇을 재나 |
|---|---|---|---|
| **hop 수** | single-hop / multi-hop | RAGAS 합성기 | 청크 하나로 답하나, 엔티티로 이어진 여러 청크를 합쳐야 하나(정보 통합) |
| **추상도** | specific / abstract | RAGAS 합성기 (`MultiHopAbstract`) | 특정 사실 질문 vs 여러 청크의 주제를 아우르는 질문 |
| **길이** | short / medium / long | RAGAS `QueryLength` | 짧은 키워드형부터 상황 설명이 긴 질문까지 |
| **스타일** | perfect grammar / poor grammar / misspelled / web-search-like | RAGAS `QueryStyle` | 오타·비문·검색어투에 검색기가 얼마나 강건한가 |
| **페르소나** | 자유 정의 (예: 신입, 운영자, 감사) | RAGAS `Persona` | 같은 청크라도 역할에 따라 다른 관점의 질문 |
| **답 가능 여부** | answerable / unanswerable | RGB negative rejection, MTRAG | 코퍼스에 답이 없을 때 거부하는가. **RAGAS 합성기는 못 만든다** — 직접 넣어야 함 |
| **턴 구조** | single-turn / multi-turn(standalone) / multi-turn(non-standalone) | MTRAG | "그럼 그건 언제야?" 같은 지시대명사 해소, 후반 턴 열화 |

구버전 RAGAS(0.1)의 evolution 타입도 이 축으로 옮겨진다: `simple`=single-hop specific, `reasoning`=single-hop이되 추론 요구, `multi_context`=multi-hop specific, `conditional`=조건절이 붙은 질문(현재는 스타일·길이 축으로 흡수).

**골든셋 200개 배분 예시(제안)**

| 유형 | 비율 | 개수 | 비고 |
|---|---|---|---|
| single-hop specific | 40% | 80 | 검색·생성 기본선 |
| multi-hop specific | 20% | 40 | 3주차 멀티홉 실습과 공유 |
| multi-hop abstract | 10% | 20 | 요약형 답변 |
| unanswerable | 15% | 30 | 거부율 측정. AnswerRelevancy 집계에서 제외 |
| multi-turn non-standalone (3~5턴) | 15% | 30 | 쿼리 재작성 효과 측정 |

스타일·길이·페르소나는 위 유형 안에서 섞는다(예: 각 유형의 20%는 오타·검색어투). 비율은 제품의 실제 질문 로그 분포에 맞추는 게 원칙이고, 로그가 없으면 위 표로 시작해 프로덕션 실패 사례를 채워 넣는다([09번 노트](09-chatbot-evaluation.md) 9절).

### 5. 심판 정렬(judge alignment)

문서가 실증한 흐름:

1. 샘플 160개에 사람 라벨.
2. 기본 프롬프트 심판과의 일치율 **75.6%** (121/160). 오정렬 39건이 **전부 false positive**, 즉 심판이 관대한 방향.
3. 프롬프트에 실패 사례를 반영해 v2 → **86.9%** (139/160).

"A misaligned judge is like a compass pointing the wrong way." 필요한 라벨 수는 대표 샘플 **100~200개**. 07번 노트의 "골든셋 200개면 충분"과 같은 숫자.

### 6. 한국어로 쓸 때

지표마다 프롬프트가 1~2개씩 있고, **각각** `adapt`해야 한다:

```python
from ragas.llms import llm_factory
from ragas.metrics.collections import Faithfulness

llm = llm_factory("gpt-5-mini", client=AsyncOpenAI())
m = Faithfulness(llm=llm)
m.statement_generator_prompt = await m.statement_generator_prompt.adapt(
    target_language="korean", llm=llm, adapt_instruction=True)
m.nli_statement_prompt = await m.nli_statement_prompt.adapt(
    target_language="korean", llm=llm, adapt_instruction=True)
```

함정 4가지:
1. 기본 `adapt_instruction=False`면 few-shot 예시만 번역되고 지시문은 영어로 남는다.
2. `adapt()`는 LLM 번역 호출이라 비용·비결정성이 붙고, 0.4.x에서 `BasePrompt` 기반 프롬프트의 save/load는 미구현 → 매번 재번역이므로 **캐싱 필수** (`DiskCacheBackend`).
3. 문자열 지표는 BLEU 대신 CHRF.
4. 한국어 성능 수치는 공식 문서에 없다(예시는 힌디어·스페인어·독일어). **5절의 정렬 실험을 한국어로 직접 해야 신뢰할 수 있다.**

### 7. 비용·재현성

- 토큰 사용량은 기본으로 안 센다. `token_usage_parser=get_token_usage_for_openai`를 넘겨야 `results.total_tokens()`, `results.total_cost(...)`가 나온다.
- 지표별 LLM 호출: AnswerCorrectness 3회 > AnswerAccuracy 2회 > RubricsScore 1회. 대량 평가면 AnswerAccuracy가 가성비.
- 비결정성: 같은 입력에 같은 점수가 안 나올 수 있다고 문서가 명시. 온도 고정 + 캐시 + 절대값 대신 상대 변화 비교.
- claim이 하나뿐인 짧은 답은 faithfulness가 0 아니면 1로 양자화된다. 등급형 지표(0/2/4)도 마찬가지. 샘플 수로 평균내야 의미가 있다.

### 8. 대안과의 비교

| 도구 | RAGAS와 다른 점 |
|---|---|
| **DeepEval** | G-Eval 중심(기준에서 CoT 평가 단계 자동 생성, 출력 토큰 확률로 점수 가중). pytest 스타일 단위 테스트 통합 |
| **TruLens** | 지표 카탈로그 대신 **RAG Triad**(Context Relevance → Groundedness → Answer Relevance) 3축으로 좁힘. 앱 실행을 계측해 피드백 함수를 트레이스에 붙임 |
| **ARES** | 프롬프트 심판 대신 **합성 데이터로 경량 심판 모델을 파인튜닝**, 사람 라벨 수백 건으로 PPI 신뢰구간. 연구 지향 |
| **Phoenix (Arize)** | OpenTelemetry 트레이스 관측 플랫폼이 본체, 평가는 그 위의 기능. RAGAS 공식 트레이싱 파트너 |
| **LangSmith** | 데이터셋 + 평가자 함수 + 실험 하네스. RAG 지표는 직접 쓰거나 openevals |
| **promptfoo** | YAML + assertion CLI. `context-faithfulness`, `context-recall`, `answer-relevance` 어서션 내장(RAGAS 개념 재구현). CI 회귀 테스트에 적합 |

정리: **지표 정의는 RAGAS가 사실상 표준이 됐고, 도구는 관측 플랫폼(Phoenix·LangSmith·Langfuse)이나 CI 러너(promptfoo)로 옮겨가는 중.** RAGAS의 지표 개념을 알면 어느 도구에서든 같은 걸 찾을 수 있다.

## 예시 / 코드

0.4 스타일 최소 예시. 검색 층은 ID 기반(LLM 불필요), 생성 층은 faithfulness + factual correctness.

```python
import asyncio
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    Faithfulness, FactualCorrectness, IDBasedContextRecall,
)

llm = llm_factory("gpt-5-mini", client=AsyncOpenAI())

sample = dict(
    user_input="카톡 방에서 9월 모임 장소를 정한 사람은 누구?",
    retrieved_contexts=["[2026-09-02 21:03] A: 이번엔 강남으로 하죠", "..."],
    retrieved_context_ids=["c_1042", "c_1043", "c_0877"],
    response="A가 강남으로 제안했고 그대로 확정됐다.",
    reference="A가 9월 2일에 강남을 제안했다.",
    reference_context_ids=["c_1042"],
)

async def main():
    recall = await IDBasedContextRecall().ascore(
        retrieved_context_ids=sample["retrieved_context_ids"],
        reference_context_ids=sample["reference_context_ids"])
    faith = await Faithfulness(llm=llm).ascore(
        user_input=sample["user_input"],
        response=sample["response"],
        retrieved_contexts=sample["retrieved_contexts"])
    fact = await FactualCorrectness(llm=llm, mode="f1").ascore(
        response=sample["response"], reference=sample["reference"])
    for name, r in [("recall", recall), ("faithfulness", faith), ("factual", fact)]:
        print(name, r.value, getattr(r, "reason", None))

asyncio.run(main())
```

합성 테스트셋 생성 뼈대:

```python
from ragas.testset import TestsetGenerator
from ragas.testset.graph import KnowledgeGraph
from ragas.testset.synthesizers import (
    SingleHopSpecificQuerySynthesizer, MultiHopSpecificQuerySynthesizer,
)

gen = TestsetGenerator(llm=llm, embedding_model=emb)
testset = gen.generate_with_langchain_docs(
    docs, testset_size=50,
    query_distribution=[
        (SingleHopSpecificQuerySynthesizer(llm=llm), 0.6),
        (MultiHopSpecificQuerySynthesizer(llm=llm), 0.4),
    ])
df = testset.to_pandas()   # user_input, reference_contexts, reference, synthesizer_name
gen.knowledge_graph.save("kg.json")   # 재생성 비용 절감
```

## 궁금한 점 / 더 알아볼 것

- [ ] 카톡 코퍼스로 KG 기반 테스트셋 50개 생성 → 3주차 멀티홉 실습의 golden set으로 재사용
- [ ] 한국어 faithfulness 심판 정렬: 사람 라벨 100개 vs gpt-5-mini 일치율 측정 (adapt_instruction 유무 비교)
- [ ] promptfoo의 `context-faithfulness` 어서션과 RAGAS Faithfulness가 같은 샘플에서 얼마나 다르게 나오는지
- [ ] 업스트림 정체의 원인 확인 (회사 방향 전환인지, 비공개 이전인지)

## 스터디에서 나눌 이야기

- 공용 골든셋을 만든다면 `reference_context_ids`까지만 만들지, `reference`(모범 답안)까지 만들지 — 후자여야 FactualCorrectness·NoiseSensitivity가 열린다
- 지표는 3~4개로 제한하자는 제안: recall@k(ID), Faithfulness, FactualCorrectness, + 대화용 TopicAdherence
- 심판 모델을 gpt-5-mini로 통일할 때 자기선호 편향(생성기도 GPT)을 어떻게 다룰지
