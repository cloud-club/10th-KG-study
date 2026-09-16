---
title: 카카오톡 검색: grep · BM25 · pgvector
date: 2026-09-09
tags: [grep, elasticsearch, bm25, pgvector, hnsw]
---

# 카카오톡 검색: grep · BM25 · pgvector

하나의 카카오톡 TXT 데이터를 세 방식으로 검색한다.

| 방식 | 데이터 저장 형태 | 검색 기준 |
| --- | --- | --- |
| grep | 원본 TXT 파일 | 문자열이 정확히 포함된 줄 |
| Elasticsearch | JSON 문서와 nori 역색인 | 한국어 형태소 토큰의 BM25 점수 |
| pgvector | PostgreSQL 행과 임베딩 벡터 | 코사인 유사도 |

## 준비물

- 실행 중인 Docker Desktop
- Python 3.10 이상
- 로컬 파일 `data/raw/kakao_group.txt`

`data/raw/kakao_group.txt`는 개인 카카오톡 원본이므로 직접 준비하며, Git에 올리지 않는다.

## 실행

아래 명령은 이 폴더(`01-kakaotalk-search`)에서 실행한다.

### 1. 컨테이너와 파이썬 패키지 준비

```powershell
docker compose up -d
docker compose ps
python -m pip install -r requirements.txt
```

Elasticsearch는 `http://127.0.0.1:9201`, PostgreSQL/pgvector는 `127.0.0.1:5433`에서 실행된다.

### 2. TXT를 검색 단위로 변환

```powershell
python src/parse_kakao.py --input data/raw/kakao_group.txt --output data/processed/chunks.jsonl
```

파서는 카카오톡 TXT를 날짜별 텍스트 청크(JSONL)로 변환한다. 원본 파일은 수정하지 않는다.

### 3. 세 방식으로 검색

#### grep — 정확한 문자열 찾기

```powershell
& 'C:\Program Files\Git\usr\bin\grep.exe' -nF '재수강' data/raw/kakao_group.txt
```

#### Elasticsearch — 한국어 BM25 검색

```powershell
python src/index_elasticsearch.py --input data/processed/chunks.jsonl
python src/search_elasticsearch.py '재수강 신청'
```

첫 명령은 `kakao_chunks` 인덱스를 새로 만들고 청크를 적재한다. Elasticsearch에는 nori 형태소 분석기가 적용된다.

#### pgvector — 벡터 유사도 검색

```powershell
python src/index_pgvector.py --input data/processed/chunks.jsonl
python src/search_pgvector.py '수업을 다시 듣는 신청' --explain
```

첫 명령은 텍스트 임베딩을 만들고 `document_chunks` 테이블 및 HNSW 인덱스를 새로 생성한다. `--explain`은 PostgreSQL이 HNSW 인덱스를 사용하는 실행 계획을 함께 출력한다.

## 파일 구성

```text
01-kakaotalk-search/
├── compose.yaml                 # Elasticsearch, PostgreSQL/pgvector 컨테이너
├── requirements.txt             # 파이썬 패키지 목록
├── elasticsearch/Dockerfile     # nori 플러그인 설치
├── data/
│   ├── raw/kakao_group.txt      # 로컬 원본 데이터
│   └── processed/chunks.jsonl   # 파싱 결과
└── src/
    ├── parse_kakao.py
    ├── index_elasticsearch.py
    ├── search_elasticsearch.py
    ├── index_pgvector.py
    └── search_pgvector.py
```
