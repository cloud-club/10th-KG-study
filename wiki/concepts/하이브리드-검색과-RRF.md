---
title: 하이브리드 검색과 RRF — 점수 대신 순위를 합친다, 그런데 항상 이기지는 않는다
type: concept
tags: [concept]
status: maintained
created: 2026-09-16
updated: 2026-10-02
members: [dldusgh318, e0ng, sese2204, lys0611, do-dop, ur2e, sunghyun, heebindev, kdyann, Yeongeunn, jjinthung, yujeong430]
weeks: [2, 3]
---

> BM25와 벡터 검색은 실패 지점이 다르므로 둘 다 돌리고 결과를 합친다. 점수는 척도가 달라(BM25 4.36 vs 코사인 0.579) 더할 수 없으니 **순위만** 쓰는 RRF `Σ 1/(k + rank)`, k=60이 아홉 멤버의 기본값이다. 2026-10-02 기준 평가셋 열한 개가 모였고 결론은 하나로 수렴하지 않는다 — **RRF가 모든 k에서 최고인 곳은 e0ng의 10문항 하나뿐**이고, 나머지는 특정 k에서만 이기거나(dldusgh318, lys0611, kdyann R@5), 동률이거나(heebindev, sunghyun Q1–Q4·Q6), 진다(Yeongeunn 평균, **yujeong430 40문항 전부**, sunghyun Q5, lys0611 R@10, e0ng 36문항 R@3·R@5). 질문 수가 가장 많은 평가(yujeong430 40문항)에서 RRF가 졌다. 패배 메커니즘은 네 멤버에서 동일하게 관측됐다: **한쪽 검색기에서만 상위인 정답이 양쪽에 중간 순위로 나타난 문서에 밀린다.** 그리고 do-dop은 "정규화 융합은 안 된다"는 이 페이지의 옛 서술에 실측 반례를 냈다.

## 왜 합치는가

| | 강점 | 약점 |
|---|---|---|
| BM25 (sparse) | 희귀어, 제품 코드, 함수명, 정확 용어 (`@Transactional`, `Write-Behind`) | 패러프레이즈, 동의어. lexical gap — 질의 "수익성이 악화된 이유" vs 문서 "원재료 가격 상승으로 영업이익률이 감소" (do-dop) |
| Dense (벡터) | 의미 유사, 표현이 다른 자연어 질문 | 정확 토큰 매칭, OOD 도메인, 코드·스펙 형식 텍스트 (e0ng — `curl -X PUT` 위주 청크는 세 방식 전부 놓침) |

- BEIR가 "도메인 밖에서는 BM25가 여전히 강한 기준선"임을 보인 것이 하이브리드의 근거다 → [[BEIR]]. 검색의 zero-shot은 "검색 대상 데이터셋으로 추가 학습하지 않은 상태"이고 LLM 프롬프팅의 zero-shot과 결이 다르다 (do-dop).
- lys0611(카카오톡 1,922청크, 질문 10개)의 BM25 top-5와 벡터 top-5 교집합은 질문마다 0~2개뿐이었다. 두 검색기가 다른 후보를 찾으므로 합칠 근거가 된다.
- **BM25 vs 벡터의 우열 자체가 코퍼스와 질문 유형에 따라 뒤집힌다.** lys0611 R@10 BM25 0.926 > 벡터 0.870, dldusgh318 R@5 0.469 > 0.407, kdyann R@1 0.733 > 0.600, jjinthung Hit@5 45% ≫ 2.5%인 반면 heebindev 0.50 < 0.80, Yeongeunn 0.60 < 0.70, e0ng 10문항 0.575 < 0.675. e0ng은 36문항에서 단일·복합 키워드 질문을 섞자 r@1 0.345 vs 0.332로 **격차가 사라졌고** "예전엔 자연어 질문뿐이라 벡터가 유리했던 것으로 보인다"고 자기 결론을 약화시켰다 → [[검색의-세-세대]].

## 점수 정규화 — 왜 피하나, 그런데 한 멤버는 이겼다

