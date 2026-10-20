---
title: 대화 청킹 → 로컬 임베딩 → pgvector / pg_trgm 하이브리드 검색
date: 2026-09-09
tags: [chunking, embedding, pgvector, pg-trgm, hybrid-search, sentence-transformers]
status: done
---

# 02. 대화 청킹 → 로컬 임베딩 → pgvector / pg_trgm 하이브리드 검색

> 관련 노트: `../../notes/02-chunking.md`, `../../notes/03-embedding-models.md`, `../../notes/04-hybrid-search.md`
> 앞 실습: [01-kakao-ingest](../01-kakao-ingest/README.md) 로 `kakao.messages` 가 차 있어야 합니다.

## 목표

카톡 메시지는 중앙값이 6자("ㅋㅋ", "ㅗ")라 한 건씩 임베딩하면 검색이 안 된다.
연속 메시지를 "한 대화" 로 묶은 청크를 만들고, 로컬 한국어 SBERT 로 임베딩해 pgvector 에 넣고,
같은 청크에 pg_trgm 인덱스도 걸어 벡터 / 트라이그램 / 하이브리드(RRF) 검색을 비교한다.

개인 대화라 외부 임베딩 API 는 쓰지 않는다. 모델은 Mac MPS 에서 돌아간다.

## 환경

- Python 3.11+, `sentence-transformers`, `psycopg` (uv 가 임시 설치)
- 모델: `jhgan/ko-sroberta-multitask` (KLUE-RoBERTa 기반 한국어 SBERT, 768차원, 입력 128토큰)
- DB: 레포 루트 `docker compose up -d postgres` (pgvector 0.8, pg_trgm)

## 실행 방법

레포 루트에서:

```bash
set -a; . ./.env; set +a
# 셸 함수로 (zsh 는 "$VAR" 를 공백으로 안 나눠서 변수 방식은 안 됨)
kg() { uv run --with 'sentence-transformers>=3' --with 'psycopg[binary]' "$@"; }

# 청킹 + 임베딩 + 적재 (방 전체, 약 1분 반)
kg members/sese2204/labs/02-kakao-chunk-embed/src/embed.py
#   --max-chars 300 --gap-minutes 60      # 청킹 조절
#   --model intfloat/multilingual-e5-small --recreate   # 다른 모델 (차원이 바뀌면 --recreate)

# 검색
kg members/sese2204/labs/02-kakao-chunk-embed/src/search.py "홍천 닭갈비" -k 5            # hybrid (기본)
kg members/sese2204/labs/02-kakao-chunk-embed/src/search.py "머리 자른 얘기" --mode vector
kg members/sese2204/labs/02-kakao-chunk-embed/src/search.py "수강신청" --mode trgm

# 테스트
python3 -m unittest discover -s members/sese2204/labs/02-kakao-chunk-embed/src
```

## 구조

```
src/
├── chunker.py        # 메시지 → 청크. 순수 함수 (시간 간격 / 글자 수 / 개수 경계, 최소 글자 필터)
├── embed.py          # CLI: kakao.messages(text) → 청크 → 임베딩 → kakao.chunks + HNSW·trgm 인덱스
├── search.py         # CLI: vector / trgm / hybrid(RRF) 검색
├── test_chunker.py   # 청커 단위 테스트 10개
└── requirements.txt
```

청킹 규칙 (`chunker.py`): 아래 중 하나라도 걸리면 새 청크.

1. 앞 메시지와 **30분** 넘게 떨어짐 (대화가 끊김)
2. 글자 수가 **모델 입력 길이 × 1.3자/토큰** 을 넘음 (128토큰 → 166자)
3. 메시지 **60개** 초과

본문은 `이름: 내용` 줄을 `\n` 로 이은 것. 내용 합이 10자 미만이면 버린다.

테이블 `kakao.chunks`:

