---
title: DDIA 저장소와 검색 — Postgres와 Elasticsearch를 함께 쓴 이유
date: 2026-09-09
tags: [ddia, storage-engine, lsm-tree, sstable, b-tree, lucene, full-text-search, oltp, olap, column-store]
status: done
---

# 03. DDIA 저장소와 검색 — Postgres와 Elasticsearch를 함께 쓴 이유

DDIA 1판의 3장 제목은 「저장소와 검색(Storage and Retrieval)」이다. 2026년에 나온 2판에서는 4장으로 옮겨졌고 벡터 임베딩과 벡터 검색 내용도 추가됐다. 이번 실습의 Postgres, Elasticsearch, pgvector를 책의 저장 구조에 대입해 보니 세 저장소를 단순히 “DB 세 개”로 보는 것보다 각각 어떤 읽기와 쓰기를 위해 만든 구조인지 보는 편이 이해하기 쉬웠다.

먼저 한 가지는 구분해 두어야 한다. Postgres는 B-tree만으로 데이터를 저장하는 DB가 아니고, Elasticsearch도 LSM-tree 구현 그 자체는 아니다. Postgres의 기본 보조 인덱스가 B-tree이고, Lucene의 불변 세그먼트와 병합 방식이 LSM 계열 설계와 닮았다고 말하는 것이 더 정확하다.

## 추가 전용 로그에서 SSTable까지

가장 단순한 저장 방식은 파일 끝에 새 값을 계속 붙이는 것이다. 쓰기는 빠르지만 원하는 키를 찾으려면 파일 전체를 읽어야 한다. 메모리에 `키 → 파일 위치` 해시를 두면 점 조회는 빨라진다. 대신 키가 메모리에 들어가야 하고 범위 검색은 어렵다.

로그가 계속 커지는 문제는 파일을 여러 세그먼트로 나누고 옛 값을 버리는 compaction으로 해결할 수 있다. 세그먼트 안을 키 순으로 정렬한 것이 SSTable이다. 정렬된 여러 파일은 merge sort와 비슷하게 병합할 수 있고, 모든 키가 아니라 일부 키의 위치만 메모리에 둔 희소 인덱스도 쓸 수 있다.

LSM-tree 계열은 쓰기를 먼저 메모리의 정렬 구조(memtable)에 모으고, 일정 크기가 되면 불변 SSTable로 내보낸다. 읽을 때는 메모리와 여러 레벨의 파일을 확인해야 하므로 Bloom filter 같은 장치가 없는 키 조회를 줄여 준다. 백그라운드 compaction은 중복 값과 삭제된 값을 정리하지만, 그만큼 디스크 I/O와 쓰기 증폭도 생긴다.

## B-tree는 페이지를 갱신한다

B-tree는 키 범위를 나누는 페이지 구조다. 루트에서 내부 페이지를 거쳐 리프까지 내려가며 원하는 키의 범위를 좁힌다. PostgreSQL의 테이블과 인덱스 페이지는 보통 8KB다.

페이지에 공간이 없으면 분할이 일어나고, 갱신 중 장애가 나도 복구할 수 있도록 WAL(write-ahead log)을 먼저 기록한다. WAL의 핵심 원칙은 변경된 데이터 페이지가 디스크에 기록되기 전에 해당 로그 레코드가 영구 저장되어야 한다는 것이다.

이번 스키마의 기본키, `(room_id, sent_at)`, `content_hash` 유니크 인덱스는 B-tree다. 여기에 본문 부분 검색용 GIN(`pg_trgm`)과 벡터 검색용 HNSW가 같이 있다. PostgreSQL을 쓴다고 모든 인덱스가 B-tree인 것은 아니다.

## Lucene 세그먼트는 LSM과 닮았지만 같지는 않다

Elasticsearch의 shard는 Lucene index이고, Lucene index는 여러 segment로 구성된다. 세그먼트는 한번 만들어지면 내용이 바뀌지 않는다. 새 문서는 새 세그먼트에 기록되고, 삭제는 바로 파일을 지우기보다 삭제 표시로 처리한 뒤 작은 세그먼트들이 병합될 때 정리된다. 추가 기록과 불변 파일, 백그라운드 병합이라는 점에서 LSM 계열과 비슷하다.

다만 Lucene 세그먼트는 검색을 위한 역색인이고, 일반적인 키-값 LSM-tree의 memtable·SSTable 레벨 구조와 완전히 같은 구현은 아니다. 그래서 이 노트에서는 Elasticsearch를 LSM DB라고 부르지 않고, Lucene의 세그먼트 구조가 log-structured한 성격을 가진다고 정리했다.

`refresh`도 compaction 자체와는 다른 일이다. Elasticsearch는 refresh 때 메모리 버퍼의 내용을 새 Lucene 세그먼트로 쓰고 새 searcher가 그 세그먼트를 볼 수 있게 한다. 기본 설정에서는 대체로 1초 주기지만, 최근 30초 안에 검색된 인덱스에 한해 주기적으로 실행된다는 조건이 있다. 현재 `index_es.py`는 bulk 색인 뒤 명시적으로 refresh를 호출한다. 따라서 이번 코드로는 “count가 잠시 0이었다”는 관찰을 했다고 쓸 수 없고, 색인 직후 확인 쿼리의 가시성을 코드가 보장한다고 보는 것이 맞다.

