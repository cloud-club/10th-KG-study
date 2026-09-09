---
title: 채팅 데이터를 세 가지 검색 방식으로 저장하고 검색하기
date: 2026-09-09
tags: [grep, elasticsearch, bm25, pgvector, vector-search]
status: done
---

# 02. 채팅 데이터를 세 가지 검색 방식으로 저장하고 검색하기

> 관련 노트: `../../notes/02-search-generations.md`

## 목표

같은 채팅 데이터와 `수강 신청`이라는 질의를 다음 세 방식으로 검색하고, 각 방식이 무엇을 잡고 놓치는지 비교한다.

1. grep 문자열 매칭
2. Elasticsearch BM25 키워드 검색
3. pgvector 코사인 유사도 검색

## 환경

- 언어 / 런타임: Python 3.13
- 주요 라이브러리: Elasticsearch Python Client 8.15.1, psycopg 3.2.10
- 검색 서버: Elasticsearch 8.15.0 + Nori, PostgreSQL 16 + pgvector
- 임베딩: Ollama 0.33.0, `bge-m3` 1024차원
- 컨테이너 실행: Docker Compose
- 외부 서비스 / 키: 없음



>개인 채팅 원문을 외부 서비스로 전송하지 않기 위해 `bge-m3`를 Ollama에서 로컬로 실행했다. 
> 검색 품질이나 처리 속도가 부족하면 OpenAI Embeddings API 같은 외부 API로 교체할 수 있다. 다만 동일한 평가 질의와 Precision@5로 먼저 품질을 비교하고, 개인 대화는 익명화하거나 외부 전송 가능 여부를 확인해야 한다. 모델을 바꾸면 문서와 질의를 모두 같은 모델로 다시 임베딩해야 한다.

## 실행 방법

아래 명령은 `members/e0ng/labs/02-search-generations/`에서 실행한다.

### 1. 환경 준비

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

mkdir -p data/raw
# 원본 CSV를 data/raw/chat.csv에 복사
```

원본 CSV에는 `Date`, `User`, `Message` 열이 필요하다. 실제 채팅 원본과 생성 데이터는 개인정보 보호를 위해 Git에서 제외했다.

### 2. CSV 파싱

```bash
python src/parse_chat.py data/raw/chat.csv --last-month
python -m unittest discover -s tests -v
```

- `--last-month`는 데이터의 마지막 날짜를 기준으로 직전 달만 추출해 다음 파일을 만든다.

  - `data/processed/chat-last-month.json`: 세 방식이 공유하는 파싱 결과
  - `data/processed/chat-last-month.tsv`: grep용 한 메시지 한 줄 데이터

- CSV에서 큰따옴표로 감싼 줄바꿈은 하나의 메시지로 읽는다. 
- `Date`와 `User`가 모두 비어 있고 `Message`만 있는 행도 직전 메시지에 이어 붙인다. 
- TSV에서는 메시지 내부 줄바꿈을 `\n`으로 치환한다.

### 3. grep 검색

```bash
bash src/grep/search.sh "수강 신청" data/processed/chat-last-month.tsv
```

- `src/grep/search.sh`에서 고정 문자열과 줄 번호를 찾는 `grep -Fn`을 사용한다.

### 4. Elasticsearch BM25 검색

```bash
docker compose up -d --build --wait
curl http://localhost:9200/_cat/plugins?v

python src/elasticsearch-bm25/index_messages.py \
  --input data/processed/chat-last-month.json
python src/elasticsearch-bm25/search.py "수강 신청" --limit 10
```

- `message`는 Nori를 사용하는 `text`, `sender`는 `keyword`, `timestamp`는 `date`로 저장한다. 
- 색인 스크립트는 `chat-messages` 인덱스를 새로 만들어 중복 적재를 막고, Elasticsearch가 준비될 때까지 최대 90초간 기다린다.

### 5. pgvector 검색

```bash
ollama pull bge-m3

python src/pgvector/index_messages.py \
  --input data/processed/chat-last-month.json \
  --window-minutes 5
