---
title: 카톡 대화 적재 — Postgres · pgvector · Elasticsearch (grep/BM25/벡터 3세대 비교)
date: 2026-09-09
tags: [kakaotalk, postgres, pgvector, elasticsearch, bm25, nori, embedding, kure, chunking, pii-masking]
status: done
---

# 01. 카톡 대화 적재 — Postgres · pgvector · Elasticsearch (grep/BM25/벡터 3세대 비교)

> 관련 노트: [`01-inverted-index-bm25.md`](../../notes/01-inverted-index-bm25.md) · [`02-embeddings-cosine-hnsw.md`](../../notes/02-embeddings-cosine-hnsw.md) · [`03-ddia-ch3-storage-and-search.md`](../../notes/03-ddia-ch3-storage-and-search.md)
> 상세 절차: [`GUIDE.md`](GUIDE.md) (일반) · [`RUNBOOK_mac_colima.md`](RUNBOOK_mac_colima.md) (Mac + Colima)

## 목표

W1 과제 "RDB 적재 + 임베딩 생성 + Elasticsearch 인덱싱"과 W2 실습 "같은 질문을 grep / BM25 / 벡터로 던져 비교"를 한 파이프라인으로 끝낸다.

1. 카톡 '대화 내보내기' txt(안드로이드) 2개 방을 파싱해 **정본**(`messages`)으로 적재한다.
2. 실명·전화·계좌를 **가명화/마스킹**한 뒤에만 임베딩·색인·공개한다.
3. 대화를 세션 기반 **청크**로 만들어 pgvector(KURE-v1, HNSW)와 Elasticsearch(nori, BM25)에 넣는다.
4. 같은 질문 10개 이상을 세 방식으로 던져 **누가 이기는 질문인지** 표로 남긴다 → W3 하이브리드·"못 답하는 질문 목록"의 재료.

## 환경

