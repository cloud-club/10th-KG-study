---
title: 하이브리드 검색과 RRF — 순위를 합치면 무엇이 좋아지고 무엇을 잃는가
date: 2026-09-16
tags: [hybrid-search, reciprocal-rank-fusion, bm25, dense-retrieval, recall-at-k, mrr, evaluation, pooling]
status: done
---

# 04. 하이브리드 검색과 RRF — 순위를 합치면 무엇이 좋아지고 무엇을 잃는가

2주차에 같은 질문을 BM25와 벡터로 던졌을 때 상위 5개의 교집합은 0~2개였다. 둘이 서로 다른 것을 찾아온다면 합치면 좋아질 것 같은데, 문제는 BM25 점수(7.12, 31.1 같은 열린 척도)와 코사인 유사도(0.59 같은 -1~1 값)를 어떻게 한 줄에 세우느냐였다. 이번 주에 한 일은 그 둘을 점수가 아니라 순위로 합치고, 정답을 미리 정해 둔 질문 27개로 실제로 좋아졌는지 재 보는 것이었다.

## 점수는 못 더하고 순위는 더할 수 있다

BM25 점수는 문서 길이와 IDF에 따라 질문마다 분포가 다르다. 코사인도 모델마다 다르다. 질문 단위로 min-max 정규화를 해도 상위 한두 개가 유독 높은 질문과 고르게 낮은 질문이 같은 0~1로 눌리는 문제가 남는다.

RRF(Reciprocal Rank Fusion)는 이 문제를 순위만 써서 피한다. 문서 d가 검색기 r에서 받은 순위를 r(d)라 하면 점수는 다음과 같다.

```text
RRFscore(d) = Σ_r  1 / (k + r(d))
```

원 논문(Cormack, Clarke, Büttcher 2009)은 k=60을 “예비 실험에서 정하고 이후 검증에서 바꾸지 않았다”고 쓴다. k가 하는 일은 어느 한 검색기가 유독 높게 매긴 순위의 영향을 눌러 주는 것이다. Elasticsearch의 `rrf` retriever도 `rank_constant` 기본값이 60이고, 각 검색기에서 몇 개를 가져와 합칠지는 `rank_window_size`로 정한다. 이 값은 `size`가 기본이며 키우면 관련성은 올라가고 성능은 내려간다고 문서에 적혀 있다.

식이 지수 함수가 아니라 1/(k+r)인 이유도 논문에 있다. 상위 문서가 더 중요하긴 하지만 하위 문서의 중요도가 급격히 사라지면 안 된다는 것이다. 1/61과 1/70의 차이는 작다. 그래서 RRF는 “한쪽에서 1위”보다 “양쪽에 모두 등장”에 보상을 준다. 이 성질이 뒤에 나오는 결과를 거의 다 설명한다.

임베딩이 pgvector에만 있어서 Elasticsearch 내장 RRF는 쓸 수 없었다. 대신 두 저장소가 같은 `chunk_id`와 `content_hash`를 공유하므로, 각각 상위 50개를 받아 파이썬에서 합쳤다. 동점은 점수, 두 순위 중 작은 값, hash 순으로 고정했다. 같은 질문에 항상 같은 순서가 나와야 평가를 다시 돌릴 수 있다.

## 정답을 먼저 정해야 Recall을 잴 수 있다

2주차 비교표는 “누가 이겼나”를 사람이 top-1만 보고 판정한 것이라 Recall@k로 읽을 수 없었다. 이번에는 질문마다 답을 지지하는 청크를 먼저 정했다.

방법은 TREC의 pooling과 같다. BM25 상위 50개와 벡터 상위 50개를 합친 후보 풀을 읽고, 원문 주변 메시지와 grep으로 실제 답을 확인한 뒤 답을 직접 지지하는 청크만 정답으로 뒀다. 풀에 없던 정답은 라벨되지 않으니 절대 수치는 낙관적이지만, 세 방식이 같은 풀을 썼으므로 상대 비교에는 공평하다.

라벨을 붙이다 보니 질문 절반을 다시 썼다. “점심 메뉴 추천해 줘”처럼 정답 문서가 정의되지 않는 질문은 Recall을 계산할 수 없다. “점심으로 뭐 주문했어?”로 바꾸면 정답 청크가 하나로 정해진다. 청킹이 앞뒤 3건씩 겹치기 때문에 같은 근거가 두 청크에 걸치는 경우도 많았다. 물리 청크가 아니라 대체 가능한 청크 묶음(evidence group)을 관련성 단위로 삼았고, 근거가 두 개 필요한 다중 홉 질문은 group이 둘이다. 하나만 찾으면 Recall은 0.5지만 답은 만들 수 없으므로 모든 group을 찾았는지(AllEvidence@k)를 따로 셌다.

Recall@k 정의는 Elasticsearch의 rank evaluation 문서를 따랐다. 관련 문서 8개 중 4개가 top-10에 있으면 R@10 = 0.5다. 순서를 보지 않으므로 첫 정답 순위의 역수인 MRR을 같이 봤다. 답이 없는 질문 4개는 분모가 0이라 평균에서 뺐고, “가장 많이 보낸 사람은?” 같은 집계 질문 3개는 관련 청크 전부를 정의할 수 없어 뺐다. 그래서 34문항 중 27문항이다.

라벨은 `content_hash`로 저장했다. 재청킹하면 `chunk_id`는 바뀌지만 본문이 같으면 hash는 같다. 실행 전에 정답 hash가 코퍼스에 있는지 확인해서 라벨이 조용히 0점이 되는 일을 막았다.

## 27문항에서 나온 결과

1,922개 청크, 후보 50개씩, k=60, HNSW `ef_search=100`이다.

