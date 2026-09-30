---
title: 청크 데이터로 grep, BM25, pgvector, HNSW 비교
date: 2026-09-30
tags: [rag, bm25, elasticsearch, nori, embedding, pgvector, hnsw]
status: done
---

# 01. 검색의 세 세대 비교

> 관련 노트: [청킹부터 BM25, pgvector, HNSW까지](../../notes/02-search-methods.md)

## 목표

같은 청크를 문자열·키워드·벡터로 검색하고, 전체 비교와 HNSW 근사 탐색의 차이를 확인한다. 문서에서 답변에 쓸 근거를 찾는 단계까지이며, LLM 답변 생성은 다음 주차에서 진행한다.

## 환경

- macOS / Python 3(표준 라이브러리만 사용), Docker Compose
- Ollama / `qwen3-embedding:0.6b` / 벡터 1,024차원
- Elasticsearch 8.19.21 + Nori, `127.0.0.1:19200`
- PostgreSQL 17 + pgvector 0.8.6, Docker 내부 `psql`로 접속

기존 로컬 실습을 보존하기 위해 저장소 루트 공용 인프라 대신 실습에 사용한 Compose를 함께 둔다. 루트 Compose와 포트·버전·DB 설정이 다르다. 아래 명령은 이 실습 폴더 안에서 실행한다. Compose 프로젝트 이름이 기존 로컬 실습과 같으므로 같은 호스트에서는 같은 컨테이너·볼륨을 사용한다. 로컬 학습용 인증 설정이다.

회사 데이터셋과 벡터 캐시는 공개 저장소에 포함하지 않는다. 사용 권한이 있는 입력 파일을 저장소 루트 `data/sunghyun/normalized_documents_with_path.jsonl`에 직접 둔다. 데이터가 다르면 아래 결과 개수와 순위도 달라진다.

## 실행 방법

### 1. 문서 → 청크

저장소 루트에서 실습 폴더로 이동한다.

```bash
cd members/sunghyun/labs/01-search-generations
python3 src/01_chunk_documents.py \
  --input ../../../../data/sunghyun/normalized_documents_with_path.jsonl \
  --output src/outputs/chunked_documents_v1.jsonl
```

출력 파일이 이미 있으면 덮어쓰지 않고 중단한다. 기존 청크가 있으면 그대로 사용하거나 다른 출력 경로를 지정한다.

### 2. 문자열 검색과 BM25

```bash
docker compose -f src/bm25_lab/compose.yaml up -d --build
curl -fsS http://127.0.0.1:19200/_cluster/health
python3 src/bm25_lab/search_lab.py load
python3 src/bm25_lab/search_lab.py grep 'URM 서버 등록하는 방법' --top 3
python3 src/bm25_lab/search_lab.py analyze 'URM 서버 등록하는 방법'
python3 src/bm25_lab/search_lab.py bm25 'URM 서버 등록하는 방법' --operator or --top 3
python3 src/bm25_lab/search_lab.py bm25 'URM 서버 등록하는 방법' --operator and --top 3
```

HTTP 요청이 성공한 뒤 적재한다. 기본 인덱스는 `rag-chunks-v1`, 검색 필드는 `embedding_text`이며 적재 시 역색인을 만든다. 같은 ID 재적재는 갱신하지만 사라진 ID를 자동 삭제하지 않으므로 입력 집합을 바꾸면 기존 인덱스와 개수가 다를 수 있다. 원본을 삭제하는 자동 정리는 하지 않는다.

원래 실습은 코드의 `operator`를 직접 바꿨다. 여기서는 비교하기 편하게 `--operator`를 추가했으며 기본값은 마지막 실습의 AND다. 다른 청크 파일은 `--input`으로 지정할 수 있다. 특정 결과의 점수 구성은 다음처럼 확인할 수 있다.

```bash
python3 src/bm25_lab/search_lab.py explain 'URM 서버 등록하는 방법' \
  --operator and --id '<검색 결과의 chunk_id>'
```

### 3. 샘플 임베딩 → 전체 벡터 파일 검색

모델이 없을 때 다운로드하고 Ollama 서버를 실행한다. 이미 실행 중이면 서버를 추가 실행하지 않는다.

```bash
ollama pull qwen3-embedding:0.6b
ollama serve
```

다른 터미널에서 같은 실습 폴더로 이동한 뒤 실행한다.

```bash
python3 src/02_embed_sample.py --input src/outputs/chunked_documents_v1.jsonl
python3 src/03_vector_search.py --limit 0 \
  --query 'URM 서버 등록하는 방법' --top-k 3 --preview-chars 0
```

