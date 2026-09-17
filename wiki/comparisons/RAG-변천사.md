---
title: RAG 변천사 — 두 개의 연표
type: comparison
tags: [concept, comparison]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [sese2204, kdyann, dldusgh318]
weeks: [2]
---

> 2019년 DPR·원조 RAG에서 2026년 Agentic RAG까지의 계보. sese2204와 kdyann이 같은 논문 집합을 각각 4기와 6기로 나눠 정리했고, 이 페이지는 두 연표를 나란히 놓고 갈리는 지점을 표시한다.

## RAG란 무엇인가

- 질문과 관련된 정보를 외부 저장소에서 검색해 생성 모델의 입력에 넣어 답을 만드는 방법. kdyann은 Lewis et al.(2020)의 용어로 모델 가중치에 든 지식을 **파라메트릭 메모리**, 문서 저장소·검색 인덱스를 **비파라메트릭 메모리**라 부르고, RAG는 둘을 결합해 재학습 없이 새 문서를 쓰게 하는 것이라고 정리했다.
- 원 논문의 RAG는 retriever와 generator를 **함께 학습**시키는 구조다(RAG-Sequence는 출력 시퀀스 전체에 같은 문서 집합, RAG-Token은 토큰마다 다른 문서). 지금 우리가 부르는 RAG(고정 검색기 + 프롬프트 주입)와 다르니 원 논문을 읽을 때 이 간극을 알고 읽어야 한다 (sese2204, kdyann 공통).

## 두 연표

| 시기 | sese2204 (4기) | kdyann (6기) | 대표 기술 |
|---|---|---|---|
| 2019~2021 | 1기 검색의 재발명 | 1기 Dense Retrieval과 원조 RAG | Sentence-BERT(2019), DPR(2020), RAG(2020), ColBERT(2020), BEIR(2021) |
| 2022~2023 | 2기 Naive RAG 대량생산과 반성 | 2기 Naive RAG의 대중화 | LangChain·LlamaIndex, "PDF → 청킹 → 벡터DB → top-k → 프롬프트" |
| 2023~2024 | (2기에 포함) | 3기 Advanced·Modular RAG | Gao et al. 서베이(2023)의 Naive / Advanced / Modular 3분류 |
| 2024 | 3기 컨텍스트 손실과의 싸움 | 4기 평가·교정하는 RAG | Self-RAG, CRAG, Adaptive-RAG |
| 2024~ | (3기에 포함) | 5기 문맥과 관계를 보존하는 RAG | RAPTOR, Contextual Retrieval, Late Chunking, GraphRAG |
| 2025~2026 / 현재 | 4기 파이프라인에서 루프로 | 6기 Agentic RAG | Adaptive RAG 라우팅, 검색을 도구로 두는 에이전트 |

> ⚠️ Contradiction: **Adaptive RAG의 자리**가 다르다. sese2204는 4기(2025~2026)에 두고 "프로덕션 베스트 프랙티스로 언급됨"이라 썼고, kdyann은 Jeong et al.(NAACL 2024) 논문 기준으로 2024년 4기에 넣었다. 논문 발표는 2024년이고 실무 채택은 그 뒤이니 둘 다 틀리지 않지만, 연표에 옮길 때는 기준(발표 vs 채택)을 명시해야 한다. 출처: [sese2204 01](../../members/sese2204/notes/01-rag-history.md) §4기, [kdyann 01](../../members/kdyann/notes/01-rag-history.md) §4기.

> ⚠️ Contradiction: **BEIR의 결론 강도**. sese2204는 "도메인 밖에서는 BM25가 여전히 강하다 → 하이브리드 검색의 근거"라고 단정했고, kdyann은 "제로샷 성능이 데이터셋과 도메인에 따라 달라질 수 있음"으로 완화했다. [[하이브리드-검색과-RRF]]의 근거로 쓸 때는 kdyann 쪽 표현이 안전하다.

포함 범위도 다르다. ColBERT와 Sentence-BERT는 sese2204에만, RAG-Sequence/RAG-Token 구분과 파라메트릭 메모리 용어는 kdyann에만 있다. 논문 링크는 kdyann이 11편 전부 달아 두었고 sese2204는 미독 체크리스트로 남겼다.

## 시기별 핵심

