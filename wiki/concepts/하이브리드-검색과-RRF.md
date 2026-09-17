---
title: 하이브리드 검색과 RRF — 점수 대신 순위를 합친다
type: concept
tags: [concept]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [dldusgh318, e0ng, sese2204, lys0611, do-dop, ur2e, sunghyun]
weeks: [2, 3]
---

> BM25와 벡터 검색은 실패 지점이 다르므로 둘 다 돌리고 결과를 합친다. 점수는 척도가 달라(BM25 4.36 vs 코사인 0.579) 더할 수 없으니 **순위만** 쓰는 RRF `Σ 1/(k + rank)`, k=60이 세 멤버 모두의 기본값이다. dldusgh318의 실측에서 Hybrid가 평균 Recall은 가장 높았지만 코드 심볼 질의에서는 BM25 단독에 졌다.

## 왜 합치는가

| | 강점 | 약점 |
|---|---|---|
| BM25 (sparse) | 희귀어, 제품 코드, 함수명, 정확 용어 (`@Transactional`, `Write-Behind`, `SeCause`) | 패러프레이즈, 동의어 |
| Dense (벡터) | 의미 유사, 표현이 다른 자연어 질문 | 정확 토큰 매칭, OOD 도메인, `Write-Behind`에 `Write Around`를 올림 |

- BEIR가 "도메인 밖에서는 BM25가 여전히 강하다"는 걸 보인 것이 하이브리드의 근거다(sese2204; kdyann은 더 완화된 표현 → [[RAG-변천사]]).
- lys0611(카카오톡 1,922청크, 질문 10개)의 BM25 top-5와 벡터 top-5 교집합은 질문마다 0~2개뿐이었다. 두 검색기가 서로 다른 후보를 찾으므로 합칠 근거가 된다. `마감 일정`에서 BM25는 `일정`이 반복된 일반 청크를, 벡터는 마지막 제출일 대화를 1위로 냈다.

## 점수 정규화가 안 되는 이유 (e0ng, dldusgh318)

- Min-Max·Z-score·Softmax·L2 정규화는 **스케일**은 맞추지만 **분포와 의미**는 못 맞춘다. `[100, 99, 98]`과 `[100, 50, 0]`은 정규화하면 둘 다 `[1.0, 0.5, 0.0]`이 된다. `[100, 10, 9, 8]`은 극단값 하나 때문에 나머지가 `0.022, 0.011, 0.000`으로 뭉개진다 (e0ng).
- BM25는 쿼리마다 점수 범위가 다르다(희귀어 "온톨로지"는 높게, 흔한 "프로젝트"는 낮게). 0~1로 맞춰도 쿼리마다 기준이 달라지고 가중치 α를 따로 정해야 한다 (dldusgh318). α 튜닝은 코퍼스마다 달라 유지보수 부담이다 (sese2204). 세 멤버가 다른 논거로 같은 결론에 닿았다.
- 다른 결합법: 정규화 후 가중합, CombSUM, CombMNZ(등장한 검색 결과 수를 곱함), Borda Count. e0ng만 정리했다.

## RRF

```
RRF(d) = Σ_{검색기 m} 1 / (k + rank_m(d))       k = 60
```

- 각 검색기에서 순위만 뽑고 역수 점수를 더한다. 여러 검색기가 공통으로 올린 문서가 올라오기 쉬운 **투표**다. 상위권 순위 차이(1위 vs 2위 = 0.5점 차)가 하위권(100위 vs 101위 = 0.0099)보다 훨씬 크다 (e0ng).
- `k`는 순위 차이를 얼마나 크게 볼지 조절한다. k↓면 상위권 영향이 커지고 k↑면 넓은 범위를 비슷하게 본다 (e0ng). 60은 Elasticsearch RRF의 `rank_constant` 기본값이기도 하다 (dldusgh318). "처음엔 60으로 시작하면 충분" (dldusgh318) vs "튜닝 가능한 파라미터"(e0ng)로 온도차가 있지만 실제로 다른 k를 실험한 멤버는 없다.
- RRF 점수 자체를 신뢰도로 쓰면 안 된다. "RRF 점수가 높다 ≠ 이 문서가 90% 관련 있다" (dldusgh318). 점수를 버렸으니 1위가 압도적이었는지 알 수 없고, 한 검색기가 완전히 틀린 결과를 가져와도 점수를 받는다. 그래서 RRF 뒤에 [[리랭커]]가 온다.
- RRF의 두 번째 용도: 같은 검색기 × 변형 쿼리 3~5개를 합치는 RAG-Fusion (sese2204) → [[쿼리-재작성]].

## 멤버들이 확인한 것

- **dldusgh318** (Notion 1,562청크, 자연어 질문 10개 R01–R10, 사람이 판정한 Gold Set, BM25 top-50 + Vector top-50 → RRF k=60):

| 방식 | Recall@5 | Recall@10 |
|---|---|---|
| BM25 | 0.469 | 0.610 |
| Vector | 0.407 | 0.682 |
| **Hybrid** | **0.534** | **0.734** |

  단, R02 `@Transactional에서 같은 클래스 내부 호출이 문제가 되는 이유는?`(코드 심볼)는 BM25 Recall@5 1.000 vs Hybrid 0.500. BM25가 잘 찾은 청크가 벡터 후보와 융합되며 top-5 밖으로 밀렸다. "RRF의 목적은 모든 질문에서 최고를 보장하는 게 아니라 서로 다른 실패 패턴을 보완해 전체 안정성을 높이는 것."
