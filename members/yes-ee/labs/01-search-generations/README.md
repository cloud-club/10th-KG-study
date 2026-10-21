---
title: 노션 데이터로 grep과 BM25 검색 실습
date: 2026-10-15
tags: [notion, grep, bm25, pgvector]
status: in-progress
---

# 노션 데이터로 검색 실습

모든 명령은 저장소 루트에서 실행한다. 현재는 **노션 페이지 하나를 검색 문서 하나로** 사용한다.

전체 실습 흐름:

```text
Elasticsearch 실행
→ Nori 분석 확인
→ 인덱스와 처리 규칙 생성
→ 문서 5개 등록
→ AWS 검색
→ 점수순으로 결과 확인
```

| 단계 | 진행 상태 |
|---|---|
| 원본 Markdown 5개 확보 | 완료 |
| grep 문자열 검색 | 완료 |
| Elasticsearch 실행 및 Nori 분석 확인 | 완료 |
| 인덱스 생성 및 문서 5개 등록 | 완료 |
| BM25 검색·점수순 결과 확인 | 완료 |
| 개별 점수 계산 근거 확인 (`explain`) | AWS에 일치한 문서 3개의 빈도·길이·점수 비교 완료 |
| pgvector 임베딩·적재·벡터 검색 | 미진행 |

## 1. 데이터 준비

원본은 `data/yes-ee/raw/`에 보존하고 개인 데이터는 커밋하지 않는다.
Markdown 5개를 대상으로 하며 첨부 HTML 1개와 이미지 34개는 검색 데이터에 포함하지 않았다. OCR도 수행하지 않았다.

`prepare_pages.py`로 각 Markdown의 전체 본문을 JSON에 담았다.
이때 본문은 유니코드 NFC 정규화 외에는 그대로 보존했다. 이후 고객사 이름을 가명으로 치환했다.
JSON의 필드는 `id`, `title`, `body`, `source_path`다.

현재 사용하는 파일:

```text
data/yes-ee/
├── raw/                              # 내려받은 원본
├── customer-pseudonyms.json           # 개인 고객사명 치환 매핑
└── processed/notion-pages-v1/
    ├── documents.jsonl               # 한 줄에 페이지 하나
    └── bulk.ndjson                   # Elasticsearch 일괄 등록 파일
```

사용하는 스크립트:

| 파일 | 역할 |
|---|---|
| `prepare_pages.py` | 원본 Markdown을 페이지 단위 JSONL로 변환. 출력 폴더가 이미 있으면 중단 |
| `prepare_bulk.py` | JSONL에 등록 지시를 붙여 Bulk 파일 생성. 서버 전송은 하지 않음 |
| `pseudonymize_pages.py` | 서버 문서의 고객사 이름을 치환하고 서버·JSONL·Bulk 파일 갱신 |

## 2. grep 검색

리눅스·macOS 터미널에서 사용하는 `grep` 명령어로 실습한다. 별도 DB나 인덱스는 필요 없다.
Markdown 파일을 디스크에 저장한 것으로 데이터 준비가 끝났으며, 실행할 때 파일을 읽어 검색한다.

### 원본 Markdown에서 문자열 검색

사용자가 실행한 명령:

```bash
grep -rnF --include='*.md' 'CloudFormation' data/yes-ee/raw/
```

출력 형식은 `파일경로:줄번호:일치한 줄`이다. 노션 내보내기의 긴 폴더명과 파일명이
결과마다 반복되어 읽기 어려웠다. 이 명령은 대소문자를 구분하며 정규식 대신 문자열 그대로 찾는다.
최초 실습 당시 원본 Markdown 1개에서 일치한 줄은 36줄이었다. 이는 단어의 총 등장 횟수나 문서 수가 아니다.

### 파일 경로를 숨기고 검색어 강조하기

```bash
grep -rnhF --color=always --include='*.md' 'CloudFormation' data/yes-ee/raw/ | less -R
```