- **1기**: DPR이 dense retrieval로 BM25를 처음 확실히 이겼고(top-20 passage retrieval accuracy, 구체 수치는 노트에 없음), BEIR가 도메인 밖에서는 그 우위가 뒤집힐 수 있음을 보였다. 이 두 사실이 [[하이브리드-검색과-RRF]]의 출발점이다.
- **2기**: ChatGPT 이후 튜토리얼 RAG가 대량생산되고 안 되는 이유들이 쏟아졌다. kdyann이 정리한 Naive RAG 한계 5가지: 필요한 문서 미포함, 청킹으로 주어·대명사·문맥 소실, 점수는 높지만 불필요한 문서 포함, 단순·복잡 질문을 같은 방식으로 검색, 올바른 문서를 줘도 생성 모델이 근거를 무시. 이 다섯이 이후 기법들의 목차가 된다.
- **Advanced RAG의 4단계**(kdyann): 검색 전(정제·의미 단위 [[청킹-전략|청킹]]·메타데이터·[[쿼리-재작성]]) → 검색 중([[하이브리드-검색과-RRF|하이브리드]]·메타데이터 필터) → 검색 후([[리랭커|리랭킹]]·중복 제거·압축) → 생성 후([[RAG-루프와-근거-인용|근거 일치·인용 확인]]). "핵심이 '벡터 DB를 쓰는가'에서 '무엇을 언제 어떻게 검색하고 결과를 어떻게 정제할 것인가'로 확장됐다."
- **3~5기**: 청크를 자르는 순간 맥락이 끊기는 문제에 대한 답들. RAPTOR(요약 트리), Late Chunking(임베딩 먼저 청킹 나중), Contextual Retrieval(청크마다 LLM 맥락 요약 프리픽스), GraphRAG(엔티티 그래프, local/global search — [[지식그래프와-온톨로지]] 참조), Self-RAG(reflection token)·CRAG(retrieval evaluator, 나쁘면 웹 검색으로 교정).
- **6기 / 4기**: 고정 파이프라인 → 계획·검색·충분성 평가·재검색 루프. sese2204는 에이전틱 RAG가 단순 파이프라인 대비 **쿼리당 약 10배 비용 + 수 초 지연**이라 적었다(출처 미표기). kdyann은 "반복 검색은 호출 횟수·응답 시간·비용·실패 지점을 늘린다. 단순한 구조부터 시작해야 한다"로 같은 결론을 정성적으로 냈다.

## 이 스터디에서의 위치

- dldusgh318은 실습을 거쳐 "지금까지의 발전은 대체가 아니라 누적이다. grep → BM25 → Vector → Hybrid RAG → Relation/Graph"라고 정리했다. [[검색의-세-세대]]와 [[멀티홉-질문과-Bridge-Entity]]가 이 누적의 앞뒤다.
- sese2204는 『AI 에이전트 엔지니어링』(마이클 알바다 저, 강민혁 역, 한빛미디어 2026.01)과의 매핑표를 붙였다. 그 책에서 RAG는 6.2.3 한 절이고, 책이 주는 것은 "RAG를 에이전트 안에 어떻게 배치할 것인가"(검색을 도구로 볼지 메모리로 볼지)다. [[OpenViking-컨텍스트-데이터베이스]]가 그 "메모리" 쪽 설계안이다.
- kdyann의 열린 질문 "복잡한 기법을 추가하기 전에 현재 검색 품질이 충분한지 어떤 지표로 판단할까"의 답 후보가 [[RAG-평가-지표]]다.

## 관련

- [[검색의-세-세대]] · [[하이브리드-검색과-RRF]] · [[청킹-전략]] · [[리랭커]] · [[쿼리-재작성]] · [[RAG-평가-지표]] · [[지식그래프와-온톨로지]] · [[멀티홉-질문과-Bridge-Entity]]

## 출처

- sese2204 · 고전 RAG 기술 변천사 — [members/sese2204/notes/01-rag-history.md](../../members/sese2204/notes/01-rag-history.md)
- kdyann · RAG 기술 변천사 — [members/kdyann/notes/01-rag-history.md](../../members/kdyann/notes/01-rag-history.md)
- dldusgh318 · Multi-hop (§그래서 다음은?) — [members/dldusgh318/notes/week3/06-multi-hop-rag.md](../../members/dldusgh318/notes/week3/06-multi-hop-rag.md)
- 외부(kdyann 노트의 링크): Lewis et al. 2020 https://papers.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html · Karpukhin et al. DPR 2020 https://aclanthology.org/2020.emnlp-main.550/ · Thakur et al. BEIR 2021 https://arxiv.org/abs/2104.08663 · Gao et al. Survey 2023 https://arxiv.org/abs/2312.10997 · Asai et al. Self-RAG https://openreview.net/forum?id=hSyW5go0v8 · Yan et al. CRAG https://arxiv.org/abs/2401.15884 · Sarthi et al. RAPTOR (ICLR 2024) · Jeong et al. Adaptive-RAG https://aclanthology.org/2024.naacl-long.389/ · Edge et al. GraphRAG https://arxiv.org/abs/2404.16130 · Anthropic Contextual Retrieval https://www.anthropic.com/engineering/contextual-retrieval · Günther et al. Late Chunking https://arxiv.org/abs/2409.04701
- 외부(sese2204): Khattab & Zaharia ColBERT https://arxiv.org/abs/2004.12832 · 『AI 에이전트 엔지니어링』(한빛미디어, 2026.01) · arXiv 2504.19754 · arXiv 2506.10408