- **sese2204** (카카오톡 11,985청크, pg_trgm + 벡터, 각 상위 2k를 RRF `1/(60+rank)`): `홍천 닭갈비` hybrid → 닭갈비집 얘기 두 개와 그 식당 지도 공유 청크가 1위. 수치 평가 없음. 다음 단계로 ES nori BM25를 붙여 RRF 3-way 예정.
- **lys0611** (카카오톡 1,922청크, KURE-v1, 후보 각 50개, k=60, ef_search=100, 사람이 라벨링한 27문항):

| 방식 | R@1 | R@3 | R@5 | R@10 | AllEvidence@5 | MRR@10 |
|---|---|---|---|---|---|---|
| BM25 (nori) | 0.648 | 0.796 | 0.833 | **0.926** | 0.815 | 0.773 |
| 벡터 (KURE-v1) | 0.685 | 0.778 | 0.815 | 0.870 | 0.778 | 0.778 |
| **RRF** | **0.759** | **0.907** | **0.907** | 0.907 | **0.889** | **0.864** |

  exact 12문항은 셋 다 R@5 1.0이고 차이는 semantic 12문항(0.667 / 0.667 / 0.833)과 다중 홉 3문항에서 났다. **R@10은 BM25가 RRF보다 높다.** RRF는 양쪽에 모두 등장한 후보를 올리고 한쪽만 확신한 후보를 내리므로(한 검색기 8위 = 1/68 ≈ 0.0147 < 양쪽 20위·25위 = 0.0243), 최종 3~5개만 쓰는 RAG에서는 좋은 교환이고 관련 대화를 전부 찾아야 하는 작업에서는 나쁜 교환이다. "돈 언제까지 보내야 해"는 7위·10위 → 2위로 올라왔고, "Lab8 변경의 구현 세부"는 BM25 8위 → RRF 11위로 밀렸다. 후보 50→10, k 60→10으로 바꿔도 Recall은 그대로, MRR만 0.864→0.858이라 27문항으로 k를 튜닝하는 건 과적합으로 보고 60을 유지했다. 원 논문(Cormack, Clarke & Büttcher 2009)도 k=60을 예비 실험에서 정하고 바꾸지 않았다.
- ur2e·sunghyun·do-dop은 "BM25와 벡터 결과를 어떻게 합칠까"를 열린 질문으로 남겼다. 이 페이지가 그 답이다.

## 한계

- RRF는 관련 문서를 더 잘 찾게 할 뿐 문서 사이의 **관계를 따라가는 문제**는 못 푼다. "존재하지 않는 두 번째 검색을 만들어주는 기술이 아니다" → [[멀티홉-질문과-Bridge-Entity]].
- 정확 용어 질의에서는 BM25 단독이 나을 수 있다. 질의 유형별로 재야 한다 → [[RAG-평가-지표]].

## 관련

- [[역색인과-BM25]] · [[임베딩과-벡터-검색]] · [[리랭커]] · [[쿼리-재작성]] · [[RAG-평가-지표]] · [[멀티홉-질문과-Bridge-Entity]] · [[RAG-변천사]]

## 출처

- dldusgh318 · 하이브리드 검색 — RRF — [members/dldusgh318/notes/week3/04-hybridSearch-rrf.md](../../members/dldusgh318/notes/week3/04-hybridSearch-rrf.md); 실습 — [labs/01-three-generations/WEEK3_hybrid_search_rrf.md](../../members/dldusgh318/labs/01-three-generations/WEEK3_hybrid_search_rrf.md)
- e0ng · RRF와 RAG 루프 (§점수 정규화, §RRF) — [members/e0ng/notes/03-rrf.md](../../members/e0ng/notes/03-rrf.md)
- sese2204 · 하이브리드 검색 (BM25 + 벡터) — [members/sese2204/notes/04-hybrid-search.md](../../members/sese2204/notes/04-hybrid-search.md); 실습 — [labs/02-kakao-chunk-embed/README.md](../../members/sese2204/labs/02-kakao-chunk-embed/README.md) (PR #6 미머지)
- lys0611 · 카톡 대화 적재 (§세 방식 비교) — [members/lys0611/labs/01-ingest/README.md](../../members/lys0611/labs/01-ingest/README.md) (PR #15 미머지); 하이브리드 검색과 RRF 노트 — [notes/04-hybrid-search-rrf-recall.md](../../members/lys0611/notes/04-hybrid-search-rrf-recall.md); 실습 — [labs/02-hybrid-rag-agent/README.md](../../members/lys0611/labs/02-hybrid-rag-agent/README.md), [results/retrieval-summary.md](../../members/lys0611/labs/02-hybrid-rag-agent/results/retrieval-summary.md) (PR #15 미머지)
- 외부: Cormack, Clarke & Büttcher, Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods (SIGIR 2009) http://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf · Elasticsearch Reciprocal rank fusion https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion · Thakur et al., BEIR (2021) https://arxiv.org/abs/2104.08663 · SPLADE, uniCOIL (learned sparse; sese2204 언급) · zg(zvec-grep) 하이브리드 사례 https://news.hada.io/topic?id=33183 (sese2204 readings)
