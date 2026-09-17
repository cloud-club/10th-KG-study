---
title: "RAG 루프와 Retrieval Evaluation: 어디서 틀렸는지 구분하기"
date: 2026-09-17
tags: [rag, retrieval-evaluation, beir, recall, mrr, ndcg, qrels]
status: done
---

# RAG 루프와 Retrieval Evaluation: 어디서 틀렸는지 구분하기

`chat.py`(질문 하나를 받아 하이브리드 검색 → 컨텍스트 조립 → LLM 답변까지 한 번에 실행하는 CLI 스크립트)를 만들면서 "질문 → 검색 → 컨텍스트 조립 → LLM 답변 + 근거 인용"이라는 루프 자체는 이미 코드로 있다. 이번 노트에서 정리하고 싶은 건 그 루프 자체보다, "이 루프가 이상한 답을 냈을 때 어디서 틀렸는지 어떻게 구분하나"이다.

## 1. RAG 루프 네 단계

우리가 만든 `chat.py`의 `answer_question()`을 그대로 단계별로 풀면 이렇다.

```text
질문
 ↓
검색(Retrieval)         hybrid_search() — BM25 + 벡터를 RRF로 융합
 ↓
컨텍스트 조립(Context)   build_context() — 청크를 [1][2]로 번호 매겨 텍스트로 합침
 ↓
답변 생성(Generation)    chat() — 시스템 프롬프트로 "근거에 없으면 모른다고 하라" 강제
 ↓
답변 + 근거 인용
```

각 단계는 서로 다른 실패 방식을 갖고 있다. 검색이 엉뚱한 문서를 가져오면 그 뒤로 아무리 LLM이 똑똑해도 답이 맞을 수 없고, 검색이 맞는 문서를 가져왔어도 LLM이 잘못 읽으면 역시 틀린다.

## 2. "LLM이 멍청하다"고 바로 결론 내리면 안 되는 이유

RAG가 이상한 답을 냈을 때, 문제가 생길 수 있는 지점은 하나가 아니다.

```text
Question
 ↓
Retrieval        ← 여기서 실패할 수도 있음
 ↓
Context selection
 ↓
Generation       ← 여기서도 실패할 수도 있음
```

이걸 구분 안 하고 "답이 이상하니 LLM 문제"라고 넘어가면 엉뚱한 데를 고치게 된다. 사실 이건 이론으로만 안 게 아니라 이번 주에 직접 겪었다. `failed_questions.md`의 그 유명한 사례("AMD에 HBM4 공급하는 회사가 최근 공시에서 밝힌 클러스터는?")에서, 처음엔 "정답 문서를 못 찾았으니 검색 실패"라고 생각했었다. 근데 실제로 확인해보니 BM25는 그 문서를 20개 후보 중 1등으로 정확히 찾아냈고, 문제는 그 뒤 RRF 융합 단계에서 벡터 검색에 없다는 이유로 11위로 밀려난 것이었다. **검색은 성공했는데 융합 단계에서 버려진 것**과 "검색 자체가 실패한 것"은 원인도 다르고 고치는 방법도 다르다. 이 구분을 안 했으면 계속 엉뚱한 곳(임베딩 모델 교체 같은)을 고치려 들었을 것이다.

그래서 retrieval 단계만 따로 떼어서 평가하는 방법을 알아둘 필요가 있다.

## 3. Retrieval만 따로 평가하기: corpus / queries / qrels

BEIR([앞선 노트](03-beir-benchmark.md) 참고)가 정리해둔 구조를 그대로 가져오면 된다.

```text
Corpus  전체 검색 대상 문서
Queries 검색 질문
Qrels   각 query와 관련 있는 문서(정답)
```

예를 들면 이런 식이다.

```text
Query: "A사의 영업이익 감소 원인은?"

Relevant evidence (qrels)
D12: 실적발표 원가 상승 설명
D31: 사업보고서 환율 영향
D52: 공장 가동률 자료
```

