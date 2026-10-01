---
title: 카톡 내보내기 → RDB 적재 → 임베딩 → Elasticsearch 색인
date: 2026-09-09
tags: [kakaotalk, postgres, pgvector, elasticsearch, bm25, embedding, chunking, pii-masking]
status: in-progress
---

# Lab 01 — 카톡 내보내기 → RDB 적재 → 임베딩 → Elasticsearch 인덱싱

W1 과제("RDB 적재 + 임베딩 생성 + Elasticsearch 인덱싱")와 W2 실습("grep / BM25 / pgvector 세 방식으로
같은 질문 던져 비교")을 한 번에 끝내는 파이프라인이다. 카톡 파일을 아직 내보내지 않은 상태에서 시작한다.

```
카톡 앱 ─내보내기─▶ data/raw/*.txt ─parse─▶ interim/*.jsonl ─mask─▶ *.masked.jsonl
                                                                        │
                                             ┌──────────────────────────┴───────────────┐
                                             ▼                                          │
                                   Postgres (rooms / members / messages)  ← 정본         │
                                             │ chunking                                 │
                                             ▼                                          │
                                   Postgres chunks ──embed──▶ chunk_embeddings(pgvector) │ 2세대 벡터
                                             └────────────index_es──▶ ES kakao_chunks    │ 1세대 BM25
                                   messages.text ILIKE '%…%'                             │ 0세대 grep
```

폴더 구조

```
kakao-kg-lab01/
├── README.md                 ← 이 문서 (일반 절차)
├── RUNBOOK_mac_colima.md     Mac + Colima 환경 실행표 (경로·명령이 lys0611 기준으로 채워져 있음)
├── docker-compose.yml        Postgres(pgvector) + Elasticsearch(nori)   ※ 스터디 템플릿이 있으면 그걸 우선
├── es/Dockerfile             ES 공식 이미지 + analysis-nori 플러그인
├── requirements.txt, .env.example, .gitignore
├── questions.example.txt     비교용 질문 목록 예시
├── run_pipeline.sh           4~8단계를 한 번에 (./run_pipeline.sh "data/raw/방*.txt" 방)
├── data/
│   ├── raw/        카톡 원본 (gitignore)
│   ├── interim/    파싱·가명화 결과 (gitignore)
│   └── private/    실명→가명 매핑표 (gitignore)
└── src/
    ├── parse_kakao.py    1. 내보내기 txt/csv → JSONL (윈도우/안드로이드/iOS·맥/CSV 자동 감지)
    ├── pseudonymize.py   2. 이름 가명화 + 전화·계좌·주민번호 마스킹
    ├── load_postgres.py  3. Postgres 적재 + 청킹
    ├── embed.py          4. 임베딩 → pgvector (OpenAI / Gemini / 로컬 모델)
    ├── index_es.py       5. Elasticsearch 색인 (nori)
    ├── search.py         6. grep vs BM25 vs 벡터 비교, 마크다운 표 생성
    ├── chunking.py       청킹 로직 (순수 함수)
    └── common.py         .env 로딩, DB/ES 연결
```

---

## 0. 준비물

| 항목 | 비고 |
|---|---|
| Docker Desktop | 설정 → Resources → **Memory 4GB 이상** (Elasticsearch 권장). Linux면 `sudo sysctl -w vm.max_map_count=262144` |
| Python 3.11+ | 3.12 권장 |
| 임베딩 API 키 | OpenAI 또는 Gemini 중 하나. 키 없이 하려면 로컬 모델(bge-m3/KURE) 옵션 |
| 카톡 방 선택 | 오프라인 활동이 반복되는 5~10명 단톡방, 1년 이상, 텍스트 위주 (지난 답변 참고) |

---

## 1. 카톡 대화 내보내기 (기기별)

내보내기는 **채팅방 단위**로 한다. 결과는 텍스트 파일이고 사진·영상·이모티콘은 `사진`, `이모티콘` 같은 자리표시자만 남는다.

**안드로이드**
1. 채팅방 → 우측 상단 `≡` → 채팅방 서랍 우측 하단 `⚙ 설정` → **대화 내용 내보내기**
2. `텍스트만 보내기` 선택 → 메일/드라이브/카톡(나에게)로 전송 → PC에 저장
   - `모든 메시지 내부저장소에 저장`을 고르면 사진까지 같이 저장되며 대화는 **CSV(Date,User,Message)** 로 나오는 버전이 있다. 이 CSV도 파서가 읽는다.
   - 저장 위치: `내 파일 → 내장 메모리 → KakaoTalk → Chats → KakaoTalk_Chats_…`

**아이폰**
1. 채팅방 → `≡` → `⚙ 설정`(채팅방 관리) → **대화 내용 내보내기**
2. `텍스트 메시지만 보내기` → 공유 시트에서 메일·AirDrop·"파일에 저장" → PC로

**PC (Windows/Mac)**
1. 채팅방 → `≡` → `대화 내용` → **대화 내보내기** → 저장 위치 지정 → `.txt`
2. ⚠ PC 카톡에는 **PC에 동기화된 범위의 대화만** 있다. 처음 설치했거나 오래 안 켰다면 옛 대화가 비어 있으니, 오래된 기록이 필요하면 **폰에서 내보내기**가 확실하다. (폰 `대화 백업` → PC `복원` 후 내보내기도 가능, 텍스트는 무료)

**공통 주의**
- 대화가 많은 방은 파일이 **여러 개로 분할**될 수 있다. 전부 `data/raw/` 에 넣고 뒤에서 glob(`"data/raw/여행모임*.txt"`)으로 한 번에 읽는다.
- 파일명은 `방이름_내보낸날짜.txt` 처럼. 방 이름은 이후 `--room` 값으로 계속 쓴다.
- **원본은 절대 커밋하지 않는다.** 이 폴더의 `.gitignore` 와 스터디 레포의 `.gitignore` 모두 `data/raw/` 를 제외한다.
- 방 멤버들에게 "스터디용으로 가명 처리해서 쓴다"고 한 줄 알리고 동의를 받아 두자.

파일 앞부분이 아래 셋 중 하나면 정상이다.

```
# 안드로이드                                   # iOS / Mac                          # Windows PC
여행모임 4 님과 카카오톡 대화                   2024년 3월 2일 토요일                 --------------- 2024년 3월 2일 토요일 ---------------
저장한 날짜 : 2024년 4월 20일 오후 9:27         2024. 3. 2. 오후 7:12, 김철수 : 부산   [김철수] [오후 7:12] 부산 언제 갈까
2024년 3월 2일 오후 7:12, 김철수 : 부산 언제 갈까
```

---

## 2. 인프라 띄우기 (Postgres + pgvector, Elasticsearch + nori)

스터디에서 배포한 `docker-compose` 가 있으면 그것을 쓴다. 다만 두 가지는 확인한다.

```bash
curl -s "localhost:9200/_cat/plugins?v"     # analysis-nori 가 보여야 한다. 없으면 아래 es/Dockerfile 방식으로 설치
docker exec -it <postgres컨테이너> psql -U <user> -d <db> -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

템플릿이 없거나 직접 띄우려면:

```bash
docker compose up -d --build        # 첫 실행: ES 이미지(~1GB) + nori 플러그인 다운로드
docker compose ps                   # postgres, elasticsearch 둘 다 (healthy)
curl -s localhost:9200 | head -5     # {"name": ..., "version": {"number": "9.5.3", ...}}
curl -s "localhost:9200/_cat/plugins?v"
docker exec -it kg-postgres psql -U kg -d kg -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extversion FROM pg_extension WHERE extname='vector';"
```

설계 메모
- Elasticsearch 공식 이미지에는 한국어 형태소 분석기 **nori 가 없다**. `es/Dockerfile` 이 `elasticsearch-plugin install analysis-nori` 를 이미지에 굽는다. 플러그인 버전은 ES 버전과 정확히 같아야 해서 이미지 태그(9.5.3)를 바꾸면 그대로 따라간다.
- `xpack.security.enabled=false`: 로컬 실습이라 인증/TLS를 끈다. 그래야 `http://localhost:9200` 로 바로 붙는다.
- `pgvector/pgvector:pg18` 은 Postgres 18 기반. **18부터 데이터 경로가 바뀌어 볼륨을 `/var/lib/postgresql` 에 마운트**해야 한다(`…/data` 에 마운트하면 재시작 때 데이터가 사라짐).

---

## 3. 파이썬 환경

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # 열어서 API 키와 EMBED_* 값을 채운다
```

`.env` 의 임베딩 옵션 (하나만 선택)

| provider | model / dim | 비용·특징 |
|---|---|---|
| `openai` | `text-embedding-3-small` / 1536 | $0.02 / 1M 토큰. 3만 메시지 전체를 임베딩해도 수십 원 수준. 기본값 |
| `gemini` | `gemini-embedding-001` / 768·1536·3072 | $0.15 / 1M 토큰, AI Studio 무료 티어 있음. MRL 이라 768로 줄이면 저장 1/4. `pip install google-genai` |
| `local` | `nlpai-lab/KURE-v1` 또는 `BAAI/bge-m3` / 1024 | 키 불필요, 한국어 검색 특화(KURE는 bge-m3 한국어 파인튜닝). 첫 실행 시 모델 ~2GB 다운로드, CPU면 수천 청크에 수십 분. `pip install sentence-transformers` |

W2 분담 과제 "임베딩 모델 2~3개 비교"를 맡았다면, `EMBED_MODEL` 만 바꿔 `embed.py` 를 다시 돌리면 같은 청크에 모델별 임베딩이 나란히 쌓인다(테이블 PK 가 `(chunk_id, model)`). 단 **차원이 다르면** 테이블을 새로 만들어야 한다(아래 트러블슈팅).

---

## 4. 파싱: txt → JSONL

```bash
python src/parse_kakao.py "data/raw/여행모임*.txt" --room 여행모임 --out data/interim/여행모임.jsonl
```

출력 예

```
[parse] 여행모임_2024-04-20.txt: 31,204건 (android)
[done] 31,204건 → data/interim/여행모임.jsonl
  기간: 2022-05-01T09:12:00 ~ 2024-04-20T21:20:00
  유형: {'text': 24810, 'media': 4102, 'link': 1188, 'system': 604, 'deleted': 500}
  발신자 상위: [('김철수', 9021), ('이영희', 7712), ...]
```

확인 포인트
- **건수와 발신자 목록**이 앱에서 보는 것과 대체로 맞는가. 발신자에 이상한 문자열이 섞였다면 `이름 : 메시지` 구분 실패이므로 해당 줄을 찾아 보자.
- 여러 줄 메시지가 이어 붙었는가(`text` 안에 `\n`).
- `msg_type`: `text`(본문) / `link`(URL만) / `media`(사진·이모티콘·파일) / `deleted` / `system`(입장·퇴장). 청킹·임베딩은 `text`+`link` 만 쓴다. 나머지는 DB에만 남는다.
- "형식을 인식하지 못했습니다" 가 뜨면 파일 첫 15줄이 함께 출력된다. 그 줄을 보고 `parse_kakao.py` 의 정규식을 손보거나 공유해 달라.

---

## 5. 가명화 + 개인정보 마스킹 (LLM API 에 보내기 전에, 레포에 올리기 전에)

```bash
python src/pseudonymize.py data/interim/여행모임.jsonl \
    --out data/interim/여행모임.masked.jsonl --map data/private/name_map.json
```

- 발신자 실명 → 가명(`김하람`, `이도윤`, …). **본문 속 이름도 같은 가명**으로 바뀐다: `철수형 시간 되나` → `하람형 시간 되나`, `지우야` → `준우야`.
- `data/private/name_map.json` 을 열어 마음에 드는 가명으로 고치고 다시 실행하면 그대로 반영된다. 이 파일은 실명이 들어 있으니 **절대 커밋 금지**(`.gitignore` 포함).
- 방에 없는 제3자 실명이 자주 나오면 `--extra-names 홍길동 김아무개` 로 추가.
- 마스킹: 휴대폰·유선 전화, 주민등록번호, 카드번호, 하이픈 포함 10~16자리(계좌 추정), 하이픈 없는 10~14자리 숫자열, 이메일 → `[전화번호]` 같은 토큰.
- 한계: 별명·초성(`ㅊㅅ`)·주소·직장명은 자동으로 못 잡는다. 아래처럼 한 번 훑고 필요한 건 `--extra-names` 나 수동으로.

```bash
grep -oE "01[016789]-?[0-9]{3,4}-?[0-9]{4}" data/interim/여행모임.masked.jsonl | head   # 남은 전화번호가 있나
```

이 단계가 있어야 이후 임베딩(API 전송)·발표 화면·깃허브 공개가 안전해진다.

---

## 6. Postgres 적재 + 청킹

```bash
python src/load_postgres.py data/interim/여행모임.masked.jsonl --room 여행모임
```

만들어지는 테이블

| 테이블 | 역할 | 한 행 |
|---|---|---|
| `rooms` | 방 | 방 1개 |
| `members` | 방별 발신자(가명) | 사람 1명 |
| `messages` | **정본**. 원문 메시지 그대로 (`sent_at`, `sender_id`, `msg_type`, `text`) | 메시지 1건 |
| `chunks` | 검색 단위 대화 조각. 임베딩·ES 인덱스는 이 테이블에서 파생된다 | 청크 1개 |

청킹 규칙(`.env` 로 조정): 앞 메시지와 **30분 이상** 떨어지면 새 세션 → 세션 안에서 **최대 30건 / 700자** 씩 자르고 → 인접 청크는 **3건 겹침**. 사진·삭제·시스템 메시지는 청크 본문에서 빠진다. 청크 텍스트 머리에 `[방] 날짜(요일) 시각~시각 · 참여: 이름들` 헤더가 붙어 "부산 갔던 날 저녁" 같은 질문에 날짜·사람이 검색어로 걸린다.

```
[여행모임] 2024-03-02(토) 19:12~19:16 · 참여: 김하람, 박서아, 이도윤
김하람: 부산 언제 갈까
박서아: 4월 첫주 어때 하람형 시간 되나
이도윤: 나는 됨 ㅋㅋ
```

원문(`messages`)은 그대로 두고 `chunks` 만 파라미터 바꿔 다시 만들 수 있다(`--rebuild-chunks`). W7의 "원문은 정본, 파생물은 재생성" 설계를 여기서부터 지킨다. 같은 파일을 두 번 넣어도 `(room_id, seq)` / `content_hash` 유니크 제약 때문에 중복되지 않는다.

확인

```sql
docker exec -it kg-postgres psql -U kg -d kg
\dt
SELECT msg_type, count(*) FROM messages GROUP BY 1 ORDER BY 2 DESC;
SELECT mem.name, count(*) FROM messages m JOIN members mem ON mem.id=m.sender_id GROUP BY 1 ORDER BY 2 DESC LIMIT 10;
SELECT count(*), round(avg(length(text))) AS avg_chars FROM chunks;
SELECT text FROM chunks ORDER BY random() LIMIT 1;
-- 0세대 grep 은 이것이다: 문자열 포함 여부만, 순위 없음
SELECT sent_at, text FROM messages WHERE text ILIKE '%부산%' ORDER BY sent_at LIMIT 10;
```

---

## 7. 임베딩 생성 → pgvector

```bash
python src/embed.py --limit 20     # 먼저 20개로 키·차원 확인
python src/embed.py                # 전체. 배치마다 커밋하므로 중간에 끊겨도 재실행하면 이어서 한다
```

- `chunk_embeddings(chunk_id, model, embedding vector(EMBED_DIM))` 에 저장하고 마지막에 **HNSW 인덱스(`vector_cosine_ops`)** 를 만든다. 데이터를 먼저 넣고 인덱스를 만드는 편이 빠르다.
- 모든 벡터를 L2 정규화해서 저장한다(코사인은 크기에 무관하므로 무해하고, Gemini 처럼 3072 미만 차원은 정규화가 권장됨).
- 비용 감: 청크 하나가 대략 200~400 토큰. 3만 메시지 ≈ 1,500~3,000 청크 ≈ 100만 토큰 미만 → text-embedding-3-small 로 **수십 원**, gemini-embedding-001 로 **200원 안팎**.

확인

```sql
SELECT model, count(*) FROM chunk_embeddings GROUP BY 1;
SELECT indexname FROM pg_indexes WHERE tablename='chunk_embeddings';   -- chunk_embeddings_hnsw
-- 청크 하나를 질의 벡터로 삼아 이웃 5개: <=> 가 코사인 거리, 1 - 거리 = 코사인 유사도
SELECT c.id, 1 - (e.embedding <=> (SELECT embedding FROM chunk_embeddings LIMIT 1)) AS cos, left(c.text, 60)
FROM chunk_embeddings e JOIN chunks c ON c.id=e.chunk_id
ORDER BY e.embedding <=> (SELECT embedding FROM chunk_embeddings LIMIT 1) LIMIT 5;
```

---

## 8. Elasticsearch 색인 (BM25 + nori)

```bash
python src/index_es.py --analyze "부산 여행 숙소 예약했어요"     # nori 토큰 확인 (인덱스가 없으면 만들고 확인만)
python src/index_es.py                                        # 전체 청크 색인
python src/index_es.py --messages                             # 메시지 1건 단위 인덱스도 원하면
```

`--analyze` 출력이 이렇게 나오면 nori 가 살아 있다.

```
korean       : ['부산', '여행', '숙소', '예약']
korean_ngram : ['부산', '산 ', ... ]        ← 분담 과제 "nori vs n-gram" 비교용 서브필드 text.ngram
```

인덱스 `kakao_chunks` 의 `text` 필드는 `nori_tokenizer(decompound_mode=mixed) → nori_part_of_speech(조사·어미 제거) → nori_readingform → lowercase`. ES 의 기본 유사도가 **BM25** 다. `_id = chunk_id` 라 다시 실행해도 덮어쓴다.

확인 (curl)

```bash
curl -s "localhost:9200/kakao_chunks/_count"
curl -s "localhost:9200/kakao_chunks/_search?pretty" -H 'Content-Type: application/json' -d '
{ "size": 3, "query": { "match": { "text": "부산 숙소" } }, "highlight": { "fields": { "text": {} } } }'
```

---

## 9. 같은 질문을 세 방식으로 — W2 실습 산출물

```bash
python src/search.py "부산 숙소 예약"
python src/search.py "여행 가서 잘 곳 정했어?" -k 8 --room 여행모임
cp questions.example.txt questions.txt      # 내 데이터에 맞는 질문 10개 이상으로 고치고
python src/search.py --batch questions.txt --md > compare.md     # 마크다운 비교표 → labs README 에 붙이기
```

한 질문의 출력 예

```
[0세대 grep] ILIKE '%부산 숙소 예약%' → 0건            ← 띄어쓰기까지 그대로 있어야 잡힌다
[1세대 BM25/nori] top-5 청크
  chunk 1207  score= 11.42 2024-03-02T19:12  «부산» 언제 갈까 … «숙소»는 내가 알아볼게
[2세대 벡터/pgvector] top-5 청크
  chunk 1207  cos= 0.71  2024-03-02 19:12  …
  chunk 1533  cos= 0.66  2024-04-01 22:10  해운대 근처 에어비앤비 잡았어           ← 키워드 없이도 걸림
  BM25 ∩ 벡터 = 2개 청크 [1207, 1210]  ← W3 RRF 융합의 출발점
```

질문은 세 종류를 섞어 만든다.
1. **키워드가 그대로 있는 사실 질문** (예: `회비 입금 계좌`) → grep/BM25 가 이길 것
2. **같은 뜻 다른 표현** (예: `여행 가서 잘 곳 정했어?`) → 벡터가 이길 것
3. **다중 홉·집계** (예: `부산 같이 간 사람 중 같은 회사 다니는 사람`, `작년에 가장 많이 언급된 가게`) → 셋 다 못 답할 것. 이 목록이 W3 "못 답하는 질문 목록" → W4~W6 그래프의 재료가 된다.

`compare.md` 의 마지막 열("누가 이겼나")을 직접 채우면 그것이 W2 실습에서 요구하는 "각 방식이 이기는 질문·지는 질문 표"다.

---

## 10. 다음 스터디 때 보여줄 것 (체크리스트)

- [ ] `data/raw/` 에 원본 txt (화면엔 파일 목록만, 내용은 가명화된 것만 노출)
- [ ] `psql` 에서 `messages`/`chunks` 건수, 발신자별 건수, 청크 샘플
- [ ] `SELECT ... FROM chunk_embeddings` 건수 + HNSW 인덱스 + 이웃 질의 한 번
- [ ] `_cat/plugins` 에 nori, `_count`, `--analyze` 토큰
- [ ] `search.py` 로 질문 3개 라이브 시연 + `compare.md` 표
- [ ] 레포 `members/<id>/labs/01-ingest/` 에 README(이 문서를 내 상황에 맞게 줄인 것) + `src/` + `compare.md` (원본·매핑표·.env 제외)

---

## 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| ES 컨테이너가 바로 죽는다(exit 78, 137) | 메모리 부족. Docker Desktop 메모리 4GB+, `ES_JAVA_OPTS=-Xms1g -Xmx1g`. Linux 는 `vm.max_map_count=262144` |
| `Unknown tokenizer type [nori_tokenizer]` | nori 플러그인 미설치. `docker compose build elasticsearch && docker compose up -d`, `_cat/plugins` 확인 |
| `UnsupportedProductError` / 버전 경고 | elasticsearch-py 메이저 ≠ 서버 메이저. 서버 9.x → `pip install "elasticsearch>=9,<10"`, 8.x 면 `>=8,<9` |
| Postgres 재시작하니 데이터가 사라짐 | pg18 볼륨을 `/var/lib/postgresql/data` 에 마운트한 경우. `/var/lib/postgresql` 로 바꾸고 `docker compose down -v` 후 재적재 |
| `chunk_embeddings.embedding 은 vector(1536) 인데 EMBED_DIM=768` | 모델 차원 변경. `DROP TABLE chunk_embeddings;` 후 재실행 (또는 모델별 테이블 이름 분리) |
| OpenAI `429 insufficient_quota` | 결제 크레딧 충전. `RateLimitError` 가 반복되면 `EMBED_BATCH=16` |
| Gemini 429 (무료 티어 한도) | 분당 요청 제한. `EMBED_BATCH` 를 키워 요청 수를 줄이거나 잠시 대기, 또는 유료 전환 |
| 파서가 "형식을 인식하지 못했습니다" | 첫 15줄을 확인. Mac 은 iOS 형식(`2024. 3. 2. …`)과 같고 24시간제도 허용됨. 새 형식이면 정규식 추가 |
| 한글이 깨져 보임 | Windows 내보내기는 UTF-8(BOM), 구형은 cp949 — 파서가 둘 다 시도한다. 그래도 깨지면 메모장에서 UTF-8 로 다시 저장 |
| 벡터 검색이 `--room` 필터 때 결과가 적음 | HNSW 근사 검색 + 필터 조합의 특성. `SET hnsw.ef_search = 200;` 또는 방이 하나면 필터 생략 |

---

## 설계 요약 (발표 때 "왜 이렇게 했나" 답변용)

- **메시지 ≠ 검색 단위.** 카톡 1건은 너무 짧아 임베딩 의미가 없다. 그래서 정본은 메시지, 검색 단위는 세션 기반 청크. 두 층을 분리해 두면 청킹을 바꿔도 원문은 그대로다(W7 정본↔파생물).
- **grep 세대는 `ILIKE`** 로 재현한다. 문자열 포함 여부만 보고 순위가 없다는 점이 grep 과 같다. `pg_trgm` 인덱스는 속도만 보조한다.
- **BM25 는 nori 로 형태소 단위** 색인. `부산에서`→`부산`, `예약했어요`→`예약` 이 되어야 한국어 키워드 검색이 성립한다. n-gram 서브필드는 비교용.
- **벡터는 코사인 + HNSW.** 정규화된 벡터라 내적과 동일. 소규모라 정확 검색과 차이가 거의 없지만 W2 키워드(HNSW)를 몸으로 익히기 위해 인덱스를 건다.
- **가명화가 첫 단계**인 이유: 레포가 public 이고, 임베딩은 외부 API 로 텍스트가 나간다. 마스킹은 추출·전송 전에 해야 의미가 있다.
