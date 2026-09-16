---
title: HNSW와 pgvector 인덱스 — 속도와 recall의 교환
type: resource
tags: [concept, pitfall]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [yujeong430, dldusgh318, do-dop, kdyann, heebindev, sese2204, lys0611]
weeks: [2]
---

> 벡터를 노드로, 가까운 벡터 사이를 간선으로 잇는 여러 층의 그래프. 위층의 성긴 그래프에서 멀리 이동하고 아래층의 촘촘한 그래프에서 정밀 탐색해 전수 비교보다 훨씬 적은 후보만 본다. 근사 검색(ANN)이라 **속도를 얻는 대신 recall 일부를 포기**한다. pgvector는 기본이 정확 검색이고 HNSW 인덱스를 만들어야 ANN이 되는데, 만들어도 플래너가 안 탈 수 있다.

## 정의

- 정확 검색(exact k-NN)은 질문과 모든 벡터를 비교한다. 정확하지만 데이터가 많으면 느리다. ANN(HNSW, IVFFlat, Annoy 등)은 가까울 가능성이 높은 후보만 탐색한다. 품질은 recall로 잰다 (yujeong430, kdyann, e0ng, heebindev).
- HNSW는 "지하철 급행"(dldusgh318): 상위 층에서 빠르게 멀리 → 하위 층에서 후보를 좁힘 → 가까운 벡터 탐색. 원 논문은 Malkov & Yashunin (2016).
- **pgvector는 기본적으로 정확 최근접 검색을 수행**하고, HNSW 인덱스를 추가하면 속도와 recall을 맞바꾸는 ANN이 된다 (yujeong430, kdyann). `CREATE INDEX … USING hnsw (embedding vector_cosine_ops)`.
- 파라미터 (yujeong430이 유일하게 정의): `m`(층당 최대 연결 수)과 `ef_construction`(생성 중 후보 목록 크기)을 키우면 recall은 좋아지지만 생성 시간·삽입 속도·메모리가 는다. 검색 시 `hnsw.ef_search`가 recall과 지연의 균형을 조절한다. dldusgh318은 `ef_search` 변경 실험을 TODO로 남겼다.
- pgvector 기본값 `m=16`, `ef_construction=64`, `hnsw.ef_search=40`. HNSW 색인 가능 차원은 `vector` 2,000, `halfvec` 4,000까지 (lys0611, 공식 문서 기준). 학습 단계가 없어 빈 테이블에도 만들 수 있지만 데이터를 넣고 만드는 편이 빌드가 빠르다.
- 거리 연산자와 인덱스 opclass를 맞춰야 한다: `<=>` 코사인 ↔ `vector_cosine_ops`, `<->` L2 ↔ `vector_l2_ops`, `<#>` 음의 내적 ↔ `vector_ip_ops`. L2 정규화해 저장하면 코사인 = 내적이다 (lys0611).

## 멤버들이 확인한 것