| 옵션 | 역할 |
|---|---|
| `-r` | 하위 폴더까지 검색 |
| `-n` | 원본 파일의 줄 번호 표시 |
| `-h` | 파일 경로를 숨김 |
| `-F` | 정규식이 아닌 고정 문자열로 검색 |
| `--include='*.md'` | Markdown 파일만 검색 |
| `--color=always` | 파이프로 전달할 때도 검색어 색상 강조 유지 |
| `\| less -R` | 색상을 유지하며 스크롤로 읽기 |

`less`에서 방향키로 이동하고 `q`로 종료한다. 파일 경로를 숨긴 결과는 `줄번호:본문` 형식이다.
실제 원본에서 확인한 출력 중 일부는 다음과 같다. 코드 블록에는 터미널의 강조 색상이 표시되지 않는다.

```text
200:#### CloudFormation
211:    (`Type: AWS::CloudFormation::Stack`)
222:                  Type: AWS::CloudFormation::Stack
```

숫자는 원본 Markdown의 줄 번호다. 결과는 원본에 등장하는 순서이며 관련도 점수로 정렬되지 않는다.
`####`나 백틱 등 Markdown 문법은 렌더링되지 않고 그대로 출력된다.
현재는 문서가 여러 개이므로 출처를 구분하려면 `-h`를 뺀다.

### 앞뒤 문맥 함께 보기

```bash
grep -rnhF -C 2 --color=always --include='*.md' 'CloudFormation' data/yes-ee/raw/ | less -R
```

`-C 2`는 일치한 줄 앞뒤 두 줄도 표시한다. 일치한 줄은 `줄번호:내용`, 문맥 줄은
`줄번호-내용`으로 구분되며 떨어진 결과 묶음 사이에는 `--`가 나온다.
겹치는 문맥은 합쳐질 수 있다. 따라서 이 출력의 줄 수는 검색에 일치한 줄 수와 다르다.

grep은 전체 파일에서 일치하는 줄을 찾으므로 한 줄이 길면 결과도 길다.
`less`는 결과를 탐색하기 쉽게 해줄 뿐 Markdown을 문서처럼 렌더링하는 도구는 아니다.

## 3. Elasticsearch BM25 검색

### 3-1. Elasticsearch 실행

Docker Desktop 실행 후 다음 명령을 사용한다.

```bash
docker compose up -d elasticsearch
docker compose ps
```

루트 `docker-compose.yml`이 `infra/elasticsearch/Dockerfile`을 사용해 공식 Elasticsearch 이미지에
Nori 플러그인을 추가한 이미지를 만들고 실행한다. Elasticsearch 9.1.0의 `healthy` 상태를 확인했다.
BM25는 기본 제공되며 별도 설치하지 않는다. Nori는 필드별 매핑에서 사용하도록 지정한다.
아래 주소는 기본 포트 9200 기준이다. `.env`의 `ES_PORT`를 변경했다면 URL도 변경한다.

### 3-2. Nori 분석 확인

```bash
curl -sS -X POST 'http://localhost:9200/_analyze?pretty' \
  -H 'Content-Type: application/json' \
  -d '{"analyzer":"nori","text":"CloudFormation으로 Lambda를 배포한다."}'
```

![Nori 분석 결과](<assets/Pasted image 20261017221937.png>)

실제 반환된 `tokens`의 `token` 값은 `cloudformation`, `lambda`, `배포`였다.
분석 결과를 확인하는 요청이며 문서 등록 요청은 아니다. `analyzer`는 사용할 분석기,
`text`는 입력 문장이고 `?pretty`는 JSON 응답을 들여써 보여준다.

### 3-3. 인덱스와 매핑 생성

**인덱스(index)**는 Elasticsearch에서 문서를 모아두는 논리적 공간이고,
**매핑(mapping)**은 그 문서의 필드별 자료형과 처리 규칙이다.
아래 명령은 문서를 담을 인덱스를 만들면서 매핑을 함께 지정한다.
이때 만드는 인덱스와 `토큰 → 문서`를 연결하는 내부 자료구조인 역색인(inverted index)은 구분한다.

`yes-ee-notion-pages-v1` 인덱스와 아래 매핑의 생성·적용을 확인했다.
아래는 최초 생성 명령이며, 이미 생성된 인덱스에 다시 실행할 필요는 없다.

