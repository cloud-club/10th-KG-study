---
title: 하이브리드 검색과 RRF — 점수 대신 순위를 합치는 이유와 Recall@k로 확인한 것
date: 2026-09-16
tags: [hybrid-search, reciprocal-rank-fusion, bm25, dense-retrieval, recall-at-k, mrr, evaluation, pooling]
status: done
---

# 04. 하이브리드 검색과 RRF — 점수 대신 순위를 합치는 이유, Recall@k로 확인한 것

> 참고 자료:
> - Cormack, Clarke & Büttcher, [Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods](http://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf) (SIGIR 2009)
> - Elasticsearch, [Reciprocal rank fusion](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion) · [Ranking evaluation API](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/search-rank-eval)
> - pgvector, [README — Iterative index scans / Filtering](https://github.com/pgvector/pgvector)
> - 실습: [`labs/02-hybrid-rag-agent`](../labs/02-hybrid-rag-agent/README.md)

## 한 줄 요약

BM25 점수와 코사인 유사도는 척도가 달라 더할 수 없지만 **순위는 더할 수 있다.** RRF는 각 검색기에서의 순위 `r`에 `1/(k+r)`을 주고 합산하는 것이 전부인데, 내 카톡 1,922개 청크·27문항에서 Recall@1을 0.65~0.69에서 0.76으로, MRR@10을 0.77에서 0.86으로 올렸다. 대신 한쪽만 아는 정답을 아래로 밀어 Recall@10은 BM25보다 조금 낮았다.

## 핵심 개념

- **점수 융합의 문제**: BM25는 문서 길이·IDF에 따라 수십까지 올라가는 열린 척도, 코사인은 [-1, 1]. 질문마다 분포가 달라 min-max 정규화도 질문 단위로 흔들린다. 그래서 순위만 쓴다.
- **RRF**: `RRFscore(d) = Σ_r 1 / (k + r(d))`. 원 논문은 k=60을 “pilot investigation에서 고정했고 이후 검증에서 바꾸지 않았다”고 쓴다. k는 “어떤 한 시스템이 유독 높게 매긴 순위(outlier)의 영향을 완화”하는 상수다. Elasticsearch도 `rank_constant` 기본값 60, `rank_window_size`는 `size`가 기본이며 “값을 키우면 관련성은 올라가고 성능은 내려간다”고 설명한다.
- **왜 지수 함수가 아닌가**: 논문의 직관은 “상위 문서가 더 중요하지만 하위 문서의 중요도가 지수 함수처럼 사라져서는 안 된다”는 것. 1/(60+1)=0.0164와 1/(60+10)=0.0143의 차이는 작다. 즉 RRF는 **양쪽에 모두 등장하는 문서**에 보상을 준다.
- **Recall@k**: 관련 문서 중 top-k에 들어온 비율. Elasticsearch 문서의 정의대로 “R@10 = 0.5는 관련 8개 중 4개가 top-10에 있었다”는 뜻. 순서는 보지 않으므로 MRR(첫 정답 순위의 역수)을 같이 본다.
- **Pooling**: 정답 라벨을 매길 때 여러 시스템의 상위 결과를 합쳐 검토하는 TREC 방식. 풀에 없던 정답은 라벨되지 않으므로 절대 수치는 낙관적이고, 풀에 참여한 시스템 간 상대 비교에는 공평하다.

## 상세 정리

### RRF가 실제로 한 일

27문항에서 evidence group의 첫 등장 순위를 방식별로 보면 세 가지 패턴이 나왔다.

| 패턴 | 예 | BM25 / 벡터 → RRF |
|---|---|---|
| 양쪽 중간 → 융합 상위 | “돈 언제까지 보내야 해” | 7 / 10 → **2** |
| 한쪽 상위가 다른 쪽을 끌어올림 | “서버가 왜 안 켜져?” | 7 / 1 → **1** |
| 한쪽에만 있는 정답이 밀림 | Lab8 변경의 구현 세부(다중 홉 2번째 근거) | 8 / – → **11** |

세 번째가 RRF의 비용이다. 한 검색기에만 8위로 있던 문서는 `1/68 ≈ 0.0147`인데, 양쪽 20위·25위에 있는 문서는 `1/80 + 1/85 ≈ 0.0243`으로 그보다 높다. 그래서 RRF는 “동의하는 후보”를 위로 올리고 “한쪽만 확신하는 후보”를 내린다. 최종 k가 작을 때(RAG 컨텍스트 3~5개) 이 교환은 유리하고, 꼬리 재현율이 중요한 작업(모든 관련 대화 찾기)에서는 불리하다.

### 후보 수와 k의 민감도

- `candidate_k`를 50 → 10으로 줄여도 이 평가셋의 Recall@1/5/10은 그대로였고 MRR@10만 0.864 → 0.858로 움직였다. 정답 대부분이 각 검색기 10위 안에 있었기 때문이지, 일반 규칙은 아니다. 정답이 한쪽 6~10위에 있는 질문(위 표 첫 줄)은 candidate_k=5면 융합 기회조차 없다.
- `rank_constant` 10과 60도 Recall은 같고 MRR만 소폭 차이. 27문항 규모에서 이 차이를 해석하는 것은 과적합이다. 기본값 60을 고정 기준값으로 두고, 바꾸려면 더 큰 평가셋에서 별도 실험해야 한다.

### 점수가 아닌 순위를 쓸 때 잃는 것

BM25 1위가 31.1점이고 2위가 8.3점이면 1위는 압도적이다. RRF는 이 격차를 `1/61`과 `1/62`로 뭉갠다. 확신이 큰 검색기의 신호가 약해지는 대가로 정규화 없이 어떤 검색기든 붙일 수 있는 단순함을 얻는다. 점수 격차까지 쓰고 싶으면 정규화 기반 융합(CombSUM/CombMNZ)이나 학습 기반 재순위화로 가야 하는데, 원 논문은 TREC 데이터에서 RRF가 Condorcet Fuse·CombMNZ와 같거나 나았다고 보고한다.

### HNSW + 필터 + 정확 검색

- 필터(방·기간)는 근사 인덱스 스캔 **뒤에** 적용된다. pgvector 문서 예시대로 조건이 10% 행에 맞으면 `ef_search=40`일 때 평균 4행만 남는다. 0.8부터 `hnsw.iterative_scan = strict_order | relaxed_order`로 필요한 만큼 탐색을 이어갈 수 있고, `hnsw.max_scan_tuples`(기본 20,000)로 상한을 둔다. 실습은 `strict_order`를 트랜잭션 로컬로 설정했다.
- 근사 손실 측정: 같은 질문 벡터로 `enable_indexscan = off` 정확 검색을 한 번 더 돌려 top-10 겹침을 계산했다. 27문항 평균 1.000. 1,922개·1024차원·ef_search=100에서는 손실이 없고, 정확 검색도 p50 8 ms라 이 규모에서 HNSW는 필수가 아니다.

### 평가셋을 만들며 배운 것

- 질문 절반을 다시 썼다. “점심 메뉴 추천해 줘”처럼 정답 문서가 정의되지 않는 질문은 Recall을 계산할 수 없다. “점심으로 뭐 주문했어?”로 바꾸면 정답 청크가 하나로 정해진다.
- overlap 3건 청킹 때문에 같은 근거가 두 청크에 걸친다. 물리 청크가 아니라 **evidence group**(대체 가능한 hash 묶음)을 관련성 단위로 삼았다. 다중 홉은 group이 2개이고 `AllEvidence@k`(모든 group을 찾았는가)를 따로 낸다. 하나만 찾으면 Recall 0.5지만 답은 만들 수 없기 때문이다.
- 정답이 없는 질문(4개)은 분모가 0이라 Recall 평균에 넣지 않고 거절 성공률로 따로 평가한다. 집계 질문(3개)은 “관련 청크 전부”를 정의할 수 없어 제외했다.
- 라벨은 `content_hash`로 저장한다. 재청킹하면 `chunk_id`는 바뀌지만 본문이 같은 청크는 hash가 같다. 실행 전에 gold hash가 코퍼스에 있는지 확인해 조용히 0점이 되는 것을 막았다.

## 예시 / 코드

```python
def reciprocal_rank_fusion(rankings: dict[str, list[Hit]], k: int = 60) -> list[Fused]:
    score, ranks = {}, {}
    for source, hits in rankings.items():
        for rank, hit in enumerate(hits, start=1):          # 순위는 1부터
            score[hit.hash] = score.get(hit.hash, 0.0) + 1.0 / (k + rank)
            ranks.setdefault(hit.hash, {})[source] = rank
    # 동점: 점수 → 두 순위 중 최소 → hash 순으로 고정해야 실행마다 같은 순서가 나온다
    return sorted(score, key=lambda h: (-score[h], min(ranks[h].values()), h))
```

```sql
-- 방 필터가 붙은 HNSW 검색: 필터 후 LIMIT을 못 채우는 문제를 iterative scan으로 완화
SET LOCAL hnsw.ef_search = 100;
SET LOCAL hnsw.iterative_scan = strict_order;
SELECT c.id, 1 - (e.embedding <=> $1::vector) AS cosine
FROM chunk_embeddings e JOIN chunks c ON c.id = e.chunk_id JOIN rooms r ON r.id = c.room_id
WHERE e.model = 'nlpai-lab/KURE-v1' AND r.name = '팀리더'
ORDER BY e.embedding <=> $1::vector LIMIT 50;
```

## 궁금한 점 / 더 알아볼 것

- [ ] 각 검색기 결과에 가중치를 다르게 주는 weighted RRF(예: 벡터 순위에 0.7)를 붙이면 semantic 질문의 Recall@5가 오르는가, exact 질문이 떨어지는가. 27문항으로는 판단 불가 — 평가셋을 50개로 늘린 뒤.
- [ ] Elasticsearch에 dense_vector 필드를 추가해 내장 `rrf` retriever와 애플리케이션 RRF 결과가 같은지 확인하기. `rank_window_size`가 `candidate_k`에 대응한다.
- [ ] `relaxed_order`로 바꾸면 필터 질의의 recall·지연이 어떻게 변하는가 (이 규모에서는 차이가 없을 것으로 예상).

## 스터디에서 나눌 이야기

- RRF가 Recall@10에서 BM25에 진 것을 “실패”로 볼 것인가. RAG 컨텍스트 5개 기준으로는 RRF가 맞고, 감사(audit)처럼 전부 찾아야 하는 작업이면 BM25 후보를 따로 유지해야 한다.
- 평가셋 라벨링에 걸린 시간이 RRF 구현의 몇 배였다. “평가셋 설계 방법론” 분담과 연결해 라벨러 간 일치도를 어떻게 잴지 논의하고 싶다.
- 셋 다 놓친 2문항의 정답이 모두 표·목록 형태였다는 점. 검색기 튜닝으로 해결할 문제인지, W4처럼 구조 추출로 넘길 문제인지.