- **작은 테이블에서는 플래너가 HNSW를 안 탄다** (sese2204, 11,985청크): 순차 스캔 74ms vs HNSW Index Scan 1.8ms인데도 플래너는 순차 스캔을 골랐다. `EXPLAIN ANALYZE`로 확인하고 **질의 단위로 `SET LOCAL enable_seqscan = off`**를 거는 것이 pgvector 문서가 권하는 방법. yujeong430의 검색 스크립트는 `--explain`으로 실행 계획을 함께 출력한다. kdyann의 문서 13개 실습은 실행 계획 확인 언급이 없어 인덱스를 탔는지 불명.
- **인덱스가 있으면 대량 적재가 느려진다** (sese2204): HNSW가 이미 있는 상태에서 COPY하니 66초 → 86초. 대량 재적재면 인덱스를 지웠다 만든다.
- **HNSW가 놓친 걸까, 임베딩이 틀린 걸까** (dldusgh318): `Write-Behind → Write Around` 오답이 ANN의 recall 손실인지 임베딩 자체의 문제인지 구분하려면 `SET enable_indexscan = off`(Exact)와 `on`(HNSW)의 결과를 비교해 `recall@10`을 재면 된다. 아직 수행하지 않아 단정하지 않았다.
- **이 규모에서 HNSW는 성능 장치가 아니다** (lys0611, 1,922청크): 정확 검색도 p50 8ms로 충분히 작다. HNSW는 recall/속도 교환을 확인하려고 넣은 것. `ef_search=100`에서 HNSW top-10과 `enable_indexscan=off` 정확 검색 top-10의 겹침이 27문항 평균 **1.000**. top-5 쿼리는 1.6~1.9ms(1회 측정, 일반 수치 아님).
- **필터와 ANN의 조합** (lys0611): `WHERE room_id = …` 필터는 보통 인덱스 스캔 뒤에 적용되므로 `ef_search=40` 후보 중 그 방 청크가 적으면 `LIMIT 10`인데 10건을 못 받는다(조건이 10% 행이면 평균 4행). pgvector 0.8.0의 `SET LOCAL hnsw.iterative_scan = strict_order`(또는 `relaxed_order`)로 해결. `hnsw.max_scan_tuples` 기본 20,000. 필터가 잦으면 `ef_search`만 키우기보다 필터 컬럼 인덱스·부분 HNSW·파티셔닝을 검토한다.
- 저장 비용: 1,024차원 벡터를 모든 청크에 저장해 원본의 23배(22MB)가 됐다 (dldusgh318). 차원 수는 저장·검색 비용에 직결된다 → [[임베딩-모델-선택]].
- 실습에서 쓴 구성: sese2204 `vector(768)` L2 정규화 + HNSW, do-dop·e0ng `vector(1024)` + HNSW, kdyann·heebindev `vector(384)` + HNSW(코사인), lys0611 `vector(1024)` + HNSW cosine. 전원이 HNSW를 골랐고 IVFFlat을 쓴 멤버는 없다.

## 함정

- pgvector 0.8(공용 인프라), 0.8.6(lys0611, Postgres 18). Postgres 18 이미지는 볼륨을 `/var/lib/postgresql`에 마운트해야 데이터가 유지된다(`…/data`는 옛 경로) (lys0611).
- 정확 검색과 ANN 결과가 다를 수 있으니 "벡터 검색이 틀렸다"고 판단하기 전에 어느 경로로 실행됐는지 본다.
- 나머지 PostgreSQL 함정(pg_trgm 로케일, word_similarity 등)은 [[PostgreSQL과-pgvector-함정]].

## 관련

- [[임베딩과-벡터-검색]] · [[PostgreSQL과-pgvector-함정]] · [[임베딩-모델-선택]] · [[저장-구조-LSM과-B-tree]] · [[로컬-인프라]]

## 출처

- yujeong430 · 2세대 검색 (§정확 검색과 ANN, §HNSW) — [members/yujeong430/notes/03-vector-search-hnsw.md](../../members/yujeong430/notes/03-vector-search-hnsw.md); 실습 `--explain` — [labs/01-kakaotalk-search/README.md](../../members/yujeong430/labs/01-kakaotalk-search/README.md)
- dldusgh318 · 2세대 — 임베딩과 벡터 검색 (§3, §5) — [members/dldusgh318/notes/week2/03-embedding-vector-search.md](../../members/dldusgh318/notes/week2/03-embedding-vector-search.md)
- sese2204 · 대화 청킹 → 로컬 임베딩 → 하이브리드 검색 (§검색, §배운 점) — [members/sese2204/labs/02-kakao-chunk-embed/README.md](../../members/sese2204/labs/02-kakao-chunk-embed/README.md) (PR #6 미머지)
- do-dop · 노트 (§벡터 인덱스와 벡터 데이터베이스) — [members/do-dop/notes/02-search-generations.md](../../members/do-dop/notes/02-search-generations.md)
- kdyann · 검색의 세 세대 (§Exact NN과 ANN) — [members/kdyann/notes/02-search-generations.md](../../members/kdyann/notes/02-search-generations.md)
- lys0611 · 임베딩·코사인 유사도·HNSW — [members/lys0611/notes/02-embeddings-cosine-hnsw.md](../../members/lys0611/notes/02-embeddings-cosine-hnsw.md); 하이브리드 노트 (§HNSW와 방 필터) — [notes/04-hybrid-search-rrf-recall.md](../../members/lys0611/notes/04-hybrid-search-rrf-recall.md); 카톡 대화 적재 — [labs/01-ingest/README.md](../../members/lys0611/labs/01-ingest/README.md) (PR #15 미머지)
- 외부: Malkov & Yashunin, Efficient and Robust Approximate Nearest Neighbor Search Using HNSW (2016) https://arxiv.org/abs/1603.09320 · pgvector https://github.com/pgvector/pgvector
