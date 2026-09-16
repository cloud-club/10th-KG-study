---
title: 저장 구조 — LSM과 B-tree, Postgres와 Elasticsearch를 함께 쓴 이유
type: resource
tags: [concept]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [lys0611]
weeks: [2]
---

> DDIA 3장(2판 4장)의 저장 구조를 스터디 실습의 Postgres·pgvector·Elasticsearch에 대입한 lys0611의 노트. 다른 멤버가 다루지 않은 주제. 핵심은 "Postgres = B-tree DB", "Elasticsearch = LSM"이라는 단순화를 거부하고, 인덱스의 존재가 아니라 실행 계획을 보라는 것.

## 정의

- **추가 전용 로그 → SSTable → LSM.** 세그먼트 안을 키 순으로 정렬한 것이 SSTable. 정렬된 파일은 merge sort처럼 병합할 수 있고 희소 인덱스를 쓸 수 있다. LSM 계열은 memtable → 불변 SSTable이며, 읽기는 여러 레벨을 확인해야 해서 Bloom filter가 없는 키 조회를 줄여 준다. 백그라운드 compaction은 디스크 I/O와 쓰기 증폭을 만든다.
- **B-tree는 페이지를 갱신한다.** PostgreSQL 테이블·인덱스 페이지는 보통 8KB. WAL의 원칙: 변경된 데이터 페이지가 디스크에 기록되기 전에 해당 로그 레코드가 영구 저장되어야 한다.
- **Lucene 세그먼트는 LSM과 닮았지만 같지는 않다.** ES shard = Lucene index = 여러 segment. 세그먼트는 불변이고 삭제는 표시 후 병합 때 정리. 이 노트는 ES를 LSM DB라 부르지 않고 "Lucene 세그먼트 구조가 log-structured한 성격을 가진다"로 정리한다. `refresh`는 compaction과 다른 일이다(메모리 버퍼를 새 세그먼트로 쓰고 새 searcher가 보게 함).
- DDIA 1판 3장은 2026년 2판에서 4장으로 옮겨졌고 벡터 임베딩·벡터 검색 내용이 추가됐다.

## 실습 구조에 대입 (lys0611)

| 구성 | 실제 역할 | 다시 만들 수 있는가 |
|---|---|---|
| Postgres `messages` | 내보낸 메시지의 정본과 관계 정보 | 원본 파일에서 복구 가능하지만 가능한 한 보존 |
| Postgres `chunks` | 검색 단위로 만든 대화 조각 | `messages`에서 재생성 |
| pgvector `chunk_embeddings` | 의미 검색용 파생 벡터와 HNSW | 청크와 모델이 있으면 재생성 |
| Elasticsearch `kakao_chunks` | Nori/n-gram 역색인과 BM25 | 청크에서 재색인 |

- 정본/파생물을 나눈 이유는 모델·청킹 규칙·분석기를 바꿀 때 드러난다. 파생 인덱스를 지우고 다시 만들어도 원 메시지와 시간·발신자 관계는 남는다. 그래프를 붙일 때도 같은 원칙 → [[데이터-수집과-출처-추적]].
- 스키마 인덱스: 기본키·`(room_id, sent_at)`·`content_hash` 유니크(B-tree) + 본문 부분 검색용 GIN(pg_trgm) + 벡터 HNSW.

## 인덱스가 있다고 항상 쓰는 것은 아니다

- 메시지 18,973건에서 `ILIKE '%일정%'`을 `EXPLAIN (ANALYZE, BUFFERS)`로 확인하니 플래너가 GIN이 아니라 순차 스캔을 골랐다(49건 찾고 18,924건 제외, 약 26.7ms). 같은 환경의 벡터 top-5는 HNSW 인덱스 스캔. 데이터가 작고 검색어가 짧거나 흔하면 순차 스캔이 선택된다. **중요한 것은 인덱스의 존재가 아니라 실제 실행 계획**이며 결과를 적을 때는 체감 속도보다 `EXPLAIN`을 남긴다. sese2204도 pgvector에서 같은 현상을 봤다 → [[PostgreSQL과-pgvector-함정]], [[HNSW와-pgvector-인덱스]].

## OLTP 검색과 집계 질문은 다르다

- "작년에 가장 많이 언급된 가게는?", "정산 이야기를 가장 자주 꺼낸 사람은?"은 검색 문제가 아니라 집계 문제이고, 현재 데이터라면 SQL `GROUP BY`가 먼저 정확하다. 이 구분이 [[RAG-실패-유형]]의 G1(집계 불가)과 [[멀티홉-질문과-Bridge-Entity]]의 집계 한계로 이어진다.
- GraphRAG의 커뮤니티 요약을 구체화 뷰와 같은 기술로 보긴 어렵다. 자주 필요한 전역 정보를 빌드 시점에 계산해 재사용한다는 설계 감각만 닮았다.

## 열린 질문 (lys0611)

- 데이터 양·검색어 선택도를 바꿔 pg_trgm이 순차 스캔 → GIN 스캔으로 넘어가는 지점.
- 대량 색인 중 `refresh_interval` 조정 시 처리량·가시성 변화.
- VACUUM과 LSM/Lucene merge를 "공간 회수"로 묶지 말고 각각 무엇을 정리하는지 비교.

## 관련

- [[PostgreSQL과-pgvector-함정]] · [[Elasticsearch-운영-함정]] · [[역색인과-BM25]] · [[HNSW와-pgvector-인덱스]] · [[데이터-수집과-출처-추적]]

## 출처

- lys0611 · DDIA 저장소와 검색 — Postgres와 Elasticsearch를 함께 쓴 이유 — [members/lys0611/notes/03-ddia-ch3-storage-and-search.md](../../members/lys0611/notes/03-ddia-ch3-storage-and-search.md) (PR #15 미머지)
- 외부: Kleppmann, Designing Data-Intensive Applications 1판 3장 https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/ch03.html · 2판 4장 (Kleppmann & Riccomini, 2026) · PostgreSQL Database Page Layout, B-Tree Indexes, WAL Introduction · Elastic Near real-time search, Merge settings