| 컬럼 | 뜻 |
|------|-----|
| `chunk_idx` | 방 안 순서 |
| `start_seq`, `end_seq` | 원본 `kakao.messages.seq` 범위. 원문으로 되돌아갈 때 |
| `started_at`, `ended_at`, `message_count` | 대화 시간대와 크기 |
| `text` | 청크 본문. `gin_trgm_ops` 인덱스 |
| `model` | 임베딩 모델 이름 |
| `embedding` | `vector(768)`, L2 정규화 → `<=>` 가 코사인 거리. HNSW 인덱스 |

검색 (`search.py`):

- **vector**: `ORDER BY embedding <=> 질문벡터`. 청크 1.2만 개면 플래너가 순차 스캔(74ms)을 고르므로 이 질의에서만 `SET LOCAL enable_seqscan = off` → HNSW Index Scan (1.8ms)
- **trgm**: `WHERE 질문 <% text ORDER BY word_similarity(질문, text)` → 질문이 본문 어딘가에 "비슷하게" 들어 있는지. GIN Bitmap Scan
- **hybrid**: 둘의 상위 2k 를 RRF `1/(60+rank)` 로 합침

## 결과

| 항목 | 값 |
|------|-----|
| 입력 | 텍스트 메시지 134,813건 (사진·링크·시스템 제외) |
| 청크 | 11,985개, 평균 11.2개 메시지 / 146자 |
| 토큰 초과로 잘림 | 90개 (0.8%) |
| 임베딩 | M4 Pro MPS, 51초 (초당 약 240청크) |
| 전체 | 86초 (모델 로드 5초 포함) |

검색 예 (상위 3):

- `수강신청` trgm → 그 단어가 든 대화 세 개가 word_similarity 1.0 / 1.0 / 0.8
- `머리 자른 얘기` vector → 미용실·펌·머리 밀기 얘기 세 개 (코사인 0.53 / 0.51 / 0.50). 단어가 안 겹쳐도 잡힘
- `홍천 닭갈비` hybrid → 닭갈비집 얘기 두 개와 그 식당 지도 공유 청크가 1위

## 배운 점

- **단위가 전부다.** 메시지 단위는 임베딩할 게 없다. 30분 간격 + 글자 수로 묶으니 청크 하나가 "그때 그 얘기" 가 된다.
- 모델 입력 길이(128토큰)에 맞춰 청크 크기를 정해야 한다. 1.5자/토큰으로 잡으니 5% 가 잘렸고, ㅋㅋㅋ·이모지·영어 때문에 실제 비율이 낮다. 1.3 으로 내리니 0.8%.
- pg_trgm 은 `similarity` 보다 `word_similarity` 가 맞다. 짧은 질문 vs 긴 본문이면 `similarity` 는 0.3 임계값을 못 넘는다.
- 첫 검색 결과에 `sha256해시.jpg` 줄이 섞여 나왔다. 안드로이드 내보내기가 첨부를 파일명으로 남긴 것. 파서를 고쳐(01) 1,099건을 photo/voice/video 로 뺐다.
- HNSW 인덱스가 이미 있으면 COPY 가 인덱스를 거쳐 느려진다(66초 → 86초). 대량 재적재면 인덱스를 지웠다 만드는 게 낫다.
- pgvector 는 테이블이 작으면 HNSW 를 안 탄다. 1.2만 행에서 순차 스캔 74ms vs 인덱스 1.8ms 인데도 플래너는 순차 스캔. `EXPLAIN ANALYZE` 로 확인하고 질의 단위로 `enable_seqscan` 을 끄는 게 pgvector 문서가 권하는 방법.

## 다음 단계

- [ ] `intfloat/multilingual-e5-small`(512토큰) 과 비교. 더 긴 청크가 검색에 유리한지
- [ ] Elasticsearch nori BM25 를 세 번째 검색기로 붙여 RRF 3-way
- [ ] 리랭커(05 노트) 로 상위 20 → 5 재정렬
- [ ] 청크에서 인물·장소·사건을 뽑아 Neo4j 그래프로
