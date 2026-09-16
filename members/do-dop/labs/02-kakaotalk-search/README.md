---
title: 카카오톡 검색 비교
date: 2026-09-10
tags: [grep, elasticsearch, bm25, nori, pgvector, hnsw]
status: done
---

# 02. 카카오톡 검색 비교

같은 카카오톡 대화를 세 가지 방식으로 검색해 결과가 어떻게 달라지는지 비교했다.

| 방식 | 검색 기준 | 저장 위치 |
|---|---|---|
| grep | 원문 문자열 일치 | TXT 파일 |
| Elasticsearch BM25 | 토큰 일치와 관련도 점수 | Elasticsearch |
| pgvector | 임베딩 사이의 코사인 유사도 | PostgreSQL |

```text
kakao-talk.txt
├─ grep으로 원문 검색
│
└─ parse_kakao.py
   └─ messages.jsonl
      ├─ Elasticsearch
      │  ├─ nori / 2-gram 역색인
      │  └─ BM25 검색
      │
      └─ PostgreSQL + pgvector
         ├─ 1분 이내 연속 메시지 청킹
         ├─ bge-m3 임베딩
         └─ 코사인 유사도 검색
```

관련 노트: [grep에서 벡터 검색까지](../../notes/02-search-generations.md)

## 데이터와 개인정보

카카오톡에서 내보낸 TXT는 `data/do-dop/`에 저장한다. 원본과 가공 결과는 개인정보를 포함할 수 있어 Git에 커밋하지 않는다.

```text
data/do-dop/
├── kakao-talk.txt
├── processed/
│   └── messages.jsonl
└── results/
    ├── grep-counts.tsv
    ├── bm25-counts.tsv
    └── pgvector-scores.tsv
```

`parse_kakao.py`는 다음 두 날짜 형식을 읽는다.

```text
YYYY. M. D. 오전/오후 H:MM, 작성자 : 메시지
YYYY. M. D. HH:MM, 작성자 : 메시지
```

여러 줄 메시지는 하나의 `text`로 합치고, 작성자명은 `user-001`과 같은 ID로 바꾼다.

익명 ID는 이름으로 계산한 고정값이 아니다. 파일에서 처음 등장한 순서대로 번호를 붙이므로 원본이나 메시지 순서가 바뀌면 같은 사람이 다른 ID를 받을 수 있다. 여러 파일에서 같은 사람을 연결하려면 별도의 고정 매핑이 필요하다.

## 환경

- PostgreSQL 17 + pgvector
- Elasticsearch 9 + analysis-nori
- Ollama + `bge-m3` 1024차원 임베딩
- Python 3.9
- Elasticsearch 인덱스: `do-dop-kakao-messages`
- PostgreSQL 테이블: `do_dop_kakao_chunks`

Elasticsearch와 PostgreSQL은 저장소 루트의 Docker Compose로 실행한다. 하나의 로컬 인스턴스를 여러 실습에서 재사용하므로 이름 충돌을 막기 위해 `do-dop` 접두사를 붙였다. 다른 사람의 컴퓨터와 데이터를 공유한다는 뜻은 아니다.

개인 대화를 외부 서비스로 보내지 않기 위해 임베딩 모델도 로컬 Ollama에서 실행한다.

## 실행 순서

명령은 저장소 루트에서 시작한다.

### 1. 인프라 실행

```bash
cp .env.example .env
docker compose up -d
bash infra/check.sh
```

### 2. 카카오톡 파싱

```bash
python3 members/do-dop/labs/02-kakaotalk-search/src/parse_kakao.py \
  --input data/do-dop/kakao-talk.txt \
  --output data/do-dop/processed/messages.jsonl
```

### 3. grep 검색

검색어 하나의 일치 줄 수를 확인한다.

```bash
bash members/do-dop/labs/02-kakaotalk-search/src/search_grep.sh \
  data/do-dop/kakao-talk.txt '합주'
```