```bash
curl -sS -X PUT 'http://localhost:9200/yes-ee-notion-pages-v1?pretty' \
  -H 'Content-Type: application/json' \
  -d '{
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0
    },
    "mappings": {
      "properties": {
        "id": {"type": "keyword"},
        "title": {"type": "text", "analyzer": "nori", "similarity": "BM25"},
        "body": {"type": "text", "analyzer": "nori", "similarity": "BM25"},
        "source_path": {"type": "keyword", "index": false}
      }
    }
  }'
```

![인덱스와 매핑 생성 결과](<assets/Pasted image 20261017222351.png>)

`mappings`는 필드별 처리 규칙이다. `title`·`body`는 Nori 분석과 BM25 점수 계산을 사용하고,
`id`는 쪼개지 않는 식별값으로 다룬다. `source_path`는 출처 표시용 값을 보관하되 검색 색인은 만들지 않는다.
`settings`의 값은 로컬 단일 노드 실습용으로 기본 샤드 1개, 복제본 0개를 지정한 것이다.
성공 응답의 `acknowledged: true`를 확인한다. 이 단계는 빈 인덱스 생성이며 문서 등록은 다음 단계다.

### 3-4. 문서 등록 및 건수 확인

서버 조회로 인덱스 생성과 Nori·BM25 매핑 적용을 확인했다.
`prepare_bulk.py`를 실행해 기존 JSONL을 Bulk 등록 파일로 바꿨고, 문서 등록까지 완료했다.
현재 JSONL과 Bulk 파일은 고객사 이름을 치환한 버전이다.
각 문서의 등록 지시와 본문을 두 줄씩 기록하므로 5개 문서에 대해 10줄이다.
노션 페이지 하나가 검색 문서 하나가 된다. 아래는 등록에 사용한 명령이다.

```bash
curl --fail-with-body -sS -X POST 'http://localhost:9200/_bulk?refresh=wait_for&pretty' \
  -H 'Content-Type: application/x-ndjson' \
  --data-binary @data/yes-ee/processed/notion-pages-v1/bulk.ndjson
```

![문서 등록 결과](<assets/Pasted image 20261017223613.png>)

`--data-binary @파일경로`는 파일 내용을 전송한다. `refresh=wait_for`는 등록한 문서가 검색에
보일 때까지 기다린다. 응답의 `errors: false`와 항목별 성공 상태를 확인한다.
HTTP 요청이 성공해도 개별 문서는 실패할 수 있다. 동일 ID로 재실행하면 해당 문서를 갱신한다.

```bash
curl --fail-with-body -sS 'http://localhost:9200/yes-ee-notion-pages-v1/_count?pretty'
```

![등록 문서 수 확인](<assets/Pasted image 20261017223634.png>)

실제 확인한 결과는 `count: 5`다. 등록 시 분석·역색인 구성이 이루어지고 BM25 점수는 검색 시 계산된다.

### 3-5. 검색 및 결과 확인

`CloudFormation`은 1개 문서가 검색되어, 여러 결과의 순위를 보기 위해 `AWS`도 검색했다.
아래 요청은 본문(`body`)을 검색하고 응답을 제목·점수·총 검색 건수로 제한한다.
`curl`은 검색을 수행하는 프로그램이 아니라 Elasticsearch에 HTTP 요청을 보내는 도구다.

```bash
curl --fail-with-body -sS -X POST \
  'http://localhost:9200/yes-ee-notion-pages-v1/_search?pretty&filter_path=hits.total,hits.hits._score,hits.hits._source.title' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"match": {"body": "AWS"}},
    "_source": ["title"]
  }'
```

요청의 핵심은 **검색할 필드와 반환할 필드가 다르다**는 점이다.

| 요청 부분 | 의미 |
|---|---|
| `"match": {"body": "AWS"}` | 본문에서 AWS를 검색. 검색어도 분석기를 거쳐 토큰으로 변환 |
| `"_source": ["title"]` | 검색 결과의 원문 필드는 제목만 반환. 검색 대상은 여전히 본문 |
| `/_search` | 해당 인덱스에 검색을 요청하는 API 경로 |
| `pretty` | 응답 JSON을 줄바꿈·들여쓰기하여 표시 |
| `filter_path` | 응답에서 일치 문서 수·점수·제목만 남김. 검색 조건을 바꾸는 옵션은 아님 |
| `-H 'Content-Type: application/json'` | 요청 본문이 JSON 형식임을 서버에 알림 |
| `-d '{…}'` | 검색 조건을 담은 JSON 요청 본문 전송 |

