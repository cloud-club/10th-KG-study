---
title: RAG 평가 지표 — 골든셋, Recall@k, 그리고 Answerability
type: resource
tags: [concept, comparison]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [sese2204, dldusgh318, lys0611, e0ng, ur2e, jjinthung, kdyann]
weeks: [2, 3]
---

> 모든 RAG 기법의 도입 여부는 측정으로 결정한다. 검색 단계는 골든셋 IR 지표(recall@k, MRR, NDCG)로, 생성 단계는 근거 충실도(RAGAS류, 인용 precision/recall)로 **따로** 잰다. 2026-09-16 기준 정답 라벨을 만들고 Recall@k를 계산한 멤버는 dldusgh318과 lys0611 둘이고, 평가셋은 멤버마다 제각각이라 공용 골든셋이 열린 과제다.

## 지표

| 층 | 지표 | 정의 | 누가 씀 |
|---|---|---|---|
| 검색 | Recall@k | 정답 청크(또는 evidence group) 중 top-k에 든 비율. 관련 8개 중 4개가 top-10 → R@10 = 0.5 | dldusgh318, lys0611 |
| 검색 | Hit@k | 정답이 top-k 안에 있으면 1, 아니면 0 | jjinthung(Hit@1/5), ur2e(Hit@3) |
| 검색 | MRR | 첫 정답 문서 순위의 역수 평균 (1위 1.0, 3위 0.33) | lys0611, ur2e |
| 검색 | Precision@k | top-k 중 관련 결과 비율 | e0ng(P@5), dldusgh318 TODO |
| 검색 | NDCG@k | 관련도 높은 문서를 전반적으로 상위에 잘 놓았는가 | sese2204 계획 |
| 검색 | AllEvidence@k | 다중 홉의 evidence group **전부**가 top-k에 있는가 (하나만 찾으면 Recall 0.5지만 답은 못 만듦) | lys0611 신설 |
| 생성 | faithfulness, answer relevance | 정답 레이블 없이 근거 충실도를 근사 (RAGAS 등 LLM-as-judge) | sese2204 계획 |
| 생성 | 인용 precision / recall | 붙인 인용이 실제로 지지하는가 / 사실 문장이 인용으로 지지되는가 (ALCE) | lys0611 |
| 생성 | 거절 성공률 | 답 없는 질문을 지어내지 않고 거절한 비율 | lys0611 |

- 골든셋 IR 지표와 RAGAS는 대체재가 아니라 다른 층을 재는 도구다. 검색 지표를 RAGAS로 대신하려 들면 노이즈만 는다 (sese2204). "골든셋 200개면 의사결정에 충분"(sese2204), 임베딩 모델도 자기 코퍼스의 MRR/NDCG로 고른다 → [[임베딩-모델-선택]].
- 실패를 검색 실패 vs 생성 실패로 반드시 분해한다 → [[RAG-실패-유형]]. 기법을 하나씩 **누적**해 붙이고 매번 **같은 골든셋**으로 잰다: ① baseline 고정 청킹 + dense → ② +하이브리드 RRF → ③ +리랭커 → ④ +쿼리 재작성 (sese2204 로드맵). [[리랭커]] 도입 판단에는 recall@100과 recall@5를 함께 재야 한다.

## 정답을 먼저 정해야 Recall을 잴 수 있다 (lys0611)

