---
title: DDIA 3장 「저장소와 검색」 — Elasticsearch(LSM 계열)와 Postgres(B-tree)가 다른 이유
date: 2026-09-09
tags: [ddia, storage-engine, lsm-tree, sstable, b-tree, lucene, full-text-search, oltp, olap, column-store]
status: done
---

# 03. DDIA 3장 「저장소와 검색」 — Elasticsearch(LSM 계열)와 Postgres(B-tree)가 다른 이유

> 참고 자료:
> - Martin Kleppmann, 『데이터 중심 애플리케이션 설계』 3장 저장소와 검색 (위키북스). 1판 기준. 2판(Kleppmann & Riccomini, O'Reilly 2026)에서는 **4장** "Storage and Retrieval"
> - 1판 3장 목차: Hash Indexes · SSTables and LSM-Trees · B-Trees · Comparing B-Trees and LSM-Trees · Other Indexing Structures · Transaction Processing or Analytics? · Data Warehousing · Stars and Snowflakes · Column-Oriented Storage · Column Compression · Sort Order in Column Storage · Writing to Column-Oriented Storage · Aggregation: Data Cubes and Materialized Views
> - 실습: [labs/01-ingest](../labs/01-ingest/README.md) — Postgres(messages/chunks/pgvector) + Elasticsearch(kakao_chunks)

## 한 줄 요약

저장 엔진은 "쓸 때 정리하느냐(B-tree, 제자리 갱신) / 읽을 때 정리하느냐(LSM, 추가만 하고 나중에 병합)"로 갈린다. Postgres는 앞쪽, Elasticsearch(Lucene)는 뒤쪽이다. 우리가 이번 주에 만든 두 저장소가 왜 성격이 다른지, 왜 ES는 색인 직후 1초쯤 뒤에 보이는지가 이 장에 그대로 있다. 장의 후반(OLTP vs OLAP)은 "작년에 가장 많이 언급된 가게" 같은 **집계 질문**이 검색과 다른 종류의 문제임을 미리 알려준다.

## 핵심 개념

- **해시 인덱스**: 추가 전용 로그 + 메모리 해시(키 → 파일 오프셋). 빠르지만 키가 메모리에 다 들어가야 하고 범위 질의가 안 된다.
- **SSTable / LSM-tree**: 정렬된 불변 세그먼트를 쌓고 백그라운드에서 병합·컴팩션. 쓰기는 순차, 읽기는 여러 세그먼트를 볼 수 있어 블룸 필터로 보완. LevelDB·RocksDB·Cassandra, 그리고 **Lucene의 세그먼트**.
- **B-tree**: 고정 크기 페이지(보통 4KB)를 제자리에서 갱신. 대부분 관계형 DB(Postgres 포함)의 기본 인덱스. 장애 복구를 위해 WAL을 먼저 쓴다.
- **비교**: LSM은 쓰기 처리량·압축에 유리, B-tree는 읽기 지연이 예측 가능하고 키가 한 곳에만 있어 트랜잭션 격리에 유리. 어느 쪽이 낫다는 답은 워크로드에 달려 있다.
- **전문 검색과 퍼지 색인**: Lucene은 term 사전을 SSTable과 비슷한 구조로 두고, 메모리 안의 색인을 문자 단위 유한 상태 오토마톤(트라이 비슷)으로 만들어 편집 거리 검색(fuzzy)을 지원한다.
- **OLTP vs OLAP**: 행 단위 조회·갱신 vs 수백만 행을 훑는 집계. 분석에는 컬럼 지향 저장과 압축(비트맵)이 유리하다.

## 상세 정리

### 1. 가장 단순한 것에서 출발 — 추가 전용 로그와 해시 인덱스

- 파일 끝에 계속 붙여 쓰기(append)만 하면 쓰기는 빠르다. 찾기는 메모리 해시(키 → 오프셋)로.
- 파일이 커지면 세그먼트로 쪼개고, 같은 키의 옛 값을 버리는 **컴팩션**으로 공간을 되찾는다.
- 한계: 키 전부가 메모리에 있어야 함, 범위 스캔 불가. → 다음 단계.

### 2. SSTable과 LSM-tree

- 세그먼트 안을 **키 순으로 정렬**하면(SSTable) 병합이 머지소트처럼 단순해지고, 메모리 색인은 일부 키만 두어도 된다(희소 색인).
- 쓰기는 메모리 트리(멤테이블)에 넣고 임계치를 넘으면 SSTable로 내보낸다. 읽기는 멤테이블 → 최신 세그먼트 → 옛 세그먼트 순으로 본다. 없는 키 조회가 느리므로 **블룸 필터**로 걸러낸다.
- **Lucene(Elasticsearch)**: 색인 세그먼트가 불변이고, 새 문서는 새 세그먼트, 삭제는 삭제 표시, 백그라운드 병합 — 구조적으로 LSM 계열이다. ES에서 문서를 넣고 `refresh`(기본 1초) 전에는 검색되지 않는 이유가 여기 있다. 실습 `index_es.py`가 색인 뒤 `indices.refresh`를 부르고 나서야 `_count`가 맞게 나온 것도 같은 이야기.

### 3. B-tree

- 데이터를 고정 크기 페이지로 나누고, 루트 → 내부 → 리프로 키 범위를 좁혀간다. 깊이가 보통 3~4단계면 수억 키를 담는다.
- 갱신은 **제자리(in-place)**. 페이지가 가득 차면 분할. 중간에 죽으면 깨질 수 있어 **WAL(write-ahead log)**에 먼저 기록한다.
- Postgres의 기본 인덱스. 실습 `messages`의 PK, `(room_id, sent_at)` 인덱스, `chunks.content_hash` 유니크가 전부 B-tree다.

### 4. B-tree vs LSM — 우리 두 저장소에 대입

| | Postgres (B-tree) | Elasticsearch / Lucene (LSM 계열) |
|---|---|---|
| 쓰기 | 제자리 갱신, WAL | 추가 후 병합. 대량 색인에 유리(실습 `helpers.bulk`) |
| 읽기 | 키가 한 곳에 → 지연 예측 가능 | 여러 세그먼트 확인, 병합 상태에 따라 변동 |
| 갱신 가시성 | 커밋 즉시 | `refresh` 후 (기본 1초, near-real-time) |
| 컴팩션 부담 | 없음 (VACUUM은 별개) | 백그라운드 병합이 디스크·CPU를 씀 |
| 실습에서 역할 | **정본**(messages), 파생물(chunks, chunk_embeddings) | 파생 색인(kakao_chunks). 언제든 정본에서 다시 만들 수 있음 |

정본은 트랜잭션과 정확성이 중요한 B-tree 쪽에, 검색 색인은 다시 만들 수 있는 파생물로 LSM 쪽에 — 이 배치가 7주차 "원문은 정본, 그래프는 재생성 가능한 파생물" 설계의 축소판이다.

### 5. 그 밖의 색인 구조 — 실습에 쓰인 것들

| 실습 요소 | DDIA에서의 위치 | 메모 |
|---|---|---|
| `messages.text` GIN(pg_trgm) | 보조 색인 / 전문 검색 | `ILIKE '%…%'`를 3-gram 색인으로 가속. 0세대 grep에 색인만 붙인 것 |
| Lucene 역색인 + nori | 전문 검색과 퍼지 색인 | term 사전을 FST로 두어 편집 거리 검색(ES `fuzziness`) 가능 → [01](01-inverted-index-bm25.md) |
| pgvector HNSW | 다차원 색인 절의 연장선 | R-tree 같은 공간 색인의 자리에 "각도 기준 근접 그래프"가 들어온 셈. Postgres 페이지 안에 저장되지만 구조는 B-tree가 아님 → [02](02-embeddings-cosine-hnsw.md) |
| 인메모리 | Keeping everything in memory | 소규모(청크 수천 개)면 ES·pgvector 모두 사실상 메모리에서 동작. 디스크 구조 차이가 잘 안 느껴지는 이유 |

### 6. 트랜잭션 처리인가, 분석인가 (OLTP vs OLAP)

- OLTP: 사용자 요청마다 소수 행을 키로 읽고 쓴다. 우리 `messages` 적재·조회.
- OLAP: 수백만 행을 훑어 집계(합·평균·개수). 데이터 웨어하우스, 스타 스키마(사실 테이블 + 차원 테이블).
- **컬럼 지향 저장**: 행이 아니라 컬럼별로 저장하면 집계에 필요한 컬럼만 읽고, 같은 컬럼 값이 반복되므로 비트맵·런렝스 압축이 잘 된다. 정렬 순서를 컬럼 저장에 활용하고, 쓰기는 LSM처럼 메모리에 모아 병합한다.
- 데이터 큐브·구체화 뷰: 자주 쓰는 집계를 미리 계산해 둔다.

**이 장이 우리 로드맵에 주는 힌트.** "작년에 가장 많이 언급된 가게는?", "정산을 가장 자주 한 사람은?"은 검색(0~2세대)이 아니라 **집계** 질문이다. grep도 BM25도 벡터도 답을 못 내는 게 정상이다. 답은 (a) SQL `GROUP BY`(작게는 지금도 가능), (b) 6주차 GraphRAG의 집계·글로벌 서치처럼 **빌드 시점에 미리 계산해 두는(파생물)** 방식에서 나온다. DDIA가 "구체화 뷰"라고 부르는 것이 GraphRAG의 커뮤니티 요약과 닮았다.

### 7. 내 데이터에서 본 것

- `ILIKE '%일정%'`는 pg_trgm GIN 덕에 수만 건에서도 즉시 돌아왔다. 색인이 있어도 **순위가 없다**는 0세대의 한계는 그대로다.
- ES에 `bulk` 색인 후 `_count`가 잠깐 0이었다가 `refresh` 뒤에 맞게 나왔다 — LSM 계열의 가시성 지연을 눈으로 확인.
- `chunk_embeddings`에 HNSW 인덱스를 데이터 적재 **뒤에** 만들었다(빌드 한 번). 삽입 중에 인덱스가 있으면 삽입마다 그래프를 갱신해 느려진다는 pgvector 안내와 일치.

## 예시 / 코드

```sql
-- 우리 Postgres 의 색인 종류 확인: btree / gin / hnsw 가 섞여 있다
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('messages', 'chunks', 'chunk_embeddings')
ORDER BY 1, 2;

-- 집계 질문은 검색이 아니라 GROUP BY 다 (OLAP 성격)
SELECT mem.name, count(*) AS n
FROM messages m JOIN members mem ON mem.id = m.sender_id
WHERE m.sent_at >= '2025-01-01' AND m.sent_at < '2026-01-01' AND m.text ILIKE '%정산%'
GROUP BY 1 ORDER BY 2 DESC LIMIT 5;
```

```bash
# ES 세그먼트 확인: 색인이 여러 불변 세그먼트로 이뤄져 있다
curl -s "localhost:9200/_cat/segments/kakao_chunks?v&h=index,segment,docs.count,size"
```

## 궁금한 점 / 더 알아볼 것

- [ ] ES `refresh_interval`을 늘리면 대량 색인 속도가 얼마나 빨라지나 (LSM 쓰기 특성 체감)
- [ ] Postgres `VACUUM`과 LSM 컴팩션은 무엇이 같고 다른가
- [ ] 우리 집계 질문들을 SQL로 먼저 다 풀어 두면, 6주차에 그래프가 "SQL보다 나은" 지점이 어디인지 명확해질 것 — 미리 목록화
- [ ] 2판(2026)에서 이 장에 추가된 내용(벡터 색인·컬럼 저장 최신 사례)이 있는지 확인

## 스터디에서 나눌 이야기

- "왜 Postgres에 전문 검색(tsvector)이나 pgvector만 쓰지 않고 ES를 따로 두나?" — LSM 계열 색인과 분석기 생태계(nori) vs 운영 복잡도
- 정본(B-tree) ↔ 파생물(LSM/그래프) 배치가 7주차 설계와 어떻게 이어지는지
- 집계 질문을 "검색이 못 답하는 질문" 목록에 넣을 때, 검색 실패인지 질문 종류 차이인지 구분하기
