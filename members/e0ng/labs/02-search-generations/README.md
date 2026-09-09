---
title: 내 데이터를 세 가지 검색 방식으로 저장하고 검색하기
date: 2026-09-09
tags: [grep, elasticsearch, bm25, pgvector, vector-search]
status: in-progress
---

# 02. 내 데이터를 세 가지 검색 방식으로 저장하고 검색하기

> 관련 노트: `../../notes/02-search-generations.md`

## 목표

본인이 선택한 데이터를 다음 세 가지 방식에 맞게 직접 저장하고 쿼리를 실행한다.

1. grep 문자열 매칭
2. Elasticsearch BM25 키워드 검색
3. pgvector 벡터 검색

다음 스터디 시간에는 저장한 데이터와 저장 구조를 보여주고, 각 방식으로 직접 쿼리를 실행한다. 시간이 남으면 해당 데이터를 조회하는 검색 기능도 붙여 본다.

## 사용할 데이터

- 데이터 주제: [TODO]
- 데이터 출처: [TODO]
- 데이터 형식: [TODO]
- 데이터 규모: [TODO]
- 이 데이터를 선택한 이유: [TODO]

원본 데이터는 `data/`에 둔다. 데이터가 크거나 공개하면 안 되는 경우에는 원본을 커밋하지 않고, 샘플 데이터와 다운로드·생성 방법만 기록한다.

## 구현별 확인 사항

### 1. grep

- 내 데이터를 grep으로 검색할 수 있도록 저장한 형태: [TODO]
- 실행할 쿼리: [TODO]
- 작업 파일: `src/grep/`

### 2. Elasticsearch BM25

- 인덱스, 문서 필드, 매핑과 분석기 구조: [TODO]
- 데이터를 저장한 방법: [TODO]
- 실행할 쿼리: [TODO]
- 작업 파일: `src/elasticsearch-bm25/`

### 3. pgvector

- 테이블, 원문·메타데이터·벡터 컬럼 구조: [TODO]
- 데이터를 임베딩하고 저장한 방법: [TODO]
- 실행할 쿼리: [TODO]
- 작업 파일: `src/pgvector/`

## 환경

- 언어 / 런타임: [TODO]
- Elasticsearch 버전: [TODO]
- PostgreSQL 버전: [TODO]
- pgvector 버전: [TODO]
- 임베딩 모델: [TODO]
- 외부 서비스 / 키: 필요하면 `.env.example`에 변수 이름만 기록하고 실제 키는 커밋하지 않는다.

## 실행 방법

```bash
[TODO] 데이터 저장 및 실행 명령
```

## 구조

```text
02-search-generations/
├── README.md
├── data/                          # 본인이 선택한 원본 또는 샘플 데이터
└── src/
    ├── grep/                      # grep 실행 스크립트 또는 명령 기록
    ├── elasticsearch-bm25/        # 인덱스 설정, 적재 및 쿼리
    └── pgvector/                  # 테이블, 적재 및 벡터 쿼리
```

## 스터디 시간에 보여줄 것

- [ ] grep에서 내 데이터가 어떤 파일 구조로 저장되어 있는지 보여주기
- [ ] Elasticsearch의 인덱스·매핑과 저장된 문서 보여주기
- [ ] PostgreSQL 테이블·벡터 컬럼과 저장된 행 보여주기
- [ ] 각 방식에 쿼리 실행하기
- [ ] 검색 기능 보여주기(선택)

## 배운 점

- 잘 된 것: [TODO]
- 막혔던 것과 해결 방법: [TODO]

## 다음 단계

- [ ] 본인 데이터 선정
- [ ] 세 방식의 데이터 저장 구조 완성
- [ ] 스터디 시간에 저장 구조와 쿼리 실행 시연
- [ ] 검색 기능 추가(선택)
