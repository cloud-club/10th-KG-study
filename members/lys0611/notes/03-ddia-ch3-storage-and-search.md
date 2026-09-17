---
title: DDIA 저장소와 검색 — Postgres와 Elasticsearch를 함께 쓴 이유
date: 2026-09-09
tags: [ddia, storage-engine, lsm-tree, sstable, b-tree, lucene, full-text-search, oltp, olap, column-store]
status: done
---

# 03. DDIA 저장소와 검색 — Postgres와 Elasticsearch를 함께 쓴 이유

DDIA 1판 3장 「저장소와 검색」을 실습에 대입했다. Postgres와 Elasticsearch는 같은 데이터를 다른 방식으로 읽는다. pgvector는 별도 DB가 아니라 Postgres의 벡터 검색 확장이다.

## 로그, SSTable, LSM-tree

파일 끝에 값을 붙이는 방식은 쓰기는 단순하지만 조회할 때 파일을 훑어야 한다. 메모리에 `키 → 파일 위치` 해시를 두면 점 조회가 빨라지는 대신 메모리가 필요하고 범위 검색에는 불리하다.

SSTable은 키순으로 정렬한 파일이다. 일부 키 위치만 저장하는 희소 인덱스로 범위를 좁히고, 파일끼리 순서대로 읽으며 병합할 수 있다.

LSM 계열에서는 쓰기를 메모리의 memtable에 모았다가 불변 SSTable로 내보낸다. 읽을 때 여러 파일을 확인하는 비용이 생겨 Bloom filter 등으로 불필요한 조회를 줄인다. compaction은 중복·삭제된 값을 정리하지만 파일을 다시 쓰는 I/O도 발생한다. ([DDIA 1판 3장](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/ch03.html))

## B-tree와 WAL

B-tree는 키 범위별 페이지를 따라 내려가며 값을 찾는다. PostgreSQL의 페이지 크기는 보통 8KB이고, 인덱스 페이지에 공간이 부족하면 분할이 일어난다.

WAL은 변경된 데이터 페이지보다 로그를 먼저 디스크에 저장한다는 원칙이다. 장애가 나면 로그를 이용해 아직 데이터 파일에 반영하지 못한 변경을 복구한다. ([페이지 구조](https://www.postgresql.org/docs/current/storage-page-layout.html), [WAL](https://www.postgresql.org/docs/current/wal-intro.html))

현재 스키마의 기본키, `(room_id, sent_at)`, `content_hash` 유니크 인덱스는 B-tree다. 본문 부분 검색에는 `pg_trgm` GIN, 벡터 검색에는 HNSW를 쓴다. 테이블의 heap 저장과 이 보조 인덱스들을 구분해야 한다.

## Lucene 세그먼트와 refresh

Elasticsearch shard의 Lucene index는 여러 segment로 구성된다. 새 문서는 추가 기록하고 삭제된 문서의 공간은 병합 때 회수한다. 불변 파일과 병합 방식은 LSM과 닮았다.

다만 Lucene 세그먼트에는 역색인 등 검색용 구조가 들어 있다. 일반적인 키-값 LSM의 memtable·SSTable과 같은 구현이라고 보기는 어렵다.

`refresh`는 병합이 아니라 새 세그먼트를 검색에서 보이게 하는 작업이다. 기본 1초 주기에도 최근 검색 여부 등의 조건이 있고, 검색 가능해졌다는 것과 디스크에 영구 저장됐다는 것은 다르다. 실습의 `index_es.py`는 bulk 색인 후 refresh를 직접 호출하므로 다음 확인 쿼리에서 새 문서를 볼 수 있다. ([Near real-time search](https://www.elastic.co/docs/manage-data/data-store/near-real-time-search))

## 정본과 파생 데이터

| 구성 | 역할 | 재생성 기준 |
|---|---|---|
| Postgres `messages` | 메시지·시각·발신자 정본 | 내보낸 원본 파일 |
| Postgres `chunks` | 검색용 대화 조각 | messages와 청킹 규칙 |
| pgvector `chunk_embeddings` | 의미 검색용 벡터 | 청크와 임베딩 모델 |
| Elasticsearch `kakao_chunks` | Nori/n-gram 역색인 | 청크와 분석기 설정 |

청킹·모델·분석기를 바꿔도 메시지 정본은 보존한다. 청크를 재생성하면 ES에도 반영해야 한다. 옛 문서가 남지 않도록 ID·본문·건수를 함께 확인한다.

## 인덱스가 있어도 순차 스캔할 수 있다

`pg_trgm`의 GIN/GiST는 `LIKE`, `ILIKE`를 지원한다. 하지만 인덱스가 있다는 이유만으로 매번 사용되는 것은 아니다. 검색어에서 추출할 trigram이 적거나 없으면 인덱스의 이점도 줄어든다. ([pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html))

W2 실행 기록에서 `ILIKE '%일정%'`은 18,973개 메시지를 순차 스캔했다. 결과는 49건, 약 26.7ms였다. 반면 벡터 top-5는 HNSW 인덱스 스캔이었다. 속도만 보고 인덱스를 탔다고 판단하면 안 되는 사례다.

`EXPLAIN (ANALYZE, BUFFERS)`로 계획과 읽은 페이지를 확인한다. 순차 스캔을 택한 이유는 데이터 크기·검색어·비용 추정을 더 살펴봐야 한다.

## 검색과 집계

OLTP는 소수 행을 자주 읽고 쓰고, OLAP은 많은 행을 집계한다. 컬럼 지향 저장은 필요한 컬럼만 읽고 유사한 값을 압축할 수 있어 분석에 유리하다.

카톡의 “정산을 가장 많이 언급한 사람은?”도 상위 청크 몇 개를 찾는 것과는 다른 문제다. 문자 그대로의 언급 횟수라면 SQL로 셀 수 있다.

```sql
SELECT mem.name, count(*) AS n
FROM messages AS m
JOIN members AS mem ON mem.id = m.sender_id
WHERE m.sent_at >= DATE '2025-01-01'
  AND m.sent_at <  DATE '2026-01-01'
  AND m.text ILIKE '%정산%'
GROUP BY mem.name
ORDER BY n DESC
LIMIT 5;
```

이 쿼리는 `정산`이 들어간 메시지만 센다. `돈 보내 줘`까지 포함하려면 별도 분류가 필요하다. 동명이인도 구분해야 한다. 회의 참석자라면 단순 언급과 실제 참석 근거를 나눠야 한다.

최다 발신자는 RDB 집계로, 요청자와 수행자는 관계 추출로 접근할 수 있다. 그래프를 붙이기 전에 질문에 필요한 정보부터 나눠 봐야 한다.

다음에는 검색어 길이와 데이터 양에 따라 GIN이 선택되는지, `refresh_interval`이 색인 처리량과 검색 가시성에 어떤 영향을 주는지 확인한다.

## 참고

- PostgreSQL, [B-Tree Indexes](https://www.postgresql.org/docs/current/btree.html)
- Elastic, [Merge settings](https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-merge.html)