| 방식 | R@1 | R@3 | R@5 | R@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| BM25 (nori) | 0.648 | 0.796 | 0.833 | 0.926 | 0.773 |
| 벡터 (KURE-v1) | 0.685 | 0.778 | 0.815 | 0.870 | 0.778 |
| RRF | 0.759 | 0.907 | 0.907 | 0.907 | 0.864 |

정확한 문구가 들어 있는 exact 12문항은 셋 다 R@5가 1.0이었다. 차이는 전부 표현이 다른 semantic 12문항(R@5 0.667 / 0.667 / 0.833)과 다중 홉 3문항에서 났다.

질문별로 정답의 첫 등장 순위를 보면 세 패턴이 있었다.

| 패턴 | 질문 | BM25 / 벡터 → RRF |
|---|---|---|
| 양쪽 중간이 합쳐져 상위로 | 돈 언제까지 보내야 해 | 7 / 10 → 2 |
| 한쪽 1위가 다른 쪽을 끌어올림 | 서버가 왜 안 켜져? | 7 / 1 → 1 |
| 한쪽에만 있던 정답이 밀림 | Lab8 변경의 구현 세부(2번째 근거) | 8 / – → 11 |

세 번째가 RRF의 비용이고, R@10에서 BM25(0.926)가 RRF(0.907)보다 높은 이유다. 한 검색기에만 8위로 있던 문서는 1/68 ≈ 0.0147인데, 양쪽 20위와 25위에 있는 문서는 1/80 + 1/85 ≈ 0.0243으로 그보다 높다. RRF는 둘이 동의하는 후보를 올리고 한쪽만 확신하는 후보를 내린다. RAG처럼 최종 3~5개만 쓰는 자리에서는 좋은 교환이고, 관련 대화를 전부 찾아야 하는 작업에서는 나쁜 교환이다.

후보를 50개에서 10개로 줄여도, k를 60에서 10으로 바꿔도 이 평가셋의 Recall은 그대로였고 MRR만 0.864에서 0.858로 움직였다. 정답이 대부분 각 검색기 10위 안에 있었기 때문이지 일반 규칙은 아니다. 첫 줄 질문처럼 한쪽 7위·10위에 있는 정답은 후보를 5개만 가져오면 합쳐질 기회가 없다. 27문항으로 k를 튜닝하는 것은 과적합이라고 판단해 60을 그대로 뒀다.

셋 다 놓친 semantic 2문항(RRF 39위, 65위)은 정답이 `IAM - A / VPC, LB, DNS - B` 같은 표 한 줄이거나 번호 매긴 지시 목록이었다. 질문의 자연어와 답의 구조화된 형태 사이를 형태소도 임베딩도 잇지 못했다. 검색기를 더 조정할 일이 아니라 “누가 무엇을 맡았다”를 관계로 뽑아야 하는 문제로 보인다.

## HNSW와 방 필터

방이나 기간 필터가 붙은 벡터 검색은 필터가 인덱스 스캔 뒤에 적용된다. pgvector 문서의 예시대로 조건이 10% 행에만 맞으면 기본 `ef_search=40`에서 평균 4행만 남아 `LIMIT 10`을 못 채운다. 0.8.0부터 `hnsw.iterative_scan`을 `strict_order`나 `relaxed_order`로 두면 필요한 만큼 탐색을 이어가고, `hnsw.max_scan_tuples`(기본 20,000)가 상한이다. 실습에서는 트랜잭션 안에서 `strict_order`를 설정했다.

근사 손실은 같은 질문 벡터로 `enable_indexscan = off` 정확 검색을 한 번 더 돌려 top-10 겹침을 재는 방식으로 봤다. 27문항 평균 1.000이었다. 1,922개·1024차원·`ef_search=100`에서는 손실이 없었고 정확 검색도 p50 8ms라, 2주차 노트에 쓴 대로 이 규모에서 HNSW는 성능 장치가 아니라 다음 단계 실험용이다.

```sql
SET LOCAL hnsw.ef_search = 100;
SET LOCAL hnsw.iterative_scan = strict_order;
SELECT c.id, 1 - (e.embedding <=> $1::vector) AS cosine
FROM chunk_embeddings e
JOIN chunks c ON c.id = e.chunk_id
JOIN rooms r ON r.id = c.room_id
WHERE e.model = 'nlpai-lab/KURE-v1' AND r.name = '팀리더'
ORDER BY e.embedding <=> $1::vector
LIMIT 50;
```

## 다음에 확인할 것

- 벡터 순위에 가중치를 다르게 주는 weighted RRF가 semantic 질문의 R@5를 올리는지, 그때 exact 질문이 떨어지는지. 평가셋을 50문항으로 늘린 뒤에 본다.
- Elasticsearch에 dense_vector 필드를 넣어 내장 `rrf` retriever 결과와 파이썬 RRF 결과가 같은지 확인한다. `rank_window_size`가 후보 수에 대응한다.
- `relaxed_order`로 바꿨을 때 필터 질의의 recall과 지연이 달라지는지. 이 규모에서는 차이가 없을 것으로 본다.
- 정답 라벨을 두 사람이 따로 붙였을 때 얼마나 일치하는지 기록한다. 라벨링에 걸린 시간이 RRF 구현의 몇 배였다.

## 확인한 자료

- Cormack, Clarke & Büttcher, [Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods](http://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf) (SIGIR 2009)
- Elastic, [Reciprocal rank fusion](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion) · [Ranking evaluation API](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/search-rank-eval)
- pgvector, [README — Iterative index scans / Filtering](https://github.com/pgvector/pgvector)
- 실습 기록: [`labs/02-hybrid-rag-agent`](../labs/02-hybrid-rag-agent/README.md)