원문이 필요할 때만 `--show`를 붙인다.

```bash
bash members/do-dop/labs/02-kakaotalk-search/src/search_grep.sh \
  --show data/do-dop/kakao-talk.txt '합주'
```

`queries.tsv`의 모든 질의를 실행한다.

```bash
bash members/do-dop/labs/02-kakaotalk-search/src/run_grep_queries.sh \
  data/do-dop/kakao-talk.txt \
  members/do-dop/labs/02-kakaotalk-search/config/queries.tsv \
  data/do-dop/results/grep-counts.tsv
```

### 4. Elasticsearch BM25 검색

파싱된 메시지를 Elasticsearch에 색인한다. 메시지 하나가 문서 하나가 된다.

```bash
cd members/do-dop/labs/02-kakaotalk-search/src

python3 index_es.py \
  --input ../../../../../data/do-dop/processed/messages.jsonl \
  --recreate
```

검색어 하나를 nori와 2-gram 필드에서 각각 확인한다.

```bash
python3 search_es.py '합주' --field text
python3 search_es.py '합주' --field text.ngram
```

단어 순서까지 맞는 문서를 찾으려면 `--match-phrase`를 사용한다.

```bash
python3 search_es.py '합주 언제' --field text --match-phrase
```

두 분석기가 문장을 어떻게 나누는지도 확인할 수 있다. 실제 대화 대신 직접 만든 예시를 권장한다.

```bash
python3 analyze_tokens.py '다음 합주곡 정하자'
```

모든 질의를 두 필드에서 실행한다.

```bash
python3 run_es_queries.py \
  --queries ../config/queries.tsv \
  --output ../../../../../data/do-dop/results/bm25-counts.tsv

cd -
```

### 5. pgvector 검색

PostgreSQL 연결에 필요한 패키지와 Ollama 모델을 준비한다.

```bash
ollama pull bge-m3

cd members/do-dop/labs/02-kakaotalk-search
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

같은 사람이 1분 안에 연속으로 보낸 메시지를 묶고, 청크마다 임베딩을 만들어 저장한다.

```bash
python3 src/index_pgvector.py \
  --input ../../../../data/do-dop/processed/messages.jsonl \
  --recreate
```

`--window-minutes`의 기본값은 1이다. `0`을 주면 메시지를 묶지 않는다.

검색어 하나를 확인한다.

```bash
python3 src/search_pgvector.py '다음 모임 날짜' --size 5
```

원문 일부가 필요할 때만 `--show`를 붙인다.

```bash
python3 src/search_pgvector.py '우리 팀명 뭐였지?' --size 5 --show
```

모든 질의를 실행한다.

```bash
python3 src/run_pgvector_queries.py \
  --queries config/queries.tsv \
  --output ../../../../data/do-dop/results/pgvector-scores.tsv

cd -
```

### 6. 테스트

```bash
python3 -m unittest discover \
  -s members/do-dop/labs/02-kakaotalk-search/tests \
  -p 'test_*.py'