- 2주차의 10개 질문 비교표는 사람이 top-1만 보고 판정한 정성 평가라 Recall@k로 읽을 수 없었다. e0ng도 "정답셋이 없어 Recall@5는 측정하지 않았다."
- 라벨링은 TREC의 **pooling**: 세 방식의 후보 풀에서 사람이 관련 여부를 판정한다. 풀에 없던 정답은 라벨되지 않아 절대 수치는 낙관적이지만 세 방식이 같은 풀을 썼으니 상대 비교에는 공평하다.
- "점심 메뉴 추천해 줘"처럼 정답 문서가 정의되지 않는 질문은 Recall을 계산할 수 없다 → "점심으로 뭐 주문했어?"로 다시 썼다. 질문 절반을 다시 썼고, **라벨링에 걸린 시간이 RRF 구현의 몇 배**였다.
- 관련성 단위는 물리 청크가 아니라 대체 가능한 **evidence group**. overlap 청킹이 같은 근거를 두 청크에 걸치게 하기 때문 → [[청킹-전략]].
- 라벨은 `chunk_id`가 아니라 `content_hash`로 저장한다. 재청킹해도 hash는 같다. 실행 전 gold hash가 코퍼스에 있는지 확인해 라벨이 **조용히 0점**이 되는 걸 막는다.
- 평균만 보지 말고 유형별로 쪼갠다. 그래야 어느 방식이 어디서 지는지 안다 (ur2e, lys0611).
- **Recall ≠ Answerability** (dldusgh318): Gold ID를 놓쳐도 중복 기록된 다른 청크가 답을 줄 수 있고(A01), 반대로 인용은 붙었는데 근거가 지지하지 않을 수 있다. 검색 지표는 검색기 비교용이고 실제 RAG는 최종 Context에 정보가 있는지와 LLM이 그걸로 답했는지까지 봐야 한다.

## 멤버별 평가셋 현황

| 멤버 | 데이터 | 질문 수·유형 | 정답 라벨 | 지표 | 결과 |
|---|---|---|---|---|---|
| dldusgh318 | Notion 1,562청크 | R01–R10 10개 (exact-term, code-symbol, semantic ×3, spelling, typo …) | 사람 판정 Gold Set(qrels) | Recall@5/10 | Hybrid 0.534 / 0.734 → [[하이브리드-검색과-RRF]] |
| dldusgh318 | 같은 데이터 | 프로브 Q01–Q10 (고유명사·의미·띄어쓰기·오타) | 없음, "판정" 열 비어 있음 | 히트 건수·top-3 | 원시 관측 기록 |
| lys0611 | 카카오톡 1,922청크 | 34문항 (exact 12 / semantic 12 / hard 10), 검색 평가 27 | evidence group, content_hash, pooling | R@1/3/5/10, AllEvidence@k, MRR@10, 인용 P/R, 거절 성공률 | RRF R@5 0.907, 생성 정확도 0.583 |
| ur2e | 합성 옵시디언 vault | 19문항 (troubleshooting 5, recall-command 3, recall-decision 2, recall-meeting 2, concept 2, cross-document 2, exact-token 1, temporal 1, low-signal 1), `expected_primary`·`answer_points` | vault 상대 경로 | Hit@3, MRR | 청킹 설정별 BM25 0.84/0.82 ~ pgvector 0.68/0.53 (README는 in-progress) |
| jjinthung | 카카오톡 753청크 | 정답 40개 | 있음(방식 불명) | Hit@1, Hit@5, 시간 | grep 0/0%, BM25 30/45%, 벡터 2.5/2.5% |
| e0ng | 채팅 9,491건 | `수강 신청` 1개 | 없음 | Precision@5, 검색 시간(3회 중앙값) | grep 0.0, BM25 0.6, pgvector 1.0 |
| do-dop | 카카오톡 1,203건 | 11개 + 자연어 2개 (exact/common/phrase/partial/semantic) | 없음 | 히트 건수·1위 유사도 | 표 → [[검색의-세-세대]] |
| kdyann | Instagram 13개 | 3개 | 없음 | 히트 건수(`--limit 3` 상한) | 표 → [[검색의-세-세대]] |
| heebindev | Notion 454청크 | 3~4개 | 없음 | 히트 건수·점수 | 정성 |

