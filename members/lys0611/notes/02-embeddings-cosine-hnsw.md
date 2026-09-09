---
title: 임베딩·코사인 유사도·HNSW — 벡터 검색(2세대)의 원리와 pgvector
date: 2026-09-09
tags: [embedding, cosine-similarity, ann, hnsw, pgvector, kure, bge-m3, dense-retrieval]
status: done
---

# 02. 임베딩·코사인 유사도·HNSW — 벡터 검색(2세대)의 원리와 pgvector

> 참고 자료:
> - Malkov & Yashunin, [Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs](https://arxiv.org/abs/1603.09320) (arXiv 2016 / IEEE TPAMI 2018) — HNSW 원 논문
> - [pgvector README](https://github.com/pgvector/pgvector) — 연산자, HNSW 옵션, 인덱스 차원 제한
> - [nlpai-lab/KURE](https://github.com/nlpai-lab/KURE) — 실습에 쓴 한국어 임베딩 모델
> - Reimers & Gurevych, Sentence-BERT (2019) — bi-encoder 임베딩의 출발점
> - 실습: [labs/01-ingest](../labs/01-ingest/README.md) 의 `chunk_embeddings` 테이블

## 한 줄 요약

임베딩은 텍스트를 "뜻이 가까우면 각도가 가까운" 벡터로 바꾸고, 검색은 질문 벡터와 각도가 가장 작은(코사인이 큰) 청크를 찾는 일이다. 전부 비교하면 문서 수에 비례해 느리므로 HNSW 같은 **근사(ANN)** 인덱스로 "거의 맞는 답"을 빨리 찾는다. 단어가 하나도 겹치지 않아도 잡는다는 게 1세대와의 결정적 차이다.

## 핵심 개념

- **dense embedding**: 문장 하나 → 고정 길이 실수 벡터(KURE-v1 1024차원). 같은 모델로 만든 벡터끼리만 비교할 수 있다.
- **코사인 유사도** `cos = (a·b) / (|a||b|)`. 벡터를 정규화하면 내적과 같아진다. pgvector의 `<=>`는 **코사인 거리 = 1 − cos**.
- **ANN**: 정확한 최근접(k-NN)은 O(N·d). HNSW는 다층 그래프를 탐욕적으로 내려가며 로그 스케일로 찾는다. 대가는 "약간의 재현율 손실".
- **HNSW 파라미터**: `m`(노드당 연결 수), `ef_construction`(빌드 시 후보 폭), `ef_search`(질의 시 후보 폭). pgvector 기본값 16 / 64 / 40.
- **청킹이 임베딩 품질을 결정**: 카톡 1건("ㅋㅋ")은 벡터가 될 게 없다. 검색 단위는 대화 조각.

## 상세 정리

### 1. 임베딩이 하는 일

- **bi-encoder**: 질문과 문서를 각각 독립적으로 인코딩해 벡터 하나씩 만든다. 문서 벡터는 미리 계산해 저장하고, 질의 때는 질문 하나만 인코딩하면 되므로 빠르다. (반대편의 cross-encoder/리랭커는 쌍을 함께 넣어 정확하지만 느리다 → 후속 주차.)
- 벡터 공간에서 "가깝다"는 학습 데이터가 정의한다. 검색용 모델은 (질문, 정답 문서) 쌍은 가깝게, 오답(hard negative)은 멀게 학습된다. KURE-v1은 bge-m3를 한국어 질의-문서 쌍 약 200만 개와 하드 네거티브로 파인튜닝한 모델이다.
- **비대칭 모델 주의**: e5 계열은 `query: `/`passage: ` 접두어를 붙여야 하고, Gemini는 `task_type=RETRIEVAL_QUERY/DOCUMENT`를 구분한다. bge-m3·KURE는 접두어가 없다. 실습 `embed.py`가 제공자별로 이 차이를 처리한다.

### 2. 코사인 유사도와 pgvector 연산자

```
cos(a, b) = (a · b) / (|a| · |b|)        ∈ [-1, 1]
정규화 후 |a| = |b| = 1  →  cos = a · b
코사인 거리 = 1 − cos                     ∈ [0, 2]
```

| pgvector 연산자 | 뜻 | 인덱스 opclass | 언제 |
|---|---|---|---|
| `<=>` | 코사인 거리 | `vector_cosine_ops` | 텍스트 임베딩 기본 선택 (크기 무시, 각도만) |
| `<->` | L2(유클리드) 거리 | `vector_l2_ops` | 크기가 의미 있는 데이터 |
| `<#>` | **음의** 내적 | `vector_ip_ops` | 정규화된 벡터에서 가장 싼 계산. Postgres가 ASC 인덱스 스캔만 지원해 부호를 뒤집어 반환 |
| `<+>` | L1(맨해튼) | `vector_l1_ops` | 특수 용도 |

- **연산자와 opclass가 다르면 인덱스를 안 탄다.** `vector_cosine_ops`로 만든 인덱스는 `<=>` 쿼리에만 쓰인다.
- 실습은 모든 벡터를 L2 정규화해 저장한다. 그래서 `1 - (embedding <=> q)`가 그대로 코사인 유사도이고, 원하면 `<#>`로 바꿔도 순위가 같다.
- 코사인 값의 절대 크기는 모델마다 다르다. KURE-v1에서 0.59가 "좋은 매칭"이어도 다른 모델의 0.59와 비교할 수 없다. 임계값(threshold)을 정할 때는 내 데이터·내 모델에서 분포를 보고 정한다.

### 3. 왜 근사(ANN) 인덱스가 필요한가 — HNSW

정확한 검색은 질문 벡터와 모든 청크 벡터를 다 비교한다(N개 × d차원). 청크 수천 개면 밀리초라 상관없지만, 수백만이면 초 단위가 된다.

HNSW(Hierarchical Navigable Small World)는 논문 요약 그대로: 계층적으로 중첩된 근접 그래프(층)를 점진적으로 만들고, 각 원소가 올라갈 최상위 층을 지수적으로 감쇠하는 확률로 무작위 선택한다. 그 결과 위층은 성기고 긴 연결(먼 거리를 한 번에), 아래층은 촘촘한 짧은 연결이 된다. 검색은 최상위 층에서 시작해 탐욕적으로 가까운 노드로 이동하고, 층을 내려가며 반복한다. 이 구조가 로그 스케일 복잡도를 준다.

| 파라미터 | 뜻 | pgvector 기본 | 올리면 |
|---|---|---|---|
| `m` | 층별 노드당 최대 연결 수 | 16 | 재현율↑, 메모리·빌드 시간↑ (논문은 5~48 범위 권장) |
| `ef_construction` | 빌드 때 유지하는 후보 목록 크기 | 64 | 그래프 품질↑, 빌드 느려짐 |
| `hnsw.ef_search` | 질의 때 유지하는 후보 목록 크기 | 40 | 재현율↑, 지연↑. **LIMIT 보다 커야** 그만큼 돌아온다 |

pgvector에서 알아둘 것:
- 인덱스를 만들면 **정확 검색과 결과가 달라질 수 있다**(근사). 재현율은 `SET enable_indexscan = off`로 정확 검색을 돌려 비교하면 측정된다. 소규모(수천 청크)에서는 거의 차이가 없지만, W2 키워드 "HNSW"를 몸으로 익히기 위해 인덱스를 걸어 두었다.
- 인덱스는 데이터를 넣은 **뒤에** 만드는 편이 빠르다. IVFFlat과 달리 학습 단계가 없어 빈 테이블에도 만들 수 있다.
- `vector` 타입은 최대 16,000차원이지만 HNSW/IVFFlat 인덱스는 2,000차원까지. 3,072차원 모델은 차원을 줄이거나 `halfvec`(2바이트, 4,000차원까지 색인)을 쓴다.
- **필터 + HNSW**: `WHERE room = …`를 붙이면 인덱스가 먼저 k개를 뽑고 필터를 거쳐 결과가 모자랄 수 있다. pgvector 0.8의 `hnsw.iterative_scan = 'relaxed_order'`가 이 경우 스캔을 이어가 채운다. 실습에서 `--room` 필터 결과가 적으면 `hnsw.ef_search`를 올리거나 이 옵션을 켜 본다.

### 4. 모델 선택 — 왜 KURE-v1인가

| 모델 | 차원 | 비용 | 한국어 | 비고 |
|---|---|---|---|---|
| **nlpai-lab/KURE-v1** (로컬) | 1024 | 0 | 특화 (bge-m3 한국어 파인튜닝) | MIT, 시퀀스 8192, 데이터가 노트북 밖으로 안 나감 |
| BAAI/bge-m3 (로컬) | 1024 | 0 | 다국어 상위 | KURE의 베이스 |
| OpenAI text-embedding-3-small | 1536 (MRL로 축소 가능) | $0.02 / 1M 토큰 | 다국어 | API 기본 미학습 정책 |
| Gemini gemini-embedding-001 | 3072 (768/1536 MRL) | $0.15 / 1M 토큰 | 다국어 상위 | 무료 티어는 학습에 사용될 수 있어 개인 데이터 부적합 |

이번 실습은 KURE-v1(로컬)로 했다. 이유: 비용 0, 개인 대화가 외부로 나가지 않음, 한국어 검색 벤치마크에서 다국어·상용 모델보다 좋은 결과. 단점은 첫 실행 시 ~2.2GB 다운로드와 CPU/MPS 시간. Apple Silicon에서는 sentence-transformers가 MPS를 자동 선택해 수천 청크를 몇 분에 처리했다.

### 5. 청킹 — 벡터 품질의 절반은 여기서 결정된다

- 카톡 1건은 평균 10~20자. 그대로 임베딩하면 "ㅋㅋ", "ㅇㅇ"이 벡터가 된다.
- 실습의 단위: **30분 이상 끊기면 새 세션 → 세션 안에서 최대 30건/700자 → 인접 청크 3건 겹침**. 청크 머리에 `[방] 날짜(요일) 시각 · 참여: 이름들`을 붙여 "그날 저녁", "누구랑" 같은 맥락이 벡터에 들어가게 했다.
- 사진·이모티콘·시스템 메시지는 청크 본문에서 제외(정본 `messages`에는 남김).
- 파라미터는 `.env`로 바꾸고 `--rebuild-chunks`로 다시 만든다 → 분담 과제 "청킹 전략이 검색 결과에 미치는 영향"의 실험 장치.

### 6. 내 데이터에서 본 것 — "마감 일정"

- 벡터 top-1은 "제출일"을 논의하는 청크(cos 0.59), top-2는 "언제까지 완성하면 되는지" 묻는 청크(0.57). 질문 단어 `마감`, `일정`이 하나도 없는데 잡혔다. 이것이 표현 불일치를 넘는 2세대의 힘.
- 반면 BM25 top-1(투표 공지)은 벡터 top-5에 없다. 두 방식의 교집합은 청크 1개. 각자 다른 것을 잡는다 → 3주차 RRF(순위 융합)의 근거.
- 벡터가 지는 질문도 있다: 고유명사·숫자·정확한 문구("레포 주소", 특정 날짜)는 BM25가 낫다. 임베딩은 "대충 그런 얘기"를 잡고 "정확히 그것"에는 약하다.

## 예시 / 코드

```sql
-- 질문 벡터 q 와 가까운 청크 5개 (코사인). e.embedding <=> q 는 거리(작을수록 가까움)
SET hnsw.ef_search = 100;                      -- 기본 40, LIMIT 보다 크게
SELECT c.id, 1 - (e.embedding <=> %(q)s::vector) AS cos, left(c.text, 80)
FROM chunk_embeddings e JOIN chunks c ON c.id = e.chunk_id
WHERE e.model = 'nlpai-lab/KURE-v1'
ORDER BY e.embedding <=> %(q)s::vector
LIMIT 5;

-- 근사 vs 정확 비교 (재현율 측정)
BEGIN; SET LOCAL enable_indexscan = off;  /* 같은 쿼리 */  COMMIT;
```

```python
import numpy as np
def cosine(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
# 정규화된 벡터라면 cosine == a @ b
```

## 궁금한 점 / 더 알아볼 것

- [ ] 우리 데이터에서 HNSW 재현율은 얼마인가 — `enable_indexscan=off`와 top-10 겹침 비율로 측정 (3주차 Recall@k 평가셋 재료)
- [ ] KURE-v1 vs text-embedding-3-small: 같은 질문 30개로 Recall@10 비교 (분담 "임베딩 모델 비교")
- [ ] MRL 차원 축소(1536→512)가 카톡 검색에서 얼마나 손해인가
- [ ] 청크 헤더(날짜·참여자)가 임베딩을 돕는가 방해하는가 — 헤더 없는 버전과 A/B

## 스터디에서 나눌 이야기

- "코사인 0.59는 좋은 건가?" — 절대값이 아니라 분포로 보는 이유
- 벡터가 이긴 질문/진 질문의 공통점 정리해 비교표 만들기
- HNSW를 소규모에서 굳이 쓰는 이유(학습)와 쓰지 말아야 할 때(정확도가 중요한 소량 데이터)
