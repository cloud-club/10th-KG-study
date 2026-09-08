---
title: Notion 문서 저장 및 검색
date: 2026-09-08
tags: [notion, grep, elasticsearch, pgvector]
status: in-progress
---

# 1. Notion 문서 저장 및 검색

> 관련 노트: `../../notes/02-search-generations.md`

## 목표

Notion에서 내보낸 운영체제 수업 자료를 이용해 grep, Elasticsearch BM25, pgvector가 각각 어떤 구조로 데이터를 저장하고 검색하는지 확인한다.

## 데이터

- 대상: 운영체제 수업을 정리한 Notion 페이지
- 형식: Markdown
- 원본 위치: `data/raw/`
- 원본 데이터는 개인정보 및 저작권 보호를 위해 Git에 올리지 않는다.
- 시험 대비 자료와 기출문제는 실습 대상에서 제외한다.

## 환경

- 언어 / 런타임: 추후 작성
- 저장소: Elasticsearch, PostgreSQL + pgvector
- 실행 환경: Docker Compose 예정

## 실행 방법

아직 실습 전이므로 구현하면서 작성할 예정이다.

## 구조

```text
01-notion-search/
├── README.md
├── data/
│   └── raw/       # Git에 올리지 않는 Notion 원본
└── src/           # 파싱 및 검색 코드
```

## 결과

실습 후 검색 쿼리와 결과를 작성할 예정이다.

## 배운 점

실습 후 작성할 예정이다.

## 다음 단계

- [ ] Notion Markdown 문서를 읽고 청크로 나누기
- [ ] grep으로 문자열 검색하기
- [ ] Elasticsearch에 저장하고 BM25 검색하기
- [ ] PostgreSQL에 임베딩을 저장하고 pgvector로 검색하기
