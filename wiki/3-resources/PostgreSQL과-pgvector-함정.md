---
title: PostgreSQL과 pgvector 함정 모음
type: resource
tags: [pitfall, tooling]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [sese2204, lys0611, dldusgh318, yujeong430]
weeks: [1, 2, 3]
---

> 공용 인프라의 PostgreSQL 17 + pgvector + pg_trgm에서 멤버들이 실제로 겪은 것들. 로케일, 플래너, 인덱스와 적재 순서, 볼륨 경로. 근거 없는 항목은 싣지 않는다.

## pg_trgm

- **`--locale=C`로 만든 DB에서는 pg_trgm이 한글 트라이그램을 못 뽑는다** (sese2204, 2026-09-09). `show_trgm('수강신청')`이 `{}`. 인덱스는 있는데 플래너가 순차 스캔의 33배 비용으로 계산해 한 번도 안 탔다. `--locale=C.UTF-8`로 다시 initdb하니 Bitmap Index Scan(heap 5블록). 확인: `select datctype from pg_database where datname='kg'`가 `C.UTF-8`이어야 한다. 예전 볼륨이면 `docker compose down -v` 후 재기동(데이터 초기화). 공용 compose가 이렇게 고쳐졌다 → [[로컬-인프라]].
- **`similarity`가 아니라 `word_similarity`** (sese2204): 짧은 질문 vs 긴 본문이면 `similarity`는 0.3 임계값을 못 넘는다. `WHERE 질문 <% text ORDER BY word_similarity(질문, text)`가 GIN Bitmap Scan을 탄다. `수강신청` → word_similarity 1.0 / 1.0 / 0.8.
- **GIN이 있어도 플래너가 안 쓴다** (lys0611, 메시지 18,973건): `ILIKE '%일정%'`을 `EXPLAIN (ANALYZE, BUFFERS)`로 보니 GIN이 아니라 **순차 스캔**을 골랐다(49건 찾고 18,924건 제외, 약 26.7ms). "처음에는 조회가 빠르니 GIN을 탄다고 생각했는데 실행 계획은 달랐다." 데이터가 작고 검색어가 짧거나 흔하면 순차 스캔이 선택된다. 결과를 적을 때는 체감 속도보다 `EXPLAIN`을 함께 남긴다.
- pg_trgm은 부분 문자열 검색을 빠르게 할 뿐 동의어 이해나 관련도 순위를 주지 않는다 (lys0611). grep 세대의 재현 도구로 `ILIKE`를 쓰고 pg_trgm은 속도 보조로만.

## pgvector

- **작은 테이블에서 HNSW를 안 탄다** (sese2204, 11,985행): 순차 스캔 74ms vs HNSW 1.8ms인데도 플래너는 순차 스캔. 질의 단위로 `SET LOCAL enable_seqscan = off`. 세부는 [[HNSW와-pgvector-인덱스]].
- **HNSW가 있으면 COPY가 느려진다** (sese2204): 66초 → 86초. 대량 재적재면 인덱스를 지웠다 만든다. lys0611도 데이터를 먼저 넣고 인덱스를 만드는 편이 빠르다고 적었다.
- **필터 + ANN = `LIMIT`을 못 채움** (lys0611): `WHERE room_id = …`가 인덱스 스캔 뒤에 적용돼 `ef_search=40` 후보 중 해당 방이 적으면 10건을 못 받는다. `SET LOCAL hnsw.iterative_scan = strict_order` (pgvector 0.8+). GUIDE 초기 처방은 `ef_search=200`이었는데 나중 문서가 iterative_scan으로 갱신했다.
- **거리 연산자와 opclass를 맞춘다** (lys0611): `<=>`↔`vector_cosine_ops`, `<->`↔`vector_l2_ops`, `<#>`↔`vector_ip_ops`(음의 내적, 인덱스가 오름차순이라). `<=>`는 거리라 작을수록 가깝고 유사도는 `1 − 거리` (네 멤버 공통).
- **차원이 바뀌면 테이블을 새로 만든다** (lys0611): `vector(1536)`인데 `EMBED_DIM=768`이면 `DROP TABLE chunk_embeddings` 후 재실행하거나 모델별 테이블 분리. PK를 `(chunk_id, model)`로 두면 같은 차원의 모델은 나란히 쌓인다.
- **정확 검색 vs ANN을 구분해서 판단** (dldusgh318, lys0611): `SET enable_indexscan = off`로 정확 검색 결과와 겹침을 재야 "벡터가 틀렸다"인지 "HNSW가 놓쳤다"인지 안다. lys0611은 ef_search=100에서 겹침 1.000.
- 테이블은 원문 `chunks`와 벡터 `emb_*`를 분리하고 `chunk_id`로 잇는다 (dldusgh318). 정본·파생물 원칙은 [[데이터-수집과-출처-추적]].