이 구조는 사실 우리 실습에 이미 그대로 있다. `chunks.jsonl`이 corpus, `config/evaluation_queries.json`의 `query`가 queries, 그리고 그 안의 `relevant_chunk_ids`가 정확히 qrels다.

## 4. 지표 네 가지

이번 주에는 이 정도만 구분해서 봐도 충분하다.

| 지표 | 무엇을 재나 | 우리 구현 |
|---|---|---|
| Hit@k | top-k 안에 정답이 하나라도 있는가 | `search_common/evaluation.py`에 있음 |
| Recall@k | 전체 정답 중 top-k에서 몇 개나 찾았는가 | `search_common/evaluation.py`에 있음 |
| MRR | 첫 번째 정답이 얼마나 빨리(몇 등에) 나오는가 | 아직 없음 |
| nDCG@k | 더 중요한 정답이 위쪽에 배치됐는가 | 아직 없음 |

지금까지 우리가 봐온 결과 표(README의 grep/BM25/벡터/하이브리드 비교)는 전부 Hit@k와 Recall@k만 쓴 것이었다. MRR과 nDCG@k는 [BEIR 구현](https://github.com/beir-cellar/beir/wiki/Metrics-available)에서도 지원하는 지표인데, 우리 `search_common/evaluation.py`에는 아직 안 들어가 있다. 정답이 여러 개인 질문에서 "그중 어떤 게 더 위에 올라왔는지"까지 보려면 이 둘을 추가하는 게 자연스러운 다음 단계다.

## 5. 기업분석에서는 Recall@k를 먼저 보는 게 맞는 이유

어떤 질문은 근거가 하나가 아니라 여러 개를 요구한다. 예를 들어:

```text
A사의 최근 수익성 하락 원인은?

원재료 가격
환율
가동률
제품 믹스
```

이런 질문에 top-5 중 하나만 찾았다고 해서 좋은 retrieval이라고 보기는 어렵다. Hit@k는 "1개라도 찾았나"만 보기 때문에 이런 경우를 과대평가할 수 있고, Recall@k가 "몇 개나 찾았나"를 보여주므로 더 정직한 지표가 된다. 이건 [rag-vs-kg-summary.md](../labs/03-company-analysis-kg/rag-vs-kg-summary.md)에서 다룬 "개방형 집계 질문"과 같은 맥락이다 — 정답이 여러 문서에 흩어진 질문일수록 Recall@k로 봐야 진짜 실력이 보인다.

## 마치며

이번 노트로 "RAG 루프를 어떻게 만드는가"에 이어 "그 루프의 검색 단계를 어떻게 따로 검증하는가"까지 정리됐다. 다음 단계로 자연스러운 건 두 가지다. 하나는 `search_common/evaluation.py`에 MRR·nDCG@k를 추가해서 지금 있는 Recall@k 표를 더 촘촘하게 만드는 것. 다른 하나는 `failed_questions.md`에 이미 기록해둔 멀티홉 실패 사례들을 이 "retrieval 단계 vs generation 단계" 틀로 다시 분류해보는 것 — 어떤 실패는 검색이 원인이고 어떤 실패는 생성이 원인인지 구분해두면, W4에서 지식그래프로 무엇을 먼저 풀어야 하는지가 더 명확해질 것 같다.

## 참고 자료

- [BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models (arXiv)](https://arxiv.org/abs/2104.08663)
- [BEIR 평가 지표 목록 — GitHub Wiki](https://github.com/beir-cellar/beir/wiki/Metrics-available)
- [03-beir-benchmark.md](03-beir-benchmark.md) — corpus/queries/qrels 구조의 배경
- [failed_questions.md](../labs/03-company-analysis-kg/failed_questions.md) — retrieval 단계 실패와 generation 단계 실패가 섞여 있던 실제 사례
- [labs/03-company-analysis-kg/README.md](../labs/03-company-analysis-kg/README.md) — 지금까지의 Hit@5·Recall@5 실측 결과

---

**다음 노트**: [Single-hop에서 Multi-hop으로, 그리고 지식그래프로](03-multihop-to-kg.md)