bash members/do-dop/labs/02-kakaotalk-search/tests/test_search_grep.sh
```

## 파일별 역할

| 파일 | 역할 |
|---|---|
| `config/queries.tsv` | 세 방식에서 공통으로 사용할 질의와 실험 목적 |
| `src/parse_kakao.py` | 카카오톡 TXT를 익명화된 JSONL로 변환 |
| `src/search_grep.sh` | 검색어 하나를 원본 TXT에서 검색 |
| `src/run_grep_queries.sh` | 모든 질의를 grep으로 실행하고 결과 저장 |
| `src/index_es.py` | nori·2-gram 설정으로 Elasticsearch 문서 색인 |
| `src/analyze_tokens.py` | 두 분석기가 만든 토큰 비교 |
| `src/search_es.py` | 검색어 하나를 BM25로 검색 |
| `src/run_es_queries.py` | 모든 질의를 두 Elasticsearch 필드에서 실행 |
| `src/chunking.py` | 짧은 연속 메시지를 벡터 검색용 청크로 결합 |
| `src/embed_ollama.py` | Ollama에서 텍스트 임베딩 생성 |
| `src/schema.sql` | pgvector 테이블과 HNSW 인덱스 생성 |
| `src/index_pgvector.py` | 청킹, 임베딩, PostgreSQL 저장 수행 |
| `src/search_pgvector.py` | 검색어 하나를 코사인 유사도로 검색 |
| `src/run_pgvector_queries.py` | 모든 질의를 pgvector로 실행하고 결과 저장 |

## 실습에 필요한 개념

### 질의 type

`queries.tsv`의 `type`은 질의의 성격을 기록한 실험용 분류다. grep 명령어나 Elasticsearch의 고정 문법은 아니다. 단, `phrase` 질의는 Elasticsearch 실험에서 `match_phrase`로 실행한다.

| type | 의미 | 예시 |
|---|---|---|
| `exact` | 원문에 있는 단어나 표현 | `합주`, `예약` |
| `common` | 자주 등장하는 단어 | `곡`, `시간` |
| `phrase` | 단어 순서까지 확인할 표현 | `합주 언제` |
| `partial` | 완성된 표현의 일부 | `정하` |
| `semantic` | 원문과 달라도 의미가 가까운 표현 | `다음 모임 날짜` |

### grep

grep은 원본 TXT를 위에서부터 읽으며 검색 문자열이 있는 줄을 찾는다. 파싱된 JSONL을 사용하지 않는 이유는 여러 줄 메시지 결합과 익명화로 원본의 줄 구조가 달라지기 때문이다.

```text
장점: 단순하고 결과를 예상하기 쉬움
한계: 띄어쓰기와 표현이 달라지면 찾기 어려우며 관련도 순위가 없음
```

### nori와 2-gram

nori는 한국어 형태를 고려해 문장을 검색 토큰으로 나눈다. 2-gram은 의미를 해석하지 않고 연속된 두 글자씩 나눈다.

```text
합주예약
→ 합주 / 주예 / 예약

정하자
→ 정하 / 하자
```

2-gram은 부분 입력이나 사전에 없는 이름을 찾는 데 유용하다. 반면 한 글자 검색어에는 토큰을 만들 수 없고, 의미 없는 글자 조각도 생긴다.

### Elasticsearch 인덱스와 역색인

`index_es.py`는 먼저 `do-dop-kakao-messages`라는 저장·검색 공간을 만든다. 여기에 분석기와 필드 규칙을 등록한 뒤 메시지를 넣는다.

```text
Elasticsearch 문서 1개
├─ chunk_id
├─ sender_id
├─ sent_at
└─ text 원문
```

Elasticsearch는 같은 `text`를 두 방식으로 분석한다.

```text
text       → nori 토큰으로 역색인
text.ngram → 2-gram 토큰으로 역색인
```

원문은 `_source.text`에 그대로 남고, 토큰은 어떤 단어가 어느 문서에 있는지 찾기 위한 역색인에 기록된다. 검색할 때 전체 문서를 다시 읽지 않고 이 역색인을 조회한다.

### `match`와 `match_phrase`

둘 다 Elasticsearch Query DSL의 쿼리 종류다.

`match`는 검색어를 토큰화한 뒤 기본적으로 하나라도 일치하는 문서를 후보로 가져온다.

```text
합주 언제
→ 합주 또는 언제가 있는 문서
```

`match_phrase`는 토큰의 순서와 위치까지 확인한다.

```text
합주 언제
→ 합주 다음에 언제가 이어지는 문서
```

### BM25 점수

BM25는 다음 요소를 이용해 후보 문서의 순위를 정한다.

- 문서 안에서 검색어가 얼마나 자주 나오는가
- 전체 문서에서 그 검색어가 얼마나 드문가
- 문서가 얼마나 긴가

같은 단어가 반복돼도 점수가 끝없이 비례해서 오르지는 않는다. 이를 TF 포화라고 한다.

```text
BM25 점수
= 단어의 희귀도(IDF)
  × 반복 횟수를 완만하게 반영한 값(TF 포화)
  × 문서 길이 보정