## 볼륨·버전·포트

- **Postgres 18 이미지는 볼륨을 `/var/lib/postgresql`에 마운트**해야 데이터가 유지된다. `…/data`에 마운트하면 재시작 때 데이터가 사라진다(PGDATA가 `/var/lib/postgresql/18/docker`로 바뀜) (lys0611). 공용 인프라는 pg17이라 `/var/lib/postgresql/data`. lys0611의 실습 데이터(pg18.6, ES 9.5.3)는 공용 인프라(pg17, ES 9.1)로 그대로 못 옮기고 `run_pipeline.sh` 재적재나 `pg_dump`가 필요하다.
- 이미 만들어진 볼륨에는 `infra/postgres/init/01-extensions.sql`이 자동 적용되지 않는다 (infra README).
- `port is already allocated` = 로컬에 이미 PG/ES/Neo4j가 돌고 있다. dldusgh318은 호스트 5432를 로컬 Postgres가 쓰고 있어 5433으로 비켰고, yujeong430도 5433·9201을 쓴다 → [[로컬-인프라]].
- 여러 실습이 한 인스턴스를 나눠 쓰면 테이블·인덱스에 멤버 접두사를 붙인다(`do_dop_kakao_chunks`, `ur2e_worklog_chunks_<설정키>`).

## 관련

- [[HNSW와-pgvector-인덱스]] · [[로컬-인프라]] · [[Elasticsearch-운영-함정]] · [[저장-구조-LSM과-B-tree]] · [[데이터-수집과-출처-추적]]

## 출처

- sese2204 · 카카오톡 파싱 → 적재 (§배운 점), 청킹 → 임베딩 → 검색 (§검색, §배운 점) — [members/sese2204/labs/01-kakao-ingest/README.md](../../members/sese2204/labs/01-kakao-ingest/README.md), [labs/02-kakao-chunk-embed/README.md](../../members/sese2204/labs/02-kakao-chunk-embed/README.md), [infra/README.md](../../infra/README.md) (PR #6 미머지)
- lys0611 · DDIA 노트 (§인덱스가 있다고 항상 쓰는 것은 아니다), 임베딩 노트 (§방 필터), GUIDE §트러블슈팅, 실습 02 (§배운 점) — [members/lys0611/notes/03-ddia-ch3-storage-and-search.md](../../members/lys0611/notes/03-ddia-ch3-storage-and-search.md), [notes/02-embeddings-cosine-hnsw.md](../../members/lys0611/notes/02-embeddings-cosine-hnsw.md), [labs/01-ingest/GUIDE.md](../../members/lys0611/labs/01-ingest/GUIDE.md), [labs/02-hybrid-rag-agent/README.md](../../members/lys0611/labs/02-hybrid-rag-agent/README.md) (PR #15 미머지)
- dldusgh318 · 2세대 노트 (§5), WEEK2 compose 주석 — [members/dldusgh318/notes/week2/03-embedding-vector-search.md](../../members/dldusgh318/notes/week2/03-embedding-vector-search.md), [labs/01-three-generations/WEEK2.md](../../members/dldusgh318/labs/01-three-generations/WEEK2.md)
- yujeong430 · 카카오톡 검색 — [members/yujeong430/labs/01-kakaotalk-search/README.md](../../members/yujeong430/labs/01-kakaotalk-search/README.md)
- 외부: PostgreSQL pg_trgm https://www.postgresql.org/docs/current/pgtrgm.html · pgvector README (Iterative index scans, Filtering) https://github.com/pgvector/pgvector · "Postgres 18 Docker Silently Ignores Your Named Volume" (lys0611 readings)