- Min-Max·Z-score·Softmax·L2 정규화는 **스케일**은 맞추지만 **분포와 의미**는 못 맞춘다. `[100, 99, 98]`과 `[100, 50, 0]`은 정규화하면 둘 다 `[1.0, 0.5, 0.0]`이 된다 (e0ng). BM25는 쿼리마다 점수 범위가 다르고 가중치 α를 코퍼스마다 따로 정해야 한다 (dldusgh318, sese2204). "같은 범위로 맞춘 점수가 같은 관련도 **확신**을 뜻하지도 않는다" (kdyann). 다른 결합법: 가중합, CombSUM, CombMNZ, Borda Count (e0ng 정리; do-dop은 min-max + 가중합을 구현).
- **RRF가 잃는 것**: 원래 점수에서 1위와 2위가 얼마나 차이 났는지 (kdyann, yujeong430). `[A=100, B=99]`와 `[A=100, B=3]`이 똑같이 "1위, 2위"로 뭉개진다 (do-dop). 정규화 융합은 이 margin을 보존한다.
- 강도는 세 단계로 갈린다 — "안 된다"(e0ng·dldusgh318·sese2204) / "가능하되 까다롭다"(Yeongeunn: min-max는 가능하고 가중치로 영향력을 조절할 수 있지만 **기준이 후보 목록에 의존**한다 — 후보에 점수 100이 하나 끼면 나머지가 0.089·0.111로 압축되고, 최댓값=최솟값이면 분모 0) / "별도 검증 필요"(yujeong430). Yeongeunn은 RRF 상수를 `c`로 쓰고 "평가의 상위 k와 다르다, 60은 출발 설정"이라고 구분했다.

> ⚠️ Contradiction: **정규화 융합은 실제로 더 나쁜가.** 이 페이지의 2026-09-16 판은 "세 멤버가 다른 논거로 같은 결론(정규화는 안 된다)에 닿았다"고 썼다. do-dop은 min-max + 동일 가중(α=0.5) 융합을 구현해 **같은 10문항에서 RRF와 비교**했고, 뉴스룸 10건·57청크에서는 정규화가 R@5 100% vs RRF 96.7%로 이겼으며, 무관 문서 4건을 더한 69청크에서는 RRF 100% vs 정규화 96.7%로 뒤집혔다. 둘 다 q009 하나에서만 흔들린다. 57청크 역전 원인: BM25 20후보 중 압도적 1위(21.56점, 2위 16.41)인 정답이 벡터 후보에 없어 RRF에서 **11위**(0.0164 < 양쪽 중간권 0.026~0.0315)로 매장됐고, 정규화는 4위로 건졌다. 69청크 역전 원인: q009(정답 3개)에서 정규화는 한 문서에 점수가 쏠려 top-5를 그 문서로 채우며 정답 하나를 놓쳤다(R@5 0.667). 결론: **"어떤 방식이 이기는지가 코퍼스에 어떤 문서가 섞여 있는지에 따라 바뀐다"** — 미리 정할 수 없고 평가셋이 있으면 둘 다 돌려야 한다. 평가셋이 없으면 RRF 기본값. 출처: [do-dop 03-rrf](../../members/do-dop/notes/03-reciprocal-rank-fusion.md), [labs/03 README](../../members/do-dop/labs/03-company-analysis-kg/README.md).

## RRF

```
RRF(d) = Σ_{검색기 m} 1 / (k + rank_m(d))       k = 60
```