## 실습 구조에 대입해 보기

| 구성 | 실제 역할 | 다시 만들 수 있는가 |
|---|---|---|
| Postgres `messages` | 내보낸 메시지의 정본과 관계 정보 | 원본 파일에서 복구할 수 있지만 가능한 한 보존 |
| Postgres `chunks` | 검색 단위로 만든 대화 조각 | `messages`에서 재생성 가능 |
| pgvector `chunk_embeddings` | 의미 검색용 파생 벡터와 HNSW | 청크와 모델이 있으면 재생성 가능 |
| Elasticsearch `kakao_chunks` | Nori/n-gram 역색인과 BM25 | 청크에서 재색인 가능 |

정본과 파생물을 나눈 것이 중요한 이유는 모델, 청킹 규칙, 분석기를 바꿀 때 드러난다. 파생 인덱스를 지우고 다시 만들어도 원래 메시지와 시간·발신자 관계는 남는다. 이후 그래프를 붙일 때도 같은 원칙을 적용할 수 있다.

## 인덱스가 있다고 항상 쓰는 것은 아니다

`messages.text`에는 `pg_trgm` GIN 인덱스가 있다. PostgreSQL 공식 문서상 trigram GIN/GiST 인덱스는 `LIKE`와 `ILIKE`를 포함한 유사도·부분 문자열 검색을 지원한다. 그렇다고 모든 쿼리가 자동으로 인덱스 스캔이 되는 것은 아니다.

현재 18,973개 메시지에서 `ILIKE '%일정%'`을 `EXPLAIN (ANALYZE, BUFFERS)`로 확인했더니 플래너는 GIN이 아니라 순차 스캔을 선택했다. 49건을 찾고 18,924건을 제외했으며 약 26.7ms가 걸렸다. 데이터가 작고 검색어가 짧거나 흔하면 인덱스를 거치는 비용보다 전체를 읽는 편이 싸다고 판단할 수 있다. 처음에는 조회가 빠르니 GIN을 탄다고 생각했는데, 실행 계획은 달랐다.

반면 같은 환경의 벡터 top-5 쿼리는 `chunk_embeddings_hnsw` 인덱스 스캔을 선택했다. 중요한 것은 인덱스의 존재가 아니라 실제 실행 계획이다. 실험 결과를 적을 때는 체감 속도보다 `EXPLAIN`을 함께 남기는 편이 낫다.

## OLTP 검색과 집계 질문은 다르다

장의 후반부는 트랜잭션 처리와 분석을 나눈다. OLTP는 보통 키로 소수 행을 읽고 쓰며, OLAP은 많은 행에서 일부 컬럼을 읽어 합계·평균·개수를 계산한다. 컬럼 지향 저장은 필요한 컬럼만 읽을 수 있고 비슷한 값이 이어져 압축도 잘 되므로 분석 워크로드에 유리하다.

이 구분은 “작년에 가장 많이 언급된 가게는?”, “정산 이야기를 가장 자주 꺼낸 사람은?” 같은 질문을 볼 때 도움이 됐다. 이것은 관련 문서 한두 개를 찾는 검색 문제가 아니라 여러 행을 세고 묶는 집계 문제다. grep, BM25, 벡터 검색이 바로 답하지 못하는 것이 자연스럽고, 현재 데이터라면 먼저 SQL `GROUP BY`로 풀어 보는 편이 정확하다.

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

GraphRAG의 커뮤니티 요약을 구체화 뷰와 완전히 같은 기술이라고 보기는 어렵다. 다만 자주 필요한 전역 정보를 빌드 시점에 계산해 두고 질의 때 재사용한다는 설계 감각은 닮아 있다. 둘을 연결할 때는 구현의 동일성이 아니라 이 비유의 범위까지만 말하는 것이 좋겠다.

## 다음에 확인할 것

- 데이터 양과 검색어 선택도를 바꿔 `pg_trgm`이 순차 스캔에서 GIN 스캔으로 넘어가는 지점을 확인한다.
- 대량 색인 중 `refresh_interval`을 조정했을 때 처리량과 검색 가시성이 어떻게 달라지는지 기록한다.
- PostgreSQL의 VACUUM과 LSM/Lucene merge를 “공간 회수”라는 공통점만으로 묶지 말고, 각각 무엇을 정리하는지 비교한다.
- 검색 실패 질문을 단순 검색, 집계, 다중 홉으로 분류한 뒤 SQL·RAG·그래프가 맡을 범위를 정한다.

## 확인한 자료

- O'Reilly, DDIA [1판 3장 Storage and Retrieval](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/ch03.html) · [2판 4장 Storage and Retrieval](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch04.html)
- PostgreSQL, [Database Page Layout](https://www.postgresql.org/docs/current/storage-page-layout.html) · [B-Tree Indexes](https://www.postgresql.org/docs/current/btree.html) · [WAL Introduction](https://www.postgresql.org/docs/current/wal-intro.html)
- PostgreSQL, [`pg_trgm`](https://www.postgresql.org/docs/current/pgtrgm.html)
- Elastic, [Near real-time search](https://www.elastic.co/docs/manage-data/data-store/near-real-time-search) · [Merge settings](https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-merge.html)