python src/pgvector/search.py "수강 신청" --limit 10
```

같은 발신자가 5분 이내에 연속으로 보낸 메시지를 하나의 청크로 합친다. 각 청크는 `bge-m3`로 임베딩하고 HNSW 인덱스가 있는 `vector(1024)` 컬럼에 저장한다. 색인 중에는 배치별 진행률과 예상 남은 시간을 출력한다.


### 6. 검색 시간 측정

```bash
time bash src/grep/search.sh "수강 신청" data/processed/chat-last-month.tsv
time python src/elasticsearch-bm25/search.py "수강 신청" --limit 10
time python src/pgvector/search.py "수강 신청" --limit 10
```

최초 실행은 모델 로딩과 연결 준비 시간이 포함되므로 한 번 예열한 뒤 3회 실행한 중앙값을 사용한다.

## 구조

```text
02-search-generations/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
├── data/
│   ├── raw/chat.csv                    # 직접 넣기, Git 제외
│   └── processed/                      # 파싱 결과, Git 제외
├── src/
│   ├── common.py
│   ├── parse_chat.py
│   ├── grep/search.sh
│   ├── elasticsearch-bm25/
│   │   ├── Dockerfile
│   │   ├── index_messages.py
│   │   └── search.py
│   └── pgvector/
│       ├── schema.sql
│       ├── index_messages.py
│       └── search.py
└── tests/test_parse_chat.py
```

파싱된 공통 데이터는 다음 구조의 JSON 배열이다.

```json
{
  "timestamp": "2025-02-12T09:21:44",
  "sender": "홍길동",
  "message": "수강신청하려고"
}
```

| 방식 | 저장 구조 | 검색 기준 |
|---|---|---|
| grep | 한 메시지 한 줄의 TSV | 원문 문자열 일치 |
| Elasticsearch | `timestamp: date`, `sender: keyword`, `message: text(nori)` | BM25 관련도 |
| pgvector | 발신자·시간·청크 원문·1024차원 벡터 | 코사인 유사도, HNSW |

## 결과

### 데이터

- 범위: 2026-08-01 이상, 2026-09-01 미만
- 파싱된 메시지: 9,491개
- Elasticsearch 문서: 9,491개
- pgvector 청크: 4,774개
- 청크당 원본 메시지: 평균 1.99개
- CSV 파서 테스트: 4개 통과

### 검색 결과

| 방식 | 결과 수 | 상위 5개 관련성 | Precision@5 | 첫 관련 결과 순위 | 검색 시간 |
|---|---:|---|---:|---:|---:|
| grep | 0 | 결과 없음 | 0.0 | 없음 | 6.2ms |
| BM25 | 17 | 0, 1, 1, 1, 0 | 0.6 | 2위 | 116.8ms |
| pgvector | 상위 10 | 1, 1, 1, 1, 1 | 1.0 | 1위 | 204.4ms |

grep은 붙여 쓴 `수강신청`을 찾지 못해 `수강 신청` 질의로는 0건이었다. 띄어쓰기를 뺀 `수강신청`으로 다시 검색하면 5건이 나온다.

```text
Precision@5 = 상위 5개 중 관련 결과 수 / 5
```

Recall@5는 지난달 전체 데이터에서 `수강 신청`과 관련된 모든 메시지를 판정한 정답셋이 없으므로 측정하지 않았다. 다음 단계에서 질의를 추가할 때 함께 정답셋을 만들면 Recall@5도 측정할 수 있다.

검색 시간은 명령 전체를 예열한 뒤 3회 실행한 중앙값이다. 서로 다른 검색 방식의 점수는 범위와 의미가 다르므로 직접 비교하지 않고, 같은 방식 안에서 순위를 해석했다.

| 세부 수치 | 결과 |
|---|---|
| Nori 질의 분석 | `수강`, `신청` |
| BM25 상위 5개 점수 | 15.727858, 13.651941, 12.060130, 9.779546, 8.770057 |
| pgvector 상위 5개 코사인 유사도 | 0.718704, 0.676578, 0.631877, 0.619440, 0.606128 |
| BM25 내부 검색 시간 중앙값 | 2ms |
| pgvector 질의 임베딩 시간 중앙값 | 32.4ms |
| pgvector DB 검색 시간 중앙값 | 1.9ms |

## 배운 점

- grep은 `수강 신청`을 0건, `수강신청`을 5건 찾았다. 띄어쓰기처럼 작은 표현 차이도 놓치는 문자열 매칭의 한계가 드러났다.
- BM25는 Nori가 질의를 `수강`, `신청`으로 분석해 17건을 찾았다. 붙여 쓴 표현도 찾았지만 상위 5개 중 2개는 검색 의도와 관련이 없어 문맥까지 구분하지는 못했다.
- pgvector는 상위 5개가 모두 검색 의도와 관련 있었다. 이번 질의에서는 직접적인 문자열 일치보다 의미 유사도가 더 정확한 상위 결과를 만들었다.


## 다음 단계

- [ ] 서로 다른 성격의 질의 2~3개와 정답셋을 추가해 결과 반복성과 Recall@5 확인
- [ ] `--window-minutes 0`과 `5`를 비교해 청킹이 검색 품질에 미치는 영향 확인
- [ ] 필요하면 개인정보를 익명화한 뒤 외부 임베딩 API와 검색 품질 비교
- [ ] 실습 종료 후 `docker compose down`으로 컨테이너 종료
