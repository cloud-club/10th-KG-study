---
title: 청크 데이터로 grep, BM25, pgvector, HNSW 비교
date: 2026-09-30
tags: [rag, bm25, elasticsearch, nori, embedding, pgvector, hnsw]
status: done
---

# 02. 검색의 세 세대 비교

> 관련 노트: [청킹부터 BM25, pgvector, HNSW까지](../../notes/02-search-methods.md)

## 목표

같은 청크를 문자열·키워드·벡터로 검색하고, 전체 비교와 HNSW 근사 탐색의 차이를 확인한다. 3주차의 RRF 결합, LLM 답변 생성과 Recall 평가는 별도 폴더에서 이어간다.

## 환경

- macOS / Python 3(표준 라이브러리만 사용), Docker Compose
- Ollama / `qwen3-embedding:0.6b` / 벡터 1,024차원
- Elasticsearch 8.19.21 + Nori, `127.0.0.1:19200`
- PostgreSQL 17 + pgvector 0.8.6, Docker 내부 `psql`로 접속

기존 로컬 실습을 보존하기 위해 저장소 루트 공용 인프라 대신 실습에 사용한 Compose를 함께 둔다. 루트 Compose와 포트·버전·DB 설정이 다르다. 아래 명령은 이 실습 폴더 안에서 실행한다. Compose 프로젝트 이름이 기존 로컬 실습과 같으므로 같은 호스트에서는 같은 컨테이너·볼륨을 사용한다. 로컬 학습용 인증 설정이다.

회사 데이터셋과 벡터 캐시는 공개 저장소에 포함하지 않는다. 사용 권한이 있는 입력 파일을 저장소 루트 `data/sunghyun/normalized_documents_with_path.jsonl`에 직접 둔다. 데이터가 다르면 아래 결과 개수와 순위도 달라진다.

## 실행 방법

### 입력 형식

입력은 한 줄에 문서 하나를 둔 JSONL이다. `document_id`와 `sections[].blocks`가 필요하며, 제목·문서 경로·섹션 경로는 검색 문맥에 쓰인다. 원본 없이 흐름을 확인하려면 직접 만든 아래 문서를 포함해 최소 3개 청크가 생성되도록 준비한다. 실제 평가 Q1~Q6은 원래 데이터에만 해당한다.

```json
{"document_id":"demo-1","title":"서버 등록","document_path":["가이드","서버"],"sections":[{"heading":"등록 방법","section_path":["등록 방법"],"blocks":[{"type":"paragraph","text":"서버 관리 화면에서 등록 버튼을 누르고 서버 정보를 입력한다."}]}]}
```

### 1. 문서 → 청크

저장소 루트에서 실습 폴더로 이동한다.

```bash
cd members/sunghyun/labs/02-search-lab
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

## 후속 실습

RRF 결합, 답변 생성과 Recall 평가는 [3주차 실습](../03-hybrid-rag/README.md)으로 분리했다.

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

아래는 기존 로컬 데이터로 실행해 기록한 결과다. 2026-10-01 정비에서는 Python 문법·CLI 옵션·캐시 전달을 점검했으며, 비공개 데이터와 DB·모델이 없어 검색 성능 실험을 다시 실행하지 않았다.

- 청킹: 문서 364개 → 본문 있는 302개 → 청크 2,685개. 빈 본문·중복 ID·본문 최대 길이 검사 통과.
- 샘플: 3개 벡터 모두 1,024차원, 유효한 숫자 확인.
- BM25: URM 질문 OR 709개 / AND 1개. 1위는 두 경우 동일하고 점수 19.422447.
- 전체 벡터: 1위 URM 초기 설정(0.6678), 2위 배포 체크리스트(0.6642), 3위 Admin 사용자 가이드(0.6583).
- JSON/DB 정확 검색: 같은 질문 벡터로 Top-k 순서 일치, 최대 점수 차이 약 `1.3e-7`.
- HNSW: 실제 인덱스 사용 확인, 이번 질문 Top-3는 정확 검색과 3/3 겹침.
- DB 측정: exact 65.023ms / HNSW 6.371ms, 약 10.2배. 별도 단일 실행 기록이며 질문 임베딩 시간 제외. 다른 질문이나 데이터에서도 같은 차이가 나는지는 더 비교해야 한다.

## 배운 점

처음에는 BM25도 임베딩이 필요하다고 생각했다. 실습해 보니 Nori로 단어를 나누고 BM25로 점수를 매기는 검색과, 임베딩한 벡터끼리 비교하는 검색이 따로 있었다.

AND로 바꾸니 709개였던 결과가 1개로 줄었다. 조건을 좁히면 관련 문서도 빠질 수 있다는 점을 알게 됐다. 벡터 검색에서는 본문이 거의 없는 청크가 2위로 나와서 문서 경로와 소제목도 같이 살펴봤다. HNSW는 전체를 비교하지 않아 빨랐고, 이번 질문의 상위 3개는 정확 검색과 같았다.

## 다음 단계

- [x] 같은 질문 세트로 검색 방식별 Recall@k 평가
- [x] BM25와 벡터 순위를 RRF로 결합
- [x] 검색 본문과 출처로 LLM 답변 생성
- [x] 관계 질문을 4주차 지식 그래프 이론 학습으로 연결 — [4주차 노트](../../notes/04-knowledge-graph-background.md)
- [ ] 실제 W3 질문의 근거를 그래프로 표현하고 검색 누락과 사실 부족 구분
- [ ] 공개 예제 데이터로 전체 DB·모델 실행 재현