```

BM25 점수는 확률이 아니다. 같은 질의와 같은 필드 안에서 문서 순서를 비교하는 값이다. nori와 2-gram은 토큰 통계가 다르므로 두 필드의 점수 절댓값도 바로 비교하면 안 된다.

### 청킹과 임베딩

Elasticsearch에서는 메시지 하나를 문서 하나로 저장했다. 벡터 검색에서는 너무 짧은 메시지에 문맥이 부족할 수 있어 같은 사람이 1분 안에 연속으로 보낸 메시지를 하나로 묶었다.

```text
우리 팀명
오늘 정해야함
추천한거
고기서고기

↓ 1분 청킹

하나의 content
```

`bge-m3`는 청크의 `content`를 1024차원 임베딩으로 바꾼다. PostgreSQL에는 원문과 벡터를 한 행에 함께 저장한다.

```text
do_dop_kakao_chunks
├─ chunk_id
├─ sender_id
├─ started_at / ended_at
├─ message_count
├─ content
└─ embedding VECTOR(1024)
```

질의도 같은 모델로 임베딩한 뒤 `<=>` 연산자로 코사인 거리를 계산한다. 코사인 거리가 작은 청크부터 가져오고, 화면에는 `1 - 거리`로 계산한 코사인 유사도를 보여준다.

HNSW는 저장된 벡터가 많을 때 가까운 후보를 빠르게 찾기 위한 pgvector 인덱스다. Elasticsearch의 역색인이 토큰을 찾는 구조라면 HNSW는 가까운 벡터를 찾는 구조다.

## 실험 결과

### 데이터 규모

| 항목 | 수량 |
|---|---:|
| 원본 TXT | 1,322줄 |
| 파싱된 메시지 | 1,203개 |
| Elasticsearch 문서 | 1,203개 |
| 1분 기준 pgvector 청크 | 637개 |
| 청크당 평균 메시지 | 약 1.89개 |

5분 기준에서는 618개 청크가 만들어졌다. 1분으로 줄이자 19개가 늘어 약 3.1% 차이가 났다. 이 대화방에서는 대부분의 연속 메시지가 1분 안에 작성된 것으로 보인다.

### 세 방식 비교

grep과 BM25는 일치한 줄 또는 문서 수를 기록했다. pgvector는 항상 가까운 결과를 반환하므로 1위 코사인 유사도를 기록했다. BM25 점수와 코사인 유사도는 서로 다른 값이므로 직접 비교할 수 없다.

| 질의 | grep 줄 | BM25 nori 문서 | BM25 2-gram 문서 | pgvector 1위 유사도 |
|---|---:|---:|---:|---:|
| 합주 | 31 | 21 | 31 | 0.6803 |
| 곡 | 38 | 27 | 0 | 0.6572 |
| 합주 언제 | 1 | 1 | 1 | 0.6872 |
| 정하 | 5 | 12 | 5 | 0.5149 |
| 다음 모임 날짜 | 0 | 3 | 3 | 0.6177 |
| 예약 | 11 | 11 | 11 | 0.6393 |
| 언제 | 3 | 3 | 3 | 0.6644 |
| 시간 | 13 | 13 | 13 | 0.6511 |
| 정하자 | 4 | 25 | 13 | 0.7298 |
| 몇시 | 5 | 75 | 5 | 0.8499 |
| 몇 시 | 1 | 75 | 0 | 0.8058 |

주요 차이는 다음과 같다.

- grep은 정확한 문자열 검색에서는 예측하기 쉬웠지만 `다음 모임 날짜`처럼 표현이 달라지면 찾지 못했다.
- BM25 nori는 활용형과 띄어쓰기 차이를 넓게 찾았다. 기본 `match`의 OR 조건 때문에 `정하자`, `몇시`, `몇 시`에서는 후보가 크게 늘었다.
- BM25 2-gram은 `합주`, `정하`, `몇시`에서 grep과 비슷한 결과를 냈다. 한 글자인 `곡`과 공백으로 나뉜 `몇 시`는 토큰을 만들지 못했다.
- pgvector는 `몇시`와 `몇 시`를 모두 비슷하게 찾았다. 다만 항상 상위 결과를 반환하므로 유사도만으로 정답이라고 판단할 수는 없다.

### 자연어 질문: 우리 팀명 뭐였지?

```text
우리 팀명 뭐였지?
```

| 방식 | 결과 | 팀명 확인 |
|---|---|---|
| grep | 0줄 | 같은 문장이 없어 실패 |
| BM25 nori | 74문서, `우리 팀명`이 1위 | 답이 다른 메시지에 있어 바로 확인하기 어려움 |
| BM25 2-gram | 28문서, 팀명 표현이 상위에 등장 | 답이 다른 메시지에 있어 바로 확인하기 어려움 |
| pgvector | 팀명 논의 청크가 상위에 등장 | `고기서고기` 확인 가능 |

grep은 질문 전체와 같은 문자열이 없어 실패했다. BM25는 관련 질문을 찾았지만 메시지 하나가 문서 하나라서 뒤에 이어진 팀명과 분리됐다.

pgvector에서는 1분 청킹 덕분에 `우리 팀명`이라는 주제와 `고기서고기`라는 이름이 같은 결과에 포함됐다. 이후의 `고기서고기 하자`, `고기서고기로 말했어`라는 대화까지 확인해 최종 팀명을 알 수 있었다.

현재 프로그램은 관련 청크를 검색하는 단계까지만 구현되어 있다. `우리 팀명은 고기서고기였어`처럼 자연어로 답하려면 검색 결과를 LLM에 전달하는 RAG 단계가 필요하다.

### 자연어 질문: 우리 마지막 합주가 몇시였더라?

```text
우리 마지막 합주가 몇시였더라?
```

| 방식 | 결과 |
|---|---|
| grep | 0줄 |
| BM25 nori | 180문서, 비슷한 질문이 1위 |
| BM25 2-gram | 64문서, 직접적인 표현이 1위 |
| pgvector | 비슷한 질문이 1위, 코사인 유사도 0.7685 |

세 방식 모두 실제 시간을 바로 답하지는 못했다. 검색된 것은 비슷한 질문이었고, 답변이 다른 발신자의 다음 메시지에 있다면 현재의 같은 발신자 기준 청킹에서는 별도 청크가 되기 때문이다.

이 문제를 해결하려면 검색된 메시지의 앞뒤 대화를 함께 가져오거나, 여러 발신자의 질문과 답변을 하나의 대화 청크로 묶는 방법이 필요하다.

## 배운 점

- grep은 검색할 때마다 원문을 훑지만, Elasticsearch는 저장할 때 역색인을 만들어 검색 시 바로 조회한다.
- 토크나이저 선택에 따라 같은 검색어의 결과 수와 순위가 크게 달라진다.
- 2-gram은 부분 문자열에 유리하지만 한 글자 검색과 공백에 약하다.
- nori와 BM25는 한국어 표현을 넓게 찾지만 기본 OR 검색은 후보를 지나치게 늘릴 수 있다.
- 임베딩 검색은 띄어쓰기와 표현 변화에 덜 민감하지만 결과가 있다는 사실만으로 정답이라고 할 수 없다.
- 검색 품질은 검색 방식뿐 아니라 어떤 범위를 한 문서나 청크로 묶는지에도 영향을 받는다.
- 비슷한 대화를 검색하는 것과 질문에 대한 답을 생성하는 것은 다른 단계다. 자연어 답변에는 RAG가 필요하다.