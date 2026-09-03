---
title: 고전 RAG 기술 변천사
date: 2026-09-03
tags: [rag, retrieval, dpr, colbert, beir, agentic-rag]
status: done
---

# 01. 고전 RAG 기술 변천사

> 참고 자료:
> - Lewis et al., RAG (2020)
> - Karpukhin et al., DPR (2020)
> - Thakur et al., BEIR (2021)
> - Khattab & Zaharia, ColBERT (2020)
> - Gao et al., RAG for LLMs: A Survey (arXiv 2312.10997)
> - 『AI 에이전트 엔지니어링』 (마이클 알바다 저 / 강민혁 역, 한빛미디어, 2026.01)

## 한 줄 요약

RAG는 "키워드 매칭 → 의미 매칭"(2019~2021), "Naive RAG 대량생산과 반성"(2022~2023), "컨텍스트 손실과의 싸움"(2024), "파이프라인에서 루프로"(2025~2026) 네 시기를 거쳐 왔다.

## 핵심 개념

- 원 논문의 RAG는 retriever와 generator를 **함께 학습**시키는 구조라서, 지금 우리가 부르는 RAG(고정 검색기 + 프롬프트 주입)와 다르다.
- BEIR: 도메인 밖에서는 BM25가 여전히 강하다 → 하이브리드 검색의 근거.
- Naive / Advanced / Modular RAG 3분류가 표준 용어가 됨.
- 에이전틱 RAG는 쿼리당 약 10배 비용 + 수 초 추가 지연. 무조건 좋은 선택이 아니다.

## 상세 정리

이 시리즈의 구성:

1. 기술 변천사 (이 노트)
2. [청킹 전략](02-chunking.md)
3. [임베딩 모델 비교](03-embedding-models.md)
4. [하이브리드 검색 (BM25 + 벡터)](04-hybrid-search.md)
5. [리랭커](05-reranker.md)
6. [쿼리 재작성](06-query-rewriting.md)
7. [평가와 실습 로드맵](07-rag-evaluation.md)

### 1기 — 검색의 재발명 (2019~2021)

| 연도 | 기술 | 의미 |
|---|---|---|
| 2019 | Sentence-BERT | bi-encoder로 문장을 벡터 하나에 담는 방식의 실용화. 현재 임베딩 모델의 조상 |
| 2020 | DPR (Karpukhin et al.) | dense retrieval이 BM25를 처음으로 확실히 이긴 사건. "키워드 매칭 → 의미 매칭" 전환의 출발점 |
| 2020 | **RAG (Lewis et al.)** | 용어의 출처. 원래는 retriever와 generator를 **함께 학습**시키는 구조 |
| 2020 | ColBERT (Khattab & Zaharia) | 토큰별 벡터를 유지하고 MaxSim으로 매칭하는 late interaction. 저장 비용 때문에 외면받았다가 2024년 부활 |
| 2021 | BEIR (Thakur et al.) | 제로샷 검색 벤치마크. **도메인 밖에서는 BM25가 여전히 강하다** → 하이브리드 검색의 근거 |

> ⚠️ 원 논문의 RAG는 지금 우리가 부르는 RAG(고정 검색기 + 프롬프트 주입)와 다르다. 이 간극을 알고 읽어야 덜 헷갈린다.

### 2기 — Naive RAG의 대량생산과 반성 (2022~2023)

ChatGPT 이후 LangChain / LlamaIndex 폭발.
"PDF → 청킹 → 벡터DB → top-k → 프롬프트"가 표준 튜토리얼이 되고,
동시에 그게 잘 안 되는 이유들이 쏟아짐.

이 시기의 정리 = **Gao et al., "RAG for LLMs: A Survey" (arXiv 2312.10997)**

여기서 나온 3분류가 표준 용어가 됨:

- **Naive RAG** — 단순 retrieve-read
- **Advanced RAG** — 밀집 의미 매칭, 리랭킹, 멀티홉 쿼리 + 세분화된 청킹, 메타데이터 인지 검색
- **Modular RAG** — 인덱싱·검색·생성을 교체 가능한 모듈로 분해·조합

### 3기 — 컨텍스트 손실과의 싸움 (2024)

청크를 자르는 순간 대명사·참조가 끊긴다는 문제가 전면화.

- **RAPTOR** — 문서를 클러스터링해 요약 트리 구성, 계층 검색
- **GraphRAG (Microsoft)** — 엔티티 그래프로 전역 질의("이 문서 전체의 주제는?") 대응
- **Late Chunking (Jina)** — 문서 전체를 먼저 토큰 단위로 인코딩한 뒤 청크로 나눠 풀링. 자르기를 임베딩 *이후*로 미룸
- **Contextual Retrieval (Anthropic)** — 청크마다 짧은 맥락 요약을 LLM으로 생성해 앞에 붙인 뒤 임베딩
- **Self-RAG / CRAG** — 검색 결과가 쓸만한지 모델이 스스로 판정하고 재검색

### 4기 — 파이프라인에서 루프로 (2025~2026)

고정된 선형 파이프라인 → 계획·검색·충분성 평가·재검색을 반복하는 에이전트 루프.

- **Adaptive RAG** — 쿼리 복잡도에 따라 "검색 안 함 / 1회 / 다단계"로 라우팅. 프로덕션 베스트 프랙티스로 언급됨
- **Agentic RAG** — 검색을 도구로 두고 에이전트가 오케스트레이션

> 💰 비용 감각: 단순 파이프라인 대비 에이전틱 RAG는 쿼리당 약 10배 비용 + 수 초의 추가 지연.
> 무조건 좋은 선택이 아니다.

### 『AI 에이전트 엔지니어링』과의 매핑

마이클 알바다 저 / 강민혁 역, 한빛미디어 (2026.01.23), 404쪽
원서: *Building Applications with AI Agents*

| 이 시리즈의 주제 | 책의 해당 부분 |
|---|---|
| RAG 기본 | 6.2.3 RAG: 검색 증강 생성 |
| 벡터 스토어 / 시맨틱 검색 | 6.2.1~6.2.2 |
| 전체 텍스트 검색 (BM25 계열) | 6.1.2 |
| 컨텍스트 윈도 관리 | 6.1.1 |
| GraphRAG | 6.3 그래프RAG |
| 쿼리 분해 / 반복 검색 | 5.1.4 쿼리 분해 에이전트, 5.1.6 심층 리서치 에이전트 |
| 검색을 도구로 노출 | 4장 도구, 5.2 도구 선택 |
| 컨텍스트 엔지니어링 | 5.5 |
| 평가 | 9.2.3 메모리 평가, 9.3 총체적 평가 |

> ⚠️ 이 책에서 RAG는 **한 개 절**이다. 청킹 전략, 임베딩 모델 비교, 하이브리드 검색,
> 리랭커, 쿼리 재작성의 세부는 이 책의 관심사가 아니다.
> 책에서 얻는 것은 **"RAG를 에이전트 안에 어떻게 배치할 것인가"** — 검색을 도구로 볼지
> 메모리로 볼지, 컨텍스트 윈도와 어떻게 경쟁시킬지 같은 설계 판단.

역자 강민혁 님의 챕터별 강의 영상이 유튜브에 공개되어 있음.

## 궁금한 점 / 더 알아볼 것

### 필수 5편 (이것만으로 계보의 8할)

- [ ] Lewis et al., **RAG** (2020) — 원조
- [ ] Karpukhin et al., **DPR** (2020) — dense retrieval
- [ ] Thakur et al., **BEIR** (2021) — 왜 BM25를 못 버리는가
- [ ] Khattab & Zaharia, **ColBERT** (2020) — late interaction
- [ ] Gao et al., **RAG for LLMs: A Survey** (arXiv 2312.10997) — 전체 지도

### 그다음

- [ ] **HyDE** — 가상 문서 생성 검색
- [ ] **Self-RAG** — 자기 판정 검색
- [ ] **CRAG (Corrective RAG)** — 검색 품질 교정
- [ ] **RAPTOR** — 계층 요약 트리
- [ ] **GraphRAG** (Microsoft)
- [ ] Anthropic, **Contextual Retrieval** 블로그 포스트
- [ ] Jina, **Late Chunking** 포스트
- [ ] **arXiv 2504.19754** — 청킹 전략 통제 비교

### 에이전트 쪽으로 넘어갈 때

- [ ] **arXiv 2506.10408** — Reasoning Agentic RAG 서베이

## 스터디에서 나눌 이야기

- 원 논문의 RAG(공동 학습)와 지금의 RAG(고정 검색기 + 프롬프트 주입)의 간극을 어떻게 볼 것인가
- 에이전틱 RAG의 10배 비용을 감수할 만한 쿼리는 어떤 것인가

---

*벤치마크 수치와 모델명은 2026년 중반 기준. 임베딩·리랭커 모델은 교체 주기가 빠르므로
구체적 모델 선택 시에는 최신 MTEB / MMTEB / BEIR 표를 다시 확인할 것.*