- 지표가 제각각(없음 / 건수 / P@5 / Hit@3·MRR / Recall@k)이라 멤버 간 수치를 직접 비교할 수 없다. 데이터도 다르다.
- **지연 측정** (질문당 p50): lys0611 BM25 5.5ms · 임베딩 26.4ms · pgvector 8.1ms · RRF 0.1ms · 합계 40.1ms. e0ng BM25 116.8ms(내부 2ms) · pgvector 204.4ms(임베딩 32.4 + DB 1.9). 벡터 검색 지연은 질의 임베딩이 지배한다. sese2204는 각 단계의 p50/p99 기록을 로드맵에 넣었다.

## 열린 질문

- 공용 골든셋을 만들 것인가 (sese2204 스터디 질문). 데이터가 멤버마다 다르므로 공용은 질문 **유형**과 라벨링 **절차**(pooling, evidence group, content_hash) 수준에서만 가능해 보인다.
- 정답 라벨을 두 사람이 따로 붙였을 때 일치도 (lys0611 TODO). 평가셋 50문항 확대.
- 인용 precision/recall을 NLI 판정 모델로 근사했을 때 사람 판정과 얼마나 일치하는가 (lys0611 TODO).

## 관련

- [[RAG-실패-유형]] · [[하이브리드-검색과-RRF]] · [[리랭커]] · [[임베딩-모델-선택]] · [[청킹-전략]] · [[검색의-세-세대]] · [[RAG-루프와-근거-인용]]

## 출처

- sese2204 · RAG 평가와 실습 로드맵 — [members/sese2204/notes/07-rag-evaluation.md](../../members/sese2204/notes/07-rag-evaluation.md)
- dldusgh318 · 하이브리드 검색 — RRF (§Recall@k), 실습 §2, RAG Agent §11 — [members/dldusgh318/notes/week3/04-hybridSearch-rrf.md](../../members/dldusgh318/notes/week3/04-hybridSearch-rrf.md), [labs/01-three-generations/WEEK3_hybrid_search_rrf.md](../../members/dldusgh318/labs/01-three-generations/WEEK3_hybrid_search_rrf.md), [WEEK3_rag_agent.md](../../members/dldusgh318/labs/01-three-generations/WEEK3_rag_agent.md), [results/compare.md](../../members/dldusgh318/labs/01-three-generations/results/compare.md)
- lys0611 · 하이브리드 검색과 RRF (§정답을 먼저 정해야), 실습 결과 — [members/lys0611/notes/04-hybrid-search-rrf-recall.md](../../members/lys0611/notes/04-hybrid-search-rrf-recall.md), [labs/02-hybrid-rag-agent/README.md](../../members/lys0611/labs/02-hybrid-rag-agent/README.md), [results/retrieval-summary.md](../../members/lys0611/labs/02-hybrid-rag-agent/results/retrieval-summary.md) (PR #15 미머지)
- e0ng · RRF와 RAG 루프 (§Recall@K, 다른 지표), 실습 결과 — [members/e0ng/notes/03-rrf.md](../../members/e0ng/notes/03-rrf.md), [labs/02-search-generations/README.md](../../members/e0ng/labs/02-search-generations/README.md)
- ur2e · 검색 방식 비교 실험, 데이터셋 설계 — [members/ur2e/notes/01-search-methods-comparison.md](../../members/ur2e/notes/01-search-methods-comparison.md), [labs/01-worklog-search/dataset/README.md](../../members/ur2e/labs/01-worklog-search/dataset/README.md) (PR #11 미머지)
- jjinthung · 결과 — [members/jjinthung/notes/01_results.md](../../members/jjinthung/notes/01_results.md)
- kdyann · RAG 기술 변천사 (§궁금한 점) — [members/kdyann/notes/01-rag-history.md](../../members/kdyann/notes/01-rag-history.md)
- 외부: Elasticsearch Ranking evaluation API https://www.elastic.co/docs/reference/elasticsearch/rest-apis/search-rank-eval · Gao et al., ALCE (2023) https://aclanthology.org/2023.emnlp-main.398/ · RAGAS