- 각 검색기에서 순위만 뽑고 역수 점수를 더한다. 여러 검색기가 공통으로 올린 문서가 올라오기 쉬운 **투표**다. 한쪽에만 나온 문서는 벌점이 아니라 그 항이 빠질 뿐이다 (do-dop, heebindev).
- `k`의 뜻을 멤버마다 다르게 설명한다 — "순위 차이를 얼마나 크게 볼지"(e0ng), "한 검색기가 결과를 지배하는 것을 방지하는 평활화"(heebindev), "커질수록 낮은 순위 문서의 영향력이 상대적으로 커진다"(do-dop). k=1이면 1위 0.500 / 2위 0.333 / 10위 0.091, k=60이면 0.0164 / 0.0161 / 0.0143. **60은 Elasticsearch `rank_constant` 기본값이고 수천~수만 건 후보용 값**이다 (do-dop). Elasticsearch RRF retriever의 파라미터 셋: `retrievers`(모두 동일 가중치), `rank_constant`, `rank_window_size`(각 검색기가 넘길 후보 수; 최종은 `size`로 재절단).
- **k를 실제로 바꿔 본 멤버 둘**: lys0611은 후보 50→10, k 60→10으로 바꿔도 Recall 불변·MRR 0.864→0.858이라 27문항으로 튜닝하는 건 과적합으로 보고 60을 유지했고(원 논문도 k=60을 예비 실험에서 정함), do-dop은 57~69청크에서 **k=1로 바꾸자 11위였던 정답이 top-5로 복귀**했다 — "현재 69개 청크에는 k=60이 과함". 모순이 아니라 **코퍼스 규모 의존**이다.
- RRF 점수 자체를 신뢰도로 쓰면 안 된다. 점수를 버렸으니 1위가 압도적이었는지 알 수 없고 한 검색기가 완전히 틀린 결과를 가져와도 점수를 받는다 (dldusgh318). 그래서 RRF 뒤에 [[리랭커]]가 온다.
- RRF의 다른 용도: 같은 검색기 × 변형 쿼리 3~5개를 합치는 RAG-Fusion (sese2204) → [[쿼리-재작성]]; 검색이 아닌 **랭킹 신호 두 개(좋아요·댓글)**를 합쳐 Instagram 참고 글 50개를 고르는 데 (kdyann).

## 멤버들이 확인한 것

조건이 제각각이라 절댓값은 비교할 수 없다 → [[RAG-평가-지표]]. 공통 설정: 후보 각 20~50개, k=60, 최종 top-5.

