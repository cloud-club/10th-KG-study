# lys0611

## 소개

- GitHub: [@lys0611](https://github.com/lys0611)
- 한 줄 소개: 개인 카톡 데이터로 grep부터 GraphRAG까지 검색 기술의 변화를 재현하고, 개인정보 보호와 재현 가능한 데이터 파이프라인을 함께 검증합니다.
- 스터디 목표:
  - 내 카톡 데이터로 grep → BM25 → 벡터 → 하이브리드 → GraphRAG 변천사를 직접 재현하고, 각 단계가 무엇을 잡고 무엇을 놓치는지 표로 남기기
  - 개인정보를 가명화한 상태로 파이프라인 전체를 공개 가능한 형태로 유지하기 (정본 ↔ 파생물 분리)
  - W5~W7에서 미니 온톨로지와 지식 그래프 v0 까지 연결해 "그래프가 검색을 이기는 질문"을 찾기

## 데이터

- 프로젝트 팀 단톡방 2개 (안드로이드 내보내기 txt). 실명은 가명으로 치환, 전화·계좌·주민번호 마스킹 후 사용
- 원본·매핑표는 커밋하지 않음 (`data/`, `.env` 제외)

## 진행 현황

### notes

| # | 주제 | 상태 |
|---|------|------|
| 01 | [역색인과 BM25 — 키워드 검색(1세대)](notes/01-inverted-index-bm25.md) | 완료 |
| 02 | [임베딩·코사인 유사도·HNSW — 벡터 검색(2세대)](notes/02-embeddings-cosine-hnsw.md) | 완료 |
| 03 | [DDIA 3장 저장소와 검색 — ES(LSM)와 Postgres(B-tree)](notes/03-ddia-ch3-storage-and-search.md) | 완료 |

### labs

| # | 실습 | 상태 |
|---|------|------|
| 01 | [카톡 대화 적재 — Postgres · pgvector · Elasticsearch (3세대 비교)](labs/01-ingest/README.md) | 완료 |
