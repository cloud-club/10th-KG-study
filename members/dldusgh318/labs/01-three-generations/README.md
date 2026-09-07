---
title: 검색의 세 세대 — grep / Elasticsearch BM25 / pgvector
date: 2026-09-06
tags: [inverted-index, bm25, nori, embedding, cosine-similarity, hnsw, pgvector]
status: in-progress
---

# 01. 검색의 세 세대 — 저장 구조부터 만들어보기

> 온톨로지 스터디 2주차 실습.
> 과제: **grep / Elasticsearch BM25 / pgvector 세 방식에 필요한 데이터 저장 구조를
> 파악하여 저장해오기.** 다음 스터디에서 저장한 것 보여주고 쿼리 날리기.

## 목표

**필수 — 과제 그대로:**

1. 세 방식이 각각 **요구하는 저장 구조를 파악**한다
2. 그 구조에 맞춰 **내 노션 데이터를 실제로 저장**한다
3. 스터디에서 저장한 것을 보여주고 **쿼리를 날린다**

세 방식은 결국 같은 문서를 서로 다른 자료구조로 바꿔 두는 일이다. 그 변환이
무엇을 가능하게 하고 무엇을 잃게 하는지를 남의 예제가 아니라 **내 문서**로 확인한다.

**선택 — "검색도 붙여보세요" 확장:**

질문 10개를 세 방식에 똑같이 던져 승패 표를 만든다. 어차피 쿼리를 날려봐야 하니
체계적으로 날린 셈이고, 세 방식의 **승리 구간이 서로 다르다**는 게 보이면 그게
3주차 하이브리드(BM25 + 벡터, RRF)의 근거가 된다.

## 저장 구조 대조표 — 필수 산출물

같은 청크 한 덩어리가 세 저장소에서 이렇게 변한다.

| | 0세대 grep | 1세대 Elasticsearch | 2세대 pgvector |
|---|---|---|---|
| **저장 단위** | 파일 안의 한 줄 | `_doc` (역색인 postings) | 테이블 한 행 |
| **스키마** | 없음 | 인덱스 매핑 (analyzer 지정) | `CREATE TABLE ... embedding vector(1024)` |
| **본문이 뭐가 되나** | 그대로 바이트 | 정규화된 토큰 목록 + TF/위치 | 1024개 실수 |
| **인덱스** | **없음** | inverted index | HNSW (`m=16`, `ef_construction=64`) |
| **쿼리 시 연산** | 문자열 비교 (전체 스캔) | postings 조회 + BM25 점수 | 코사인 거리 (근사 탐색) |
| **랭킹** | 없음 (이진) | BM25 점수 | 코사인 유사도 |
| **메타데이터 필터** | 불가 | `source` keyword 필드로 가능 | SQL `WHERE`로 가능 |
| **비용** | 색인 0 / 쿼리 O(n) | 색인 있음 / 쿼리 빠름 | 색인 비쌈(임베딩) / 쿼리 빠름 |
| **잘 잡는 것** | 정확한 식별자·코드·로그 | 키워드, 형태소 정규화된 한국어 | 개념·자연어 질의, 표기 변이 |
| **놓치는 것** | 조사·띄어쓰기·동의어 전부 | 사전에 없는 신조어, 의미적 동의어 | 무의미 식별자, 정확 매칭 |

한국어 때문에 1세대에서 갈림길이 하나 더 생긴다. 그래서 같은 본문을 **두 가지로 동시에 색인**해 뒀다:

| 필드 | analyzer | 특징 |
|---|---|---|
| `text` | nori (형태소) | 조사·어미를 떼고 원형을 색인. 사전 기반 |
| `text.ngram` | 2-3그램 | 사전이 필요 없는 대신 토큰이 폭발하고 노이즈가 많다 |

실제로 돌려본 결과 (`python src/gen1_es.py analyze "..."`):

```
"학교에서 지식그래프를 배웠다"
  nori  : ['학교', '지식', '그래프', '배웠', '배우']
  ngram : ['학교','학교에','교에','교에서','에서','에서 ','서 ','서 지',' 지',' 지식','지식','지식그', ...]

"엘라스틱서치 Elasticsearch ES"
  nori  : ['엘라스틱', '서치', 'elasticsearch', 'es']
```

여기서 이미 세 가지가 보인다:

1. **`학교에서 → 학교`** — 조사가 떨어졌다. 2주차 자료의 "나라의 말이 → 나라" 예시가 그대로 재현된다.
   grep은 `-w`를 주는 순간 이걸 놓치지만 1세대는 잡는다.
2. **`지식그래프 → 지식 + 그래프`인데 `지식그래프` 원형이 안 나온다.** `decompound_mode: mixed`를
   줬는데도 이렇다 — nori 사전에 "지식그래프"라는 복합명사가 없기 때문이다.
   즉 **형태소 분석기는 사전에 없는 신조어를 쪼개버린다.** n-gram 필드를 같이 둔 이유가 이것.
3. **`엘라스틱서치`와 `Elasticsearch`는 nori에서도 여전히 다른 토큰이다.**
   1세대는 한영 혼용·의미적 동의어를 끝내 해결하지 못한다 → 2세대가 필요한 지점.