| 멤버 | 데이터 | 후보 | 평가셋 | 결과 | 판정 |
|---|---|---|---|---|---|
| dldusgh318 | Notion 1,562청크, bge-m3 | 50+50 | R01–R10, 사람 판정 Gold | R@5 BM25 0.469 / 벡터 0.407 / **Hybrid 0.534**, R@10 0.610 / 0.682 / **0.734**. 단 R02(코드 심볼) BM25 1.000 vs Hybrid 0.500 | 평균 승, 정확 용어에서 패 |
| lys0611 | 카카오톡 1,922청크, KURE-v1 | 50+50 | 27문항 사람 라벨, evidence group | R@1 0.648 / 0.685 / **0.759**, R@5 0.833 / 0.815 / **0.907**, **R@10 0.926** / 0.870 / 0.907, MRR@10 0.773 / 0.778 / **0.864**. exact 12문항은 셋 다 1.0 | R@1~5 승, R@10 패. "최종 3~5개만 쓰는 RAG에서는 좋은 교환, 관련 대화를 전부 찾는 작업에서는 나쁜 교환" |
| e0ng (03) | Notion 111청크, bge-m3, 제목+본문 결합 | 20+20 | ① 10문항 (LLM 생성 + 사람 확정) ② **36문항** (TREC pooling + LLM-as-a-Judge 0~3점) | ① r@1 0.575 / 0.675 / **0.775**, @3 이상 벡터·하이브리드 동률 ② r@1 0.345 / 0.332 / 0.357 **거의 동률**, r@3 0.594 / **0.681** / 0.673, r@5 0.727 / **0.787** / 0.757, **nDCG는 모든 k에서 하이브리드 최고**(@1 0.926, @5 0.879) | 같은 코퍼스·같은 검색기인데 **평가셋만 바꾸자 결론이 뒤집혔다.** "하이브리드는 recall보다 nDCG에서 강하다 — 많이 찾기보다 가장 좋은 근거를 위로 두기" |
| heebindev (02) | Notion 운영체제 454청크, e5-small | 20+20 | 5문항 골드셋 **초안**(미검토) | R@5 BM25 0.50 / 벡터 0.80 / 하이브리드 **0.80** | 동률, 이득 0. 교착상태 질의에서 BM25 1위 정답이 벡터 후보 20개에 없어 RRF 5위로 밀렸고 양쪽 5위였던 무관 청크가 RRF 1위 |
| kdyann (03) | Instagram 248문서, e5-small | 20+20 | 15문항, 검색 전 수동 지정 | R@1 **0.733** / 0.600 / 0.600, R@3 **0.889** / 0.667 / 0.800, R@5 0.889 / 0.667 / **0.956** | 상위 1·3은 BM25, 5에서만 역전. "하이브리드가 항상 더 좋다는 결과는 아니다" |
| sunghyun (03) | 회사 기술 문서 2,685청크, qwen3-embedding 1024d, BM25 **OR** | 20+20 | Q1~Q6, 원문 선독 후 고정 정답(비공개) | Q1~Q4 평균 R@5 0.625 / 0.750 / 0.750 (**이득 0**, Q4에서 BM25 5위 정답이 RRF 9위로). Q5(정답 4개) BM25 R@5 0.75·R@10 **1.00** vs RRF 0.50·0.75 — BM25 4위 정답이 벡터 후보 20개에 없어 **14위**. Q6 셋 다 동률 | 동률 또는 패 |
| Yeongeunn (04) | Notion 1,369청크, e5-small, 정확 검색 | **30+30** | 10문항(정확용어 3·다른표현 3·조건 2·다중홉 2), evidence group + corpus_sha256, **AI 보조 라벨 초안** | R@5 BM25 0.60 / 벡터 **0.70** / RRF **0.55**. q01(정확 용어) BM25 1.0 → RRF 0.0, q05 벡터 1.0 → RRF 0.0, q10(다중홉) 0.5 / 1.0 / 1.0 | **평균 꼴찌.** "c=60에서는 한 검색기의 높은 순위 하나보다 양쪽의 중간 순위가 더 유리할 수 있다." 결과를 보고 설정을 바꾸지 않았다 |
| do-dop (03) | 기업 뉴스룸·공시 69청크, bge-m3 | 20+20 | 10문항 qrels (keyword/semantic/multi_hop) | Hit@5 전부 100%, R@5 grep(핵심어) 83.3% / BM25 96.7% / 벡터 100% / **RRF 100%** / 정규화 96.7% | 승. 단 57청크에서는 정규화 승 (위 ⚠️) |
| yujeong430 (PR #19 미머지) | 카카오톡 공지방 814청크, e5-small, 날짜별 청킹 | 20+20 | **40문항** 손 라벨, 유형 6종, 2026-09-16 | R@1 **0.5875** / 0.45 / 0.575, R@3 **0.8875** / 0.8375 / 0.8625, R@5 **0.95** / 0.85 / 0.8875. 유형별 R@3: 정확 키워드 5문항 셋 다 100 / 형태 변형 6문항 91.7 / 91.7 / **100** / **의미 바꿔 말하기 13문항 88.5** / 76.9 / 80.8 / 시점 구분 7문항 셋 다 71.4 / 다중 근거 2문항 **75** / 50 / 50 | **전 지표 BM25 승**, RRF는 형태 변형에서만 1위. "공지의 핵심어가 질문에 많이 남아 있어 형태소 기반 키워드 검색이 강하게 작동한 것으로 해석" |
| sese2204 | 카카오톡 11,985청크, pg_trgm + 벡터 | 각 2k | 수치 평가 없음 | `홍천 닭갈비` hybrid → 관련 청크 3개가 1위 | 정성 |
| jjinthung | 카카오톡 | — | — | RRF top-5 + GPT 파이프라인을 **구현했으나 하이브리드 수치는 재지 않았다** | — |

- **공통 패배 메커니즘** (lys0611, heebindev, sunghyun, Yeongeunn, do-dop — 다섯 멤버 독립 관측): 한 검색기에서 1~5위인 정답이 **다른 검색기의 후보 N개 안에 없으면** `1/(60+rank)` 한 항만 받아, 양쪽에 20·25위로 나타난 문서(`2/(60+22)`)에 밀린다. lys0611의 계산: 한 검색기 8위 = 1/68 ≈ 0.0147 < 양쪽 20위·25위 = 0.0243.
- **정확 용어 질의에서 하이브리드가 손해**: dldusgh318 R02(`@Transactional`) BM25 1.000 → 0.500, Yeongeunn q01 1.0 → 0.0, sunghyun Q4 — 서로 다른 데이터·멤버에서 같은 패턴. "RRF의 목적은 모든 질문에서 최고를 보장하는 게 아니라 서로 다른 실패 패턴을 보완해 전체 안정성을 높이는 것" (dldusgh318) — 그런데 그 "전체 안정성"이 평균에서 드러나지 않는 코퍼스가 셋이다.
- **질문 표현이 승자를 바꾼다**: e0ng 사례 01/02 — 같은 정답 4개인데 추상적 자연어("USDC 파일은 어떻게 GLB가 되고")에서는 top-5 밖, 문서 어휘를 쓴 질문에서는 세 방식 모두 4/4. heebindev도 탐색용 질문과 골드셋 질문의 표현 차이로 결과가 달랐다.
- **후보 수와 Top-k는 역할이 다르다** (sunghyun). RRF는 두 후보 목록을 합쳐 최대 40개 고유 청크를 가질 수 있다. 순위 `None`은 "그 방식의 후보에 없다"이지 "원본에 없다"가 아니다.

## 한계 · 열린 질문

- RRF는 관련 문서를 더 잘 찾게 할 뿐 문서 사이의 **관계를 따라가는 문제**는 못 푼다. "존재하지 않는 두 번째 검색을 만들어주는 기술이 아니다" → [[멀티홉-질문과-Bridge-Entity]].
- **후보 수가 RRF 손익을 가르는 변수인가.** RRF가 이긴 dldusgh318·lys0611은 50+50, 꼴찌인 Yeongeunn은 30+30, 동률·패인 heebindev·sunghyun·kdyann은 20+20이다. 후보 풀이 작으면 "한쪽 후보에 아예 없는 문서"가 늘어 RRF가 더 쉽게 깎인다는 가설이 선다. **어느 멤버도 후보 수를 변수로 실험하지 않았다** (lys0611의 50→10 실험은 Recall 불변이었지만 27문항·k 동시 변경). 위키의 추론이다.
- "recall은 벡터가 높은데 nDCG는 하이브리드가 높다"(e0ng)는 [[리랭커]] 도입 판단과 직결된다 — RRF가 상위 품질을 올리는 역할이라면 리랭커와 역할이 겹친다.
- 정확 용어 질의는 BM25 단독이 나을 수 있다. 질의 유형별로 재야 한다 → [[RAG-평가-지표]].

## 관련

- [[역색인과-BM25]] · [[임베딩과-벡터-검색]] · [[리랭커]] · [[쿼리-재작성]] · [[RAG-평가-지표]] · [[멀티홉-질문과-Bridge-Entity]] · [[RAG-변천사]] · [[BEIR]] · [[검색의-세-세대]] · [[실습-비교표]]

## 출처

- dldusgh318 · 하이브리드 검색 — RRF — [members/dldusgh318/notes/week3/04-hybridSearch-rrf.md](../../members/dldusgh318/notes/week3/04-hybridSearch-rrf.md); 실습 — [labs/01-three-generations/WEEK3_hybrid_search_rrf.md](../../members/dldusgh318/labs/01-three-generations/WEEK3_hybrid_search_rrf.md)
- e0ng · RRF와 RAG 루프 (§점수 정규화, §RRF) — [members/e0ng/notes/03-rrf.md](../../members/e0ng/notes/03-rrf.md); 개인 데이터 검색 에이전트 (10·36문항) — [labs/03-personal-data-agent/README.md](../../members/e0ng/labs/03-personal-data-agent/README.md)
- sese2204 · 하이브리드 검색 (BM25 + 벡터) — [members/sese2204/notes/04-hybrid-search.md](../../members/sese2204/notes/04-hybrid-search.md); 실습 — [labs/02-kakao-chunk-embed/README.md](../../members/sese2204/labs/02-kakao-chunk-embed/README.md) (PR #6 미머지)
- lys0611 · 카톡 대화 적재 (§세 방식 비교) — [members/lys0611/labs/01-ingest/README.md](../../members/lys0611/labs/01-ingest/README.md); 하이브리드 검색과 RRF 노트 — [notes/04-hybrid-search-rrf-recall.md](../../members/lys0611/notes/04-hybrid-search-rrf-recall.md); 실습 — [labs/02-hybrid-rag-agent/README.md](../../members/lys0611/labs/02-hybrid-rag-agent/README.md), [results/retrieval-summary.md](../../members/lys0611/labs/02-hybrid-rag-agent/results/retrieval-summary.md)
- do-dop · RRF — 순위로 합치기 (정규화 융합 실측) — [members/do-dop/notes/03-reciprocal-rank-fusion.md](../../members/do-dop/notes/03-reciprocal-rank-fusion.md); BEIR 벤치마크 — [03-beir-benchmark.md](../../members/do-dop/notes/03-beir-benchmark.md); 기업 분석 실습 — [labs/03-company-analysis-kg/README.md](../../members/do-dop/labs/03-company-analysis-kg/README.md)
- heebindev · 하이브리드 검색과 RAG — [members/heebindev/notes/03-hybrid-search-and-rag.md](../../members/heebindev/notes/03-hybrid-search-and-rag.md); 실습 — [labs/02-hybrid-search-rag/README.md](../../members/heebindev/labs/02-hybrid-search-rag/README.md)
- kdyann · 하이브리드 검색과 RAG — [members/kdyann/notes/03-hybrid-search.md](../../members/kdyann/notes/03-hybrid-search.md); 실습 — [labs/03-hybrid-search/README.md](../../members/kdyann/labs/03-hybrid-search/README.md)
- sunghyun · 3주차 하이브리드 검색, RAG와 Recall 평가 — [members/sunghyun/notes/03-hybrid-rag-and-evaluation.md](../../members/sunghyun/notes/03-hybrid-rag-and-evaluation.md); 실습 — [labs/03-hybrid-rag/README.md](../../members/sunghyun/labs/03-hybrid-rag/README.md)
- Yeongeunn · 하이브리드 평가 실습 — [members/Yeongeunn/labs/04-hybrid-evaluation/README.md](../../members/Yeongeunn/labs/04-hybrid-evaluation/README.md); 실습 인덱스 — [labs/README.md](../../members/Yeongeunn/labs/README.md)
- yujeong430 · RRF, 하이브리드 검색, Recall@k 노트 — [members/yujeong430/notes/04-reciprocal-rank-fusion.md](../../members/yujeong430/notes/04-reciprocal-rank-fusion.md), [05-hybrid-search.md](../../members/yujeong430/notes/05-hybrid-search.md), [07-recall-at-k.md](../../members/yujeong430/notes/07-recall-at-k.md); 평가 결과 — [labs/01-kakaotalk-search/data/evaluation/README.md](../../members/yujeong430/labs/01-kakaotalk-search/data/evaluation/README.md) (전부 PR #19 미머지)
- Yeongeunn · 3주차 하이브리드 검색과 RAG 노트 (정규화·c 구분) — [members/Yeongeunn/notes/03-week3-hybrid-rag.md](../../members/Yeongeunn/notes/03-week3-hybrid-rag.md)
- jjinthung · BM25 + RRF + GPT 파이프라인 — [members/jjinthung/notes/02_BM25.md](../../members/jjinthung/notes/02_BM25.md), [labs/02-rag-hybrid/README.md](../../members/jjinthung/labs/02-rag-hybrid/README.md)
- 외부: Cormack, Clarke & Büttcher, Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods (SIGIR 2009) http://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf · Elasticsearch RRF https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion · RRF retriever https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/rrf-retriever · Linear retriever https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/linear-retriever · Weighted RRF (Elastic Search Labs) https://www.elastic.co/search-labs/blog/weighted-reciprocal-rank-fusion-rrf · OpenSearch normalization processor https://docs.opensearch.org/latest/search-plugins/search-pipelines/normalization-processor/ · Elastic, Hybrid retrieval https://www.elastic.co/search-labs/blog/improving-information-retrieval-elastic-stack-hybrid · Thakur et al., BEIR (2021) https://arxiv.org/abs/2104.08663 · zg(zvec-grep) 하이브리드 사례 https://news.hada.io/topic?id=33183 (sese2204 readings)