- 머신: MacBook Apple Silicon(arm64), 16 GiB, macOS 26.6.2
- 컨테이너: Colima 0.10.0 (VM **4 CPU / 6 GiB**, `colima list` 실측) · Docker CLI 29.1.3 / Engine 28.4.0 · Compose 5.0.2
- 저장소: `pgvector/pgvector:pg18` (Postgres 18 + pgvector 0.8.x) · Elasticsearch 9.5.3 + `analysis-nori` (커스텀 Dockerfile)
- 언어 / 런타임: Python 3.13.5 (`.venv`; PyCharm 프로젝트 인터프리터도 이 환경으로 지정)
- 주요 라이브러리: psycopg 3, elasticsearch-py 9, sentence-transformers (로컬 임베딩), python-dotenv
- 임베딩 모델: [`nlpai-lab/KURE-v1`](https://huggingface.co/nlpai-lab/KURE-v1) (bge-m3 한국어 파인튜닝, 1024차원, MIT) — API 키·비용 없음, 데이터가 노트북 밖으로 나가지 않음. OpenAI/Gemini로 바꾸려면 `.env.example` 참고
- 외부 서비스 / 키: 없음 (OpenAI 를 쓸 때만 `OPENAI_API_KEY`)

환경 값은 2026-09-09에 `colima list`, `docker version`, `.venv/bin/python`, PyTorch의 MPS 상태를 다시 측정했다. Colima는 `--cpus`·`--memory`로 VM 자원을 설정할 수 있고, Sentence Transformers는 사용 가능한 경우 MPS를 자동 선택한다([Colima](https://github.com/abiosoft/colima#customizing-the-vm), [Sentence Transformers](https://www.sbert.net/examples/sentence_transformer/applications/computing-embeddings/README.html), [PyTorch MPS](https://docs.pytorch.org/docs/stable/notes/mps.html)).

## 실행 방법

```bash
# 0) 원본 txt 를 data/raw/ 에 둔다 (커밋 금지 — .gitignore 로 제외됨)
colima start --cpus 4 --memory 6
docker compose up -d --build            # Postgres(pgvector) + Elasticsearch(nori)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt sentence-transformers
cp .env.example .env
# .env에서 EMBED_PROVIDER=local, EMBED_MODEL=nlpai-lab/KURE-v1, EMBED_DIM=1024로 변경

# 1) 방마다: 파싱 → 가명화 → Postgres 적재+청킹 → 임베딩 → ES 색인
./run_pipeline.sh "data/raw/KakaoTalkChats_ㅇ.txt" 프로젝트팀
./run_pipeline.sh "data/raw/KakaoTalkChats_팀리더단톡방.txt" 팀리더   # 두 방은 같은 name_map.json 을 공유

# 2) 비교
python src/search.py "마감 일정" --room 팀리더
python src/search.py --batch questions.txt --md > data/interim/compare.raw.md  # 원문 스니펫 포함, 커밋 금지
# compare.raw.md를 사람이 판정·비식별화해 공개용 compare.md에 반영
python src/report.py                    # 아래 '결과' 절의 통계
```

## 구조

```
01-ingest/
├── README.md                 이 문서
├── GUIDE.md                  단계별 상세 절차·트러블슈팅 (일반)
├── RUNBOOK_mac_colima.md     Mac + Colima 실행표
├── docker-compose.yml        pgvector/pgvector:pg18 + es/Dockerfile(nori)
├── es/Dockerfile
├── requirements.txt · .env.example · .gitignore · run_pipeline.sh
├── questions.example.txt     질문 작성용 예시
├── questions.txt             실제 비교 질문 10개 (단일사실 / 표현불일치 / 다중홉·집계)
├── compare.md                검색 결과를 수동 판정·비식별화한 비교표
├── data/                     raw·interim·private — 전부 커밋 제외
└── src/
    ├── parse_kakao.py        내보내기 txt/csv → JSONL (윈도우/안드로이드/iOS·맥 자동 감지)
    ├── pseudonymize.py       이름 가명화(본문 속 이름 포함) + 전화·계좌·주민번호·이메일 마스킹
    ├── chunking.py           세션(30분) → 최대 30건/700자 → 3건 겹침
    ├── load_postgres.py      rooms / members / messages(정본) / chunks
    ├── embed.py              chunks → chunk_embeddings (vector(1024), HNSW cosine)
    ├── index_es.py           kakao_chunks 인덱스 (nori mixed + n-gram 서브필드)
    ├── search.py             grep(ILIKE) / BM25 / 벡터 나란히, --batch --md 비교표
    ├── report.py             결과 통계 마크다운
    └── common.py             .env, 연결 헬퍼
```

데이터 모델: `messages`(원문 1건 1행)가 정본이고 `chunks` → `chunk_embeddings` / ES 인덱스는 언제든 다시 만들 수 있는 파생물이다. 같은 파일을 다시 넣어도 `(room_id, seq)`·`content_hash` 유니크로 중복되지 않는다.

## 결과

### 적재 결과 (2026-09-09, `src/report.py` 출력)

| 방 | 메시지 | 기간 | 발신자 | 청크 | 청크 평균 글자 | 청크당 메시지 |
|---|---|---|---|---|---|---|
| 팀리더 | 4,799 | 2023-06-30 ~ 2026-09-09 | 13 | 803 | 292 | 5.7 |
| 프로젝트팀 | 14,174 | 2023-10-27 ~ 2025-09-18 | 5 | 1,119 | 363 | 12.4 |

| 방 | text | link | media | system | deleted | empty |
|---|---|---|---|---|---|---|
| 팀리더 | 4,171 | 138 | 482 | 8 | 0 | 0 |
| 프로젝트팀 | 12,747 | 82 | 1,343 | 1 | 0 | 1 |

- Postgres 18.6 (Debian 18.6-1.pgdg12+2) · pgvector 0.8.6 · 임베딩 `nlpai-lab/KURE-v1` (local, 1024차원)
  - `chunk_embeddings` nlpai-lab/KURE-v1: 1,922행 · 인덱스 `chunk_embeddings_hnsw`, `chunk_embeddings_pkey`
- Elasticsearch 9.5.3 · 플러그인 analysis-nori 9.5.3 · `kakao_chunks` 1,922건
  - `korean` analyzer 토큰 예: `부산 여행 숙소 예약했어요` → `['부산', '여행', '숙소', '예약']`
- 청킹: 세션 간격 30분 · 최대 30건/700자 · 겹침 3건

### 세 방식 비교 — 예시 질문 "마감 일정" (팀리더 방)

| 방식 | 결과 | 왜 |
|---|---|---|
| 0세대 grep `ILIKE '%마감 일정%'` | 0건 | 두 단어가 붙어 있는 메시지가 없음. 문자열 그대로만 봄 |
| 1세대 BM25 (nori) | top-1 = 일반 일정 조율 `#1908` (7.12), 마감 논의 `#1463`은 top-2 (7.00) | 기본 `match`가 두 토큰 중 하나만 있어도 후보로 삼아 `일정`이 반복된 청크가 1위 |
| 2세대 벡터 (KURE-v1) | top-1 = 마지막 제출일 `#1653` (0.592), top-2 = 완료 기한 질문 `#1695` (0.573) | 질의 단어가 그대로 없어도 마감의 의미와 가까운 대화를 검색 |
| BM25 ∩ 벡터 | top-5 중 1개, `#1463` | 두 방식이 서로 다른 후보를 찾는다 → W3 RRF 융합의 근거 |

### 질문 10개 비교표

> 실행 조건: 두 방 전체, `k=5`, 방 필터 없음. 원문 스니펫은 공개하지 않고 청크 ID·점수·관련성 요약만 남겼다. 전체 판정 기준과 한계는 [`compare.md`](compare.md)에 기록했다. BM25 점수와 cosine 값은 서로 다른 척도이므로 숫자를 직접 비교하지 않았다.

| 질문 | grep 건수 | BM25 top-1 | 벡터 top-1 | top-5 교집합 | 누가 이겼나 |
|---|---:|---|---|---:|---|
| 회비 입금 계좌 | 0 | `#635` (9.2), 마스킹된 계좌 안내 | `#635` (0.55), 같은 청크 | 2/5 | **BM25·벡터 공동승** — 같은 정답 청크 |
| 회의록 오늘 중으로 | 1 | `#283` (31.1), 정확 문구 포함 | `#283` (0.63), 같은 청크 | 2/5 | **grep** — 정확 문구 1건이라 순위화 불필요 |
| 배포 오류 | 0 | `#1406` (8.6), 배포 오류 대화 | `#1406` (0.59), 같은 청크 | 2/5 | **BM25·벡터 공동승** — 같은 정답 청크 |
| 데이터베이스 연결 문제 | 0 | `#1182` (21.5), 연결 설정 코드 | `#478` (0.57), DB 연동 실패 원인 대화 | 2/5 | **벡터** — 문제 상황을 더 직접 검색 |
| 돈 언제까지 보내야 해 | 0 | `#613` (11.8), 무관한 작업 지시 | `#1598` (0.57), 지급·기한 안내 | 0/5 | **벡터 부분 성공** — 송금 기한 확정은 못 함 |
| 서버가 왜 안 켜져? | 0 | `#1244` (8.3), 서버 구성 자료 | `#1848` (0.64), 재부팅 뒤 서비스 비활성 대화 | 0/5 | **벡터** — 장애 증상을 직접 검색 |
| 점심 메뉴 추천해 줘 | 0 | `#1525` (7.4), 점심 언급 | `#1792` (0.60), 식사 장소 선택 대화 | 0/5 | **벡터 부분 성공** — 식사 선택 맥락을 검색 |
| 회식 장소 어디야? | 0 | `#1705` (9.0), 회식 투표 알림 | `#86` (0.55), 회식 취소 대화 | 1/5 | **셋 다 실패** — top-1에 장소 정보 없음 |
| 작년에 가장 많이 언급된 기능은 무엇이야? | 0 | `#129` (11.1), 단일 대화 | `#171` (0.44), 단일 대화 | 0/5 | **셋 다 실패** — 기간 필터와 언급 집계 필요 |
| 프로젝트팀에서 회의에 가장 많이 참여한 사람은 누구야? | 0 | `#303` (10.5), 단일 회의 청크 | `#283` (0.65), 단일 회의록 청크 | 1/5 | **셋 다 실패** — 방 필터·참여자 연결·횟수 집계 필요 |

이 비교는 10개 질문의 top-1을 사람이 판정한 소규모 정성 평가이며 Recall@k가 아니다. W3에서는 질문별 정답 청크를 먼저 라벨링한 뒤 Recall@k를 계산한다.

**셋 다 못 답한 질문(→ W3 "못 답하는 질문 목록")**: `회식 장소 어디야?`, `작년에 가장 많이 언급된 기능은 무엇이야?`, `프로젝트팀에서 회의에 가장 많이 참여한 사람은 누구야?`.

## 배운 점

- **잘 된 것**
  - 안드로이드 내보내기 형식(`2024년 3월 2일 오후 7:12, 이름 : 메시지`)을 정규식으로 파싱하고 여러 줄 메시지·시스템 메시지·미디어 자리표시자를 분류해 유형별 건수를 확인할 수 있었다.
  - 가명화를 임베딩 **앞**에 두어 로컬 모델이라도 결과물(청크 텍스트, 비교표)을 그대로 공개할 수 있게 했다. 두 방을 같은 매핑표로 처리해 같은 사람이 같은 가명을 유지한다.
  - KURE-v1이 실제로 `mps:0`을 사용함을 확인했다. 모델이 이미 캐시된 상태에서 1,922개 청크를 배치 32로 다시 임베딩한 결과, 모델 로딩 10.31초 + 인코딩 519.29초로 총 529.60초(약 8분 50초), 초당 3.70청크였다. 최초 모델 다운로드 시간은 제외한 값이다. API 비용은 0원이다.
  - 한 질문 출력에 grep 0건 / BM25 OR 매칭 / 벡터 의미 매칭 / 교집합 1개가 한눈에 보여서 "왜 하이브리드인가"가 데이터로 설명된다.
- **막혔던 것과 해결**
  - Docker 컨텍스트가 Colima인데 VM이 꺼져 있어 소켓 연결이 실패했다. `colima start --cpus 4 --memory 6`으로 다시 시작했고, 현재 `colima list`에서 4 CPU/6 GiB를 확인했다. Colima VM의 `vm.max_map_count`는 권장값 1,048,576으로 이미 설정되어 있어 별도 변경이 필요 없었다([Elastic 문서](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/vm-max-map-count)).
  - `run_pipeline.sh` 실행 권한이 zip 해제 과정에서 빠져 `command not found` → `chmod +x`. `sudo`로 돌리면 venv를 못 찾으니 쓰지 않는다.
  - Postgres 18 이미지는 볼륨을 `/var/lib/postgresql`에 마운트해야 데이터가 유지된다(`…/data`는 옛 경로).
  - 가명화 한계: 이름 뒤에 `학생`처럼 다른 명사가 바로 붙은 경우는 잡지 못했다. `_SUFFIX` 목록 보강 또는 `--extra-names`로 처리.

## 다음 단계

- [x] `questions.txt` 10개로 `compare.md`를 만들고 top-1 관련성을 수동 판정해 "누가 이겼나" 작성
- [ ] W3: BM25 + 벡터를 RRF로 융합하고 Recall@k로 키워드/벡터/하이브리드 비교 → 개인 데이터 에이전트 v1
- [ ] Recall@k 평가용 질문 30개(단일사실·표현불일치·다중홉 각 10)와 정답 청크 라벨 확정
- [ ] 분담 후보: 청킹 파라미터(`SESSION_GAP_MIN`, `CHUNK_MAX_MSGS`)를 바꿔 `--rebuild-chunks`로 재실험, nori vs `text.ngram` 비교
- [ ] `minimum_should_match` / `match_phrase` 옵션을 `search.py`에 추가해 BM25 정밀도 실험
- [ ] 가명화 후 남은 이름 점검 스크립트를 `pseudonymize.py --check`로 흡수
