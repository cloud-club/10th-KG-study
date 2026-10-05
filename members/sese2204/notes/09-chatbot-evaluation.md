---
title: 챗봇 평가 기준 — 무엇을, 어느 층에서, 누가 재는가
date: 2026-09-16
tags: [evaluation, llm-as-judge, rag, golden-set, mt-bench, chatbot-arena, rgb, ragchecker]
status: done
---

# 09. 챗봇 평가 기준 — 무엇을, 어느 층에서, 누가 재는가

> 참고 자료:
> - [Zheng et al., Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (NeurIPS 2023)](https://arxiv.org/abs/2306.05685) — LLM 심판의 타당성과 편향을 처음 체계적으로 검증
> - [Chen et al., Benchmarking LLMs in RAG (RGB, 2023)](https://arxiv.org/abs/2309.01431) — RAG가 갖춰야 할 4가지 능력
> - [Ru et al., RAGChecker (NeurIPS 2024)](https://arxiv.org/abs/2408.08067) — 클레임 단위 진단 지표
> - [Katsis et al., MTRAG (TACL 2025)](https://arxiv.org/abs/2501.03468) — 멀티턴 RAG 벤치마크
> - [Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge (2024)](https://arxiv.org/abs/2410.02736), [Self-Preference Bias in LLM-as-a-Judge (2024)](https://arxiv.org/abs/2410.21819)
> - 이전 노트 [07. RAG 평가와 실습 로드맵](07-rag-evaluation.md)의 "검색/생성 분리" 원칙을 확장

## 한 줄 요약

챗봇 평가는 "정답이 하나가 아닌 출력"을 재는 문제라서, **어느 층(검색·생성·대화·시스템)을**, **무엇을 기준으로(정답셋·근거·루브릭)**, **누가(사람·LLM·규칙)** 채점하는지를 먼저 정해야 지표가 의미를 가진다.

## 핵심 개념

- **층위 분리**: 검색 실패와 생성 실패, 그리고 대화 맥락 실패는 원인이 다르므로 따로 잰다.
- **기준(reference)의 종류**: 정답 문장, 정답 근거 문서, 채점 루브릭, 비교 대상 응답. 지표마다 요구하는 기준이 다르다.
- **심판의 종류**: 규칙 기반(정확 일치·BLEU·ROUGE), 임베딩 유사도, 사람, LLM-as-judge. 비용·재현성·타당성이 트레이드오프.
- **LLM-as-judge는 사람과 80% 이상 일치**하지만 위치·장황함·자기선호 편향이 있어 설계로 보정해야 한다.
- **오프라인 골든셋 → 온라인 신호**로 이어지는 루프가 실무 표준. 프로덕션 실패 사례를 테스트 케이스로 환류시킨다.

## 상세 정리

### 1. 왜 챗봇 평가가 어려운가

전통 ML은 라벨이 하나이고 정확도로 끝난다. 챗봇은

- 같은 질문에 여러 "맞는" 답이 있고 (표현·길이·상세도 자유)
- 답의 품질이 여러 축(정확성, 근거 충실도, 관련성, 안전성, 톤)으로 갈라지며
- 멀티턴이면 이전 턴의 맥락에 따라 같은 답이 맞기도 틀리기도 한다.

그래서 "정확도 몇 %"라는 단일 숫자는 거의 없고, **축을 분해한 지표 묶음**으로 본다.

### 2. 평가 층위 4단

| 층 | 묻는 것 | 대표 지표 | 필요한 기준 |
|---|---|---|---|
| ① 검색 (Retrieval) | 필요한 문서를 가져왔나 | recall@k, precision@k, NDCG@k, MRR, context precision/recall | 질문별 정답 청크 ID (골든셋) |
| ② 생성 (Generation) | 가져온 문서로 제대로 답했나 | faithfulness/groundedness, answer relevancy, answer correctness | 근거 문서(참조 없이 가능) 또는 정답 문장 |
| ③ 대화 (Conversation) | 앞 턴을 이어받아 답했나 | 턴별 faithfulness, 지시대명사 해소 정확도, 무응답(unanswerable) 처리율, 주제 일관성(topic adherence) | 대화 로그 + 턴별 정답, 정답 없음 표시 |
| ④ 시스템 (System) | 쓸 만한가 | p50/p99 지연, 토큰 비용, 거부율, 안전성 위반율, 사용자 만족(thumbs up) | 로그, 가드레일 규칙 |

07번 노트에서 정리한 "검색 실패 vs 생성 실패" 구분이 ①②이고, 이번에 ③④를 추가한 것.

### 3. RAG 챗봇이 갖춰야 할 4가지 능력 (RGB 벤치마크)

Chen et al.(2023)은 LLM이 RAG 세팅에서 가져야 할 능력을 넷으로 정의했다. 지표를 설계할 때 체크리스트로 쓰기 좋다.

| 능력 | 정의 | 테스트 방법 |
|---|---|---|
| **Noise robustness** | 관련 없는 문서가 섞여도 정답을 낸다 | 정답 문서 + 노이즈 문서 비율을 바꿔가며 정확도 측정 |
| **Negative rejection** | 근거가 없으면 "모른다"고 한다 | 정답 문서를 빼고 넣었을 때 거부율 |
| **Information integration** | 여러 문서를 합쳐 답한다 | 답이 두 문서 이상을 요구하는 질문 |
| **Counterfactual robustness** | 문서가 틀렸을 때 그대로 따르지 않는다 | 일부러 오류가 있는 문서를 주고 자기 지식으로 잡아내는지 |

논문 결론: 노이즈 견디기는 어느 정도 되지만 **거부·통합·반사실 셋은 모두 크게 취약**했다. 즉 "검색이 좋아지면 답도 좋아진다"는 가정이 깨지는 구간이 있고, 이걸 재려면 ② 층 지표만으로 부족하다.

### 4. 기준(reference)의 유형

지표를 고르기 전에 **어떤 정답 데이터를 만들 수 있는가**부터 정해야 한다. 만들기 쉬운 순서로:

| 유형 | 내용 | 만들기 | 쓰이는 곳 |
|---|---|---|---|
| 없음 (reference-free) | 질문·검색결과·응답만 | 프로덕션 로그 그대로 | faithfulness, answer relevancy, aspect critic |
| 정답 근거 (reference contexts) | 질문별 관련 청크 ID 목록 | 코퍼스에서 사람이 표시 또는 질문을 청크에서 역생성 | recall@k, NDCG, context recall |
| 정답 문장 (reference answer) | 질문별 모범 답안 | 사람이 작성 또는 LLM 초안 + 사람 검수 | answer correctness, factual correctness, semantic similarity |
| 루브릭 (rubric) | 점수별 기준 서술 (1점: …, 5점: …) | 도메인 전문가가 작성 | rubric score, instance-specific rubric |
| 선호 쌍 (preference pair) | 응답 A vs B 중 승자 | 크라우드 투표 (Chatbot Arena 방식) | Elo/Bradley-Terry 랭킹 |

**중요한 구분**: reference-free 지표는 "정답과 맞나"가 아니라 "주어진 근거와 모순 없나"를 잰다. 근거 자체가 틀리면 만점이 나온다. 그래서 검색 층은 반드시 reference contexts 기반으로 따로 재야 한다. 자세한 정답셋 유형과 합성 방법은 [10. RAGAS](10-ragas.md)에서.

### 5. 누가 채점하는가

| 심판 | 장점 | 단점 | 적합한 곳 |
|---|---|---|---|
| 규칙/문자열 (exact match, BLEU, ROUGE) | 공짜, 재현 가능 | 표현이 조금만 달라도 0점. 개방형 답변에 무의미 | 분류·추출·SQL처럼 답이 고정된 태스크 |
| 임베딩 유사도 | 저렴, 표현 차이에 관대 | "부정문"을 못 잡음 (맞다/아니다가 비슷하게 나옴) | 정답 문장과 대략적 근접도 |
| 사람 | 타당성 최고 | 비싸고 느리고 사람끼리도 80% 정도만 일치 | 골든셋 검수, 루브릭 작성, 심판 캘리브레이션 |
| LLM-as-judge | 확장성, 사람과 80%+ 일치 | 편향, 비결정성, 비용, 자기 모델 선호 | 대량 오프라인 평가, 온라인 샘플링 모니터링 |

### 6. LLM-as-judge: 근거와 함정

**근거** — Zheng et al.(2023)이 MT-Bench(80문항 멀티턴, 8개 카테고리)와 Chatbot Arena(크라우드 투표 3만 건)로 검증: GPT-4 심판과 사람의 일치율이 80%를 넘었고, 이는 **사람끼리의 일치율과 같은 수준**. 이후 LLM 심판이 사실상 표준이 된 출발점.

**같은 논문이 보고한 편향 3종과 보정법**

| 편향 | 현상 | 보정 |
|---|---|---|
| Position bias | 쌍대 비교에서 먼저 제시된 답을 선호 | 순서를 바꿔 두 번 채점, 결과가 다르면 무승부 처리 |
| Verbosity bias | 긴 답을 선호 | 길이 페널티 루브릭, 단일 답 채점(single-answer grading)으로 전환 |
| Self-enhancement bias | 자기(같은 계열) 모델 출력을 선호 | 다른 계열 모델을 심판으로, 또는 복수 심판 |

이 외에 후속 연구들이 지적한 것: 심판 프롬프트 형식 편향, 캘리브레이션 드리프트(모델 버전이 바뀌면 점수 분포가 이동), 자기 출력 인식 능력과 자기선호 강도의 선형 상관(Panickssery et al. 2024).

**실무 규칙**
1. 심판 모델·프롬프트·온도를 **고정하고 버전 기록**한다. 바꾸면 이전 점수와 비교 불가.
2. 쌍대 비교는 **양방향 채점**이 기본.
3. 절대 점수보다 **동일 골든셋에서의 상대 변화**를 본다.
4. 골든셋의 일부(50~100개)는 **사람이 채점해 심판과의 일치율을 먼저 확인**한다. 일치율이 낮으면 루브릭을 고친다.
5. 심판에게 **근거를 먼저 쓰게(CoT) 한 뒤 점수**를 내게 한다. 점수 먼저 내면 사후 합리화가 늘어난다.

### 7. 멀티턴 챗봇 평가 (MTRAG)

단일 질의응답 벤치마크로는 챗봇의 실제 실패를 못 잡는다. IBM의 MTRAG(2025)는 사람이 만든 110개 대화(평균 7.7턴, 총 842 태스크, 4개 도메인)로 다음을 강제한다:

- **후반 턴**: 대화가 길어질수록 검색·생성이 모두 나빠진다.
- **비독립 질문(non-standalone)**: "그럼 그건 언제야?"처럼 앞 턴 없이는 의미가 없는 질문. 쿼리 재작성(06번 노트) 성능이 여기서 드러난다.
- **답할 수 없는 질문(unanswerable)**: 코퍼스에 답이 없을 때 거부하는지. RGB의 negative rejection과 같은 축.
- 평가는 검색(nDCG@5)과 생성(품질·근거 충실도의 조화평균)을 분리해서 낸다.

우리 실습에 시사하는 것: 골든셋을 만들 때 **단일 질문만 만들면 ③ 층을 아예 못 잰다**. 3~5턴짜리 대화 시나리오를 일부 포함시켜야 한다.

### 8. 진단형 지표: RAGChecker

RAGAS류가 "점수"를 주는 데 비해 RAGChecker(Amazon, 2024)는 응답을 **클레임 단위로 쪼개 근거와의 함의(entailment)를 판정**하고, 그 결과를 검색기/생성기 지표로 분해한다.

- Retriever: claim recall, context precision
- Generator: context utilization(가져온 근거를 얼마나 썼나), noise sensitivity(노이즈 문서에 얼마나 휘둘렸나), hallucination, self-knowledge(근거 없이 자기 지식으로 답한 비율), faithfulness
- 사람 판단과의 상관이 기존 지표보다 유의미하게 높다고 보고.

즉 "점수가 낮다"에서 끝나지 않고 "**리랭커가 노이즈를 못 걸러서 생성기가 휘둘렸다**"까지 내려갈 수 있다. RAGAS 0.2 이후의 noise sensitivity 지표는 이 아이디어를 가져온 것.

### 9. 오프라인 → 온라인 평가 루프

```
골든셋(오프라인)          프로덕션(온라인)
  ├ 검색 IR 지표             ├ 샘플링해서 LLM 심판 채점
  ├ RAGAS/루브릭 채점        ├ 사용자 피드백(👍👎), 재질문율, 이탈
  └ 회귀 테스트 (CI)         └ 지연·비용·가드레일 위반
        ▲                          │
        └── 실패 사례를 골든셋에 추가 ┘
```

- 배포 전: 같은 골든셋으로 회귀 테스트. 기법 하나 붙일 때마다 측정(07번 로드맵).
- 배포 후: 트레이스(검색 호출·리랭크·생성 span)마다 평가 결과를 붙여 저장하는 게 2026년 관측 도구들의 공통 패턴.
- 프로덕션에서 잡힌 환각·오검색은 **바로 테스트 케이스로 환류**. 골든셋은 정적이 아니라 자란다.

## 예시 / 코드

양방향 쌍대 비교로 위치 편향을 상쇄하는 심판 호출 뼈대:

```python
def pairwise_judge(question, ans_a, ans_b, judge):
    v1 = judge(question, first=ans_a, second=ans_b)  # "A" | "B" | "tie"
    v2 = judge(question, first=ans_b, second=ans_a)
    v2 = {"A": "B", "B": "A", "tie": "tie"}[v2]       # 자리 바꿨으니 되돌림
    return v1 if v1 == v2 else "tie"                  # 불일치 → 무승부
```

## 궁금한 점 / 더 알아볼 것

- [ ] 한국어 골든셋에서 GPT 계열 심판의 사람 일치율이 영어와 같은 80% 수준인지 직접 50개로 확인
- [ ] 카톡 대화 코퍼스(랩 02)에서 멀티턴 시나리오 골든셋 20개 만들기
- [ ] RAGChecker를 카톡 RAG에 붙여 noise sensitivity를 리랭커 유무로 비교

## 스터디에서 나눌 이야기

- 우리 스터디 공용 골든셋을 만든다면: 정답 근거(청크 ID)까지만 만들지, 정답 문장까지 만들지
- LLM 심판 모델을 gpt-5-mini로 통일할지, 심판 편향 때문에 다른 계열도 둘지
- "답할 수 없는 질문"을 골든셋의 몇 %로 넣을지