샘플은 처음 3개를 검사하고 저장하지 않는다. `--limit 0`은 전체 청크를 임베딩하며, `src/outputs/vectors_qwen3_<청크 수>.json`에 캐시를 만든다. 같은 입력·모델 설정이면 캐시를 재사용한다. `--limit` 기본값은 50이므로 전체 실습에는 0을 명시한다. 원문 및 캐시는 로컬에만 남는다.

### 4. 기존 벡터를 pgvector에 적재하고 정확 검색

```bash
docker compose -f src/pgvector_lab/compose.yaml up -d --wait
python3 src/pgvector_lab/04_pgvector_search.py \
  --load --cache src/outputs/vectors_qwen3_2685.json
python3 src/pgvector_lab/04_pgvector_search.py \
  --cache src/outputs/vectors_qwen3_2685.json --mode exact \
  --query 'URM 서버 등록하는 방법' --top-k 3
```

2,685는 이번 데이터의 청크 수다. 다른 입력을 쓰면 생성된 실제 캐시 파일명으로 바꾼다. 적재 시 문서 벡터는 다시 생성하지 않는다. 질문은 같은 모델로 임베딩한다. 테이블의 ID 집합과 캐시 설정이 다르면 검색을 중단하므로 같은 데이터를 사용해야 한다.

### 5. HNSW 생성 → 실제 사용 확인

```bash
docker compose -f src/pgvector_lab/compose.yaml exec -T db \
  psql -X -v ON_ERROR_STOP=1 -U rag -d rag < src/pgvector_lab/create_hnsw.sql
python3 src/pgvector_lab/04_pgvector_search.py \
  --cache src/outputs/vectors_qwen3_2685.json --mode hnsw --ef-search 40 \
  --query 'URM 서버 등록하는 방법' --top-k 3
```

`HNSW 실제 사용: True`와 인덱스 이름, 정확 검색 결과와 겹치는 개수를 확인한다. exact는 해당 트랜잭션에서 인덱스 탐색을 꺼 기준을 만들고, hnsw는 순차 탐색을 억제한 뒤 실행 계획으로 사용 여부를 검사한다. 설정은 트랜잭션 안에서만 적용한다. `last_comparison.json`은 로컬 결과이며 Git에서 제외한다.

## 구조

```text
src/
├── 01_chunk_documents.py          # 문서 구조 → 청크
├── 02_embed_sample.py             # 3개 샘플, 저장 없음
├── 03_vector_search.py            # 벡터 캐시 + Python 코사인 검색
├── bm25_lab/
│   ├── search_lab.py              # load/grep/analyze/bm25/explain
│   ├── Dockerfile                # Nori 설치
│   └── compose.yaml
└── pgvector_lab/
    ├── 04_pgvector_search.py      # 벡터 적재, exact/hnsw, 계획 확인
    ├── create_hnsw.sql
    └── compose.yaml
```

## 결과

실제 학습 중 확인한 실행 기록이다. 아래 요약에는 원문 본문·자격증명을 포함하지 않았다.

- 청킹: 문서 364개 → 본문 있는 302개 → 청크 2,685개. 빈 본문·중복 ID·본문 최대 길이 검사 통과.
- 샘플: 3개 벡터 모두 1,024차원, 유효한 숫자 확인.
- BM25: URM 질문 OR 709개 / AND 1개. 1위는 두 경우 동일하고 점수 19.422447.
- 전체 벡터: 1위 URM 초기 설정(0.6678), 2위 배포 체크리스트(0.6642), 3위 Admin 사용자 가이드(0.6583).
- JSON/DB 정확 검색: 같은 질문 벡터로 Top-k 순서 일치, 최대 점수 차이 약 `1.3e-7`.
- HNSW: 실제 인덱스 사용 확인, 이번 질문 Top-3는 정확 검색과 3/3 겹침.
- DB 측정: exact 65.023ms / HNSW 6.371ms, 약 10.2배. 별도 단일 실행 기록이며 질문 임베딩 시간 제외. 일반 성능 보장은 아니다.

## 배운 점

처음에는 임베딩을 해야 BM25도 쓸 수 있다고 생각했다. Nori는 단어 분석, BM25는 키워드 점수, pgvector는 벡터 저장·검색이라는 역할을 구분하고 나니 전체 흐름이 연결됐다.

AND는 빠짐없이 찾아주는 조건이 아니라 후보를 엄격하게 제한하는 조건이었다. 벡터 유사도가 높아도 본문이 실제 답변을 담지 않을 수 있다. HNSW에서 전체 벡터가 아래층에 있어도 일부만 방문하므로 검색을 줄일 수 있지만 최근접 결과를 놓칠 가능성이 있다.

## 다음 단계

- [ ] 같은 질문 세트로 검색 방식별 Recall@k 평가
- [ ] BM25와 벡터 순위를 RRF로 결합
- [ ] 검색 본문과 출처로 LLM 답변 생성
- [ ] 관계 질문을 남겨 4주차 지식 그래프 학습으로 연결
