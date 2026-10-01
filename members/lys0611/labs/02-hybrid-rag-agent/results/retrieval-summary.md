# W3 검색 평가 결과

> 코퍼스 1,922개 청크 · 평가 가능 질문 27개 · candidate_k=50 · RRF c=60

`Evidence Recall@k`의 관련성 단위는 물리 청크가 아니라 대체 가능한 overlap 청크를 묶은 evidence group이다.

| 방식 | evidence_recall@1 | evidence_recall@3 | evidence_recall@5 | evidence_recall@10 | all_evidence@1 | all_evidence@3 | all_evidence@5 | all_evidence@10 | mrr@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bm25 | 0.648 | 0.796 | 0.833 | 0.926 | 0.593 | 0.778 | 0.815 | 0.926 | 0.773 |
| vector | 0.685 | 0.778 | 0.815 | 0.870 | 0.630 | 0.741 | 0.778 | 0.852 | 0.778 |
| rrf | 0.759 | 0.907 | 0.907 | 0.907 | 0.704 | 0.889 | 0.889 | 0.889 | 0.864 |

## 유형별 Evidence Recall@5 (평가 질문 수)

| 유형 | n | BM25 | 벡터 | RRF |
|---|---:|---:|---:|---:|
| exact | 12 | 1.000 | 1.000 | 1.000 |
| hard | 3 | 0.833 | 0.667 | 0.833 |
| semantic | 12 | 0.667 | 0.667 | 0.833 |

## 지연 시간 (ms, 질문당)

| 단계 | p50 | 평균 |
|---|---:|---:|
| bm25 | 5.5 | 6.0 |
| embedding | 26.4 | 45.3 |
| vector | 8.1 | 8.2 |
| rrf | 0.1 | 0.1 |
| total | 40.1 | 59.6 |

## HNSW 근사 손실

HNSW top-10과 정확 검색(`enable_indexscan=off`) top-10의 겹침 비율 평균: **1.000** (ef_search=100, iterative_scan=strict_order)

## 해석할 때 주의할 점

- 답이 없는 질문과 완전한 qrels를 만들기 어려운 집계 질문은 Recall 평균에서 제외했다.
- 이 결과는 개인 카톡의 작은 수동 평가셋에 대한 기술 통계이며 일반 성능을 뜻하지 않는다.
- 원문·질문별 검색 결과·content hash는 비공개 JSON에만 저장한다.