```text
검색어 AWS → Nori 분석 → 본문의 역색인에서 후보 문서 찾기
           → BM25 점수 계산 → 점수순 정렬 → 제목과 점수 등 응답
```

실제 확인 결과(고객사 이름 치환 전 측정값이며, 아래 제목은 가명으로 표시):

| 순서 | 문서 제목 | BM25 점수 (`_score`) |
|---|---|---:|
| 1 | [고객사 A] Lambda 문의 | 1.1663128 |
| 2 | [고객사 B] 비용 최적화 관련 추가 | 0.89880633 |
| 3 | [고객사 C] 비활성화, 비용 대시보드 안내 | 0.8259328 |

`hits.total.value`는 일치 문서 수(3), `hits.hits`는 검색 결과 목록이다.
`match`는 검색어도 분석한 후 본문 토큰과 매칭하며, 기본 결과 순서는 관련도 점수 내림차순이다.
점수는 정확도나 확률이 아니다.

### 3-6. 첫 문서의 점수 계산 근거 확인

검색 요청에 `explain: true`를 추가하면 각 결과의 `_explanation`에 계산 근거가 나온다.
`size: 1`로 현재 1위 문서 하나만 확인한다. 검색어·검색 필드는 이전과 동일하다.

```bash
curl -sS -X POST \
  'http://localhost:9200/yes-ee-notion-pages-v1/_search?pretty&filter_path=hits.hits._source.title,hits.hits._score,hits.hits._explanation' \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 1,
    "explain": true,
    "query": {"match": {"body": "AWS"}},
    "_source": ["title"]
  }'
```

고객사 이름 치환 후 실제 조회한 `[고객사 A] Lambda 문의`의 결과:

| 항목 | 값 | 의미 |
|---|---:|---|
| `_score` | 1.1672001 | 해당 검색의 최종 점수 |
| `freq` | 138 | 이 문서 본문에 색인된 `aws` 토큰의 등장 횟수 |
| `n` | 3 | 본문에 `aws`가 있는 문서 수 |
| `N` | 5 | 본문 필드가 있는 전체 문서 수 |
| `idf` | 0.5389965 | n과 N으로 계산한 희귀성 가중치 |
| `dl` | 4632 | 검색에 쓰이는 본문 길이 근삿값(토큰 기준, 글자 수 아님) |
| `avgdl` | 2196.2 | 전체 문서 본문의 평균 길이 |
| `tf` | 0.9843209 | 등장 빈도 포화와 길이 보정을 반영한 항 |

현재 설명의 계산식은 `boost × idf × tf`이며 `2.2 × 0.5389965 × 0.9843209 ≈ 1.1672001`이다.
여기서 출력된 boost 2.2는 이번 기본 BM25 구현의 계수이며 사용자가 별도 가중치를 준 것은 아니다.
`k1=1.2`와 `b=0.75`도 응답에 나오며 각각 반복 효과의 포화와 길이 보정을 조절하는 값이다.
이 단일 검색어의 idf는 후보 문서들에 공통이며 문서 간 차이는 빈도·길이 항에서도 생긴다.
문서가 평균보다 길다는 이유만으로 점수가 낮다고 단정하거나, 이 한 문서만 보고 순위 원인 전체를 단정하지 않는다.

### 3-7. 같은 검색에 나온 문서들의 점수 비교

앞선 explain 요청에서 `"size": 1`을 `"size": 5`로 바꾸면 현재 AWS 검색에 일치한 문서 3개를
모두 확인할 수 있다. size는 반환할 최대 건수이며 일치하지 않는 문서를 채워주는 값이 아니다.

고객사 이름 치환 후 실제 조회한 비교 결과:

| 문서 | aws 등장 횟수 (`freq`) | 본문 길이 근삿값 (`dl`) | BM25 점수 |
|---|---:|---:|---:|
| [고객사 A] Lambda 문의 | 138 | 4632 | 1.1672001 |
| [고객사 B] 비용 최적화 관련 추가 | 3 | 1688 | 0.8911845 |
| [고객사 C] 비활성화, 비용 대시보드 안내 | 3 | 2328 | 0.83624053 |

- B와 C는 등장 횟수가 3으로 같다. B가 더 짧아 길이 보정에서 유리하며 점수도 높다.
- A는 더 길지만 등장 횟수가 많아 최종 점수가 가장 높다. 짧은 문서가 무조건 이기는 것은 아니다.
- A의 등장 횟수는 B의 46배지만 점수는 46배가 아니다. 반복 효과가 포화되며 길이도 함께 보정되기 때문이다.
- `idf=0.5389965`, `n=3`, `N=5`, `avgdl=2196.2`는 세 결과에 공통이다.
  특히 이 단일 검색어의 희귀성은 문서마다 달라지는 값이 아니다.
- 나머지 문서 2개는 본문에 `aws` 토큰이 없어 이번 match 검색 결과에 포함되지 않는다.

**등장 횟수 `freq`와 응답의 `tf` 구분**

TF를 일반적으로 단어의 등장 빈도라고 부르기도 하지만, 이번 explain 응답의 `tf`는
원래 등장 횟수인 `freq`에 **반복 효과의 포화와 문서 길이 보정까지 반영한 값**이다.

| 항목 | 고객사 A | 고객사 B | 고객사 C |
|---|---:|---:|---:|
| 등장 횟수 `freq` | 138 | 3 | 3 |
| 본문 길이 `dl` | 4632 | 1688 | 2328 |
| 보정된 `tf` | 0.9843 | 0.7516 | 0.7052 |
| 희귀성 `idf` | 0.5390 | 0.5390 | 0.5390 |

압도적으로 차이가 나는 것은 보정 전 등장 횟수 `freq`다. 보정된 `tf`의 차이는 훨씬 작다.

> A는 가장 긴 문서라 길이 보정에서는 불리하지만, AWS가 훨씬 많이 등장해서 최종 점수가 가장 높다.
> IDF는 같은 검색어와 같은 문서 집합을 기준으로 하므로 세 문서가 동일하다.
> B와 C는 등장 횟수가 같지만 B가 더 짧아서 B의 점수가 높다.

## 4. 고객사 이름 가명 처리

고객사 이름을 `고객사 A`~`고객사 D`로 치환했다. Elasticsearch의 제목·본문과
현재 적재용 JSONL·Bulk 파일을 함께 갱신했다. `source_path`는 이름을 포함하지 않는
`notion/<페이지ID>.md`로 바꿨으며, 실제 로컬 파일 위치를 뜻하지는 않는다.
원본 Markdown은 보존한다. 고객사명 치환 매핑은 Git에서 제외된
`data/yes-ee/customer-pseudonyms.json`에 두고, 아래 스크립트로 적용한다.

```bash
python3 members/yes-ee/labs/01-search-generations/pseudonymize_pages.py
```

이 스크립트는 현재 Elasticsearch 문서를 읽어 치환하고 JSONL·Bulk 파일과 서버를 갱신한다.
`prepare_pages.py`로 원본에서 JSON을 다시 만들면 원래 이름이 들어갈 수 있다.
이 스크립트는 로컬 파일이 아니라 현재 서버의 문서를 읽으므로, 원본에서 재생성한 파일을 그대로 등록하지 않도록 주의한다.
이미지 OCR이나 다른 식별정보 제거는 포함하지 않는다.

## 5. 다음 단계

기본 BM25 검색과 AWS에 일치한 문서 3개의 점수 근거 비교까지 완료했다.
다음에는 다른 검색어로 같은 현상을 관찰하거나 여러 단어 검색에서 희귀성 가중치를 비교할 수 있다.
pgvector 실습은 아직 진행하지 않았다.

참고: [Elasticsearch Bulk API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-bulk),
[Nori](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-analyzer),
[pgvector](https://github.com/pgvector/pgvector).