## 환경

- Python 3.13
- Elasticsearch 8.15.1 + `analysis-nori` (도커)
- PostgreSQL 16 + pgvector (도커, **호스트 포트 5433** — 5432는 로컬 Postgres가 쓰는 중)
- 임베딩: `BAAI/bge-m3` (1024차원, **로컬 실행**)

임베딩을 로컬로 돌리는 이유: 코퍼스가 개인 노션 전체라서 외부 API로 보내지 않는다.
비용도 0이고, 나중에 모델을 바꿔 끼우려면 `src/common.py`의 `EMBED_MODEL`만 고치면 된다.

## 실행 방법

```bash
cd members/dldusgh318/labs/01-three-generations

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d --build          # ES(nori) + pgvector. 첫 빌드는 몇 분

python src/collect_notion.py ~/Downloads/Export-xxxx.zip   # 노션 → data/raw/
python src/chunk.py                                        # → data/processed/chunks.jsonl

python src/gen0_grep.py --stats       # 0세대: 저장 구조 확인 (적재랄 게 없음)
python src/gen1_es.py index           # 1세대: 매핑 생성 + 색인
python src/gen2_pgvector.py index     # 2세대: 임베딩 + 적재 + HNSW
```

저장 구조 확인:

```bash
python src/gen0_grep.py --stats
python src/gen1_es.py mapping
python src/gen2_pgvector.py schema
```

쿼리 (스터디 데모용):

```bash
python src/query.py "지식그래프"      # 세 방식 나란히
python src/query.py --demo            # 실패 3종 재현
```

## 구조

```
.
├── docker-compose.yml     # ES(nori) + pgvector
├── Dockerfile.es          # 공식 이미지에 nori 플러그인 설치
└── src/
    ├── common.py          # 경로·접속 정보·모델 설정
    ├── collect_notion.py  # 노션 Export(zip) → data/raw/*.md
    ├── chunk.py           # 헤딩 기준 청킹 → chunks.jsonl (세 세대 공통 입력)
    ├── gen0_grep.py       # 0세대
    ├── gen1_es.py         # 1세대 (매핑이 곧 저장 구조)
    ├── gen2_pgvector.py   # 2세대 (DDL + HNSW)
    └── query.py           # 세 방식 동시 비교
```

세 세대가 **같은 `chunks.jsonl`** 을 입력으로 받는다. 그래야 차이가 저장 구조에서
온 것이지 전처리 차이가 아니라고 말할 수 있다. (0세대만 청킹조차 안 한다 — 그게 0세대다)

## 결과 ①  적재 규모 — 필수

| | 문서/청크 수 | 저장 크기 | 색인 시간 |
|---|---|---|---|
| 0세대 grep | | | 0 (색인 없음) |
| 1세대 ES | | | |
| 2세대 pgvector | | | |

## 결과 ②  질문 10개 승패 표 (선택 확장)

`python src/query.py --table` 이 `results/comparison.md`를 만든다.
각 칸은 `히트 수 / 소요시간`이고, '판정'은 상세 결과를 눈으로 보고 채운다.

<!-- TODO: results/comparison.md 생성 후 여기에 옮겨 붙이기 -->

| # | 질문 | 유형 | 0세대 grep | 1세대 BM25 | 2세대 벡터 | 판정 |
|---|------|------|-----------|-----------|-----------|------|
| Q01 | HTTP 404 | 정확 식별자 | | | | |
| Q02 | OPENAI_API_KEY | 코드/설정 심볼 | | | | |
| Q03 | 학교 | 조사 결합 | | | | |
| Q04 | 쿠버네티스 배포 | 복합 키워드 | | | | |
| Q05 | 정처기 | 고유 축약어 | | | | |
| Q06 | 엘라스틱서치 | 한영 혼용 | | | | |
| Q07 | 지식 그래프 | 띄어쓰기 변이 | | | | |
| Q08 | 검색이 왜 어려운가 | 개념 질의 | | | | |
| Q09 | 면접에서 받은 피드백 | 자연어 질의 | | | | |
| Q10 | 성능을 개선한 경험 | 의미 검색 | | | | |

질문 10개는 유형을 고르게 섞었다. 한쪽으로 몰면 "역시 벡터가 최고" 같은
뻔한 결론만 나오고, 정작 알고 싶은 **경계선**이 안 보인다.

### 승자 판정의 한계

정답 레이블이 없어서 승패를 자동으로 매길 수 없다. 지금은 상위 결과를 눈으로 보고
판정한다. 이 한계가 그대로 다음 단계의 이유가 된다 — **골든셋이 필요하다.**

## 배운 점

<!-- TODO -->

## 다음 단계

- [ ] 골든셋을 만들어 승자 판정을 정량화 (recall@5, NDCG@10)
- [ ] nori vs n-gram 어느 쪽이 내 문서에 맞는지 (분담 주제)
- [ ] **BM25 + 벡터 하이브리드(RRF)** — 위 표에서 승리 구간이 갈렸다면 이게 다음 수순
