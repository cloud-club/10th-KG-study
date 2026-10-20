---
title: 카카오톡 대화 파싱 → PostgreSQL 적재
date: 2026-09-09
tags: [kakaotalk, parsing, postgres, ingestion, pg-trgm]
status: done
---

# 01. 카카오톡 대화 파싱 → PostgreSQL 적재

> 관련 노트: `../../notes/02-chunking.md`, `../../notes/04-hybrid-search.md`

## 목표

내 카카오톡 단톡방 내보내기(txt)를 구조화해서 로컬 PostgreSQL 에 쌓는다.
이후 청킹·임베딩·하이브리드 검색·지식그래프 추출 실습의 원천 데이터가 된다.

- 여러 줄 메시지, 날짜 구분선, 시스템 이벤트(입장/퇴장/초대), 오전/오후 12시 처리를 정확히
- 사진·동영상·음성·파일·삭제·링크 같은 비텍스트 메시지를 `kind` 로 구분해 텍스트만 골라 쓸 수 있게
- 같은 파일을 다시 넣어도 중복 없이 갱신되게

## 환경

- 언어 / 런타임: Python 3.9+ (파서는 표준 라이브러리만, DB 적재는 `psycopg`)
- DB: 레포 루트 `docker compose up -d postgres` (PostgreSQL 17 + pgvector + pg_trgm)
- 접속 정보: `.env` 의 `POSTGRES_*` 또는 `DATABASE_URL`. 기본값 `postgresql://kg:kg@localhost:5432/kg`

## 실행 방법

레포 루트에서:

```bash
docker compose up -d postgres
cp ~/Downloads/우리동네.txt data/      # data/ 는 README 빼고 git 이 무시함

# 파싱 결과만 확인 (DB 접속 안 함)
python3 members/sese2204/labs/01-kakao-ingest/src/ingest.py --dry-run data/우리동네.txt

# 적재 (uv 가 psycopg 를 임시로 깔아 줌. pip 이면 pip install -r src/requirements.txt)
set -a; . ./.env; set +a
uv run --with 'psycopg[binary]' members/sese2204/labs/01-kakao-ingest/src/ingest.py data/우리동네.txt

# 확인
docker compose exec postgres psql -U kg -d kg -c 'select * from kakao.sender_stats order by messages desc;'

# 테스트
python3 -m unittest discover -s members/sese2204/labs/01-kakao-ingest/src
```

## 구조

```
src/
├── kakao_parser.py       # txt → Chat(room_name, exported_at, messages). 순수 함수, DB 모름
├── schema.sql            # kakao.rooms / kakao.messages + 인덱스 + sender_stats·daily_counts 뷰
├── ingest.py             # CLI: 파싱 → 스키마 적용 → 방 upsert → 기존 메시지 삭제 → COPY
├── test_kakao_parser.py  # 파서 단위 테스트 17개
└── requirements.txt      # psycopg[binary]
```

입력 형식은 모바일 "대화 내보내기" txt 입니다.

```
우리동네 카카오톡 대화
저장한 날짜 : 2024년 8월 2일 오후 4:03

2023년 8월 9일 오전 12:34                          ← 날짜 구분선 (건너뜀)
2023년 8월 9일 오전 12:34, 홍길동 : 안녕            ← 메시지
둘째 줄                                             ← 앞 메시지에 이어 붙임 (\n)
2024년 8월 2일 오후 3:39, 홍길동님이 나갔습니다.     ← 시스템 이벤트, sender NULL
```

테이블 `kakao.messages`:

| 컬럼 | 뜻 |
|------|-----|
| `seq` | 파일 안 순서. 시각이 분 단위라 같은 분 안의 순서는 이걸로 |
| `line_no` | 원본 txt 줄 번호 (파싱 검증용) |
| `sent_at` | KST, `timestamp` (분 단위) |
| `sender` | 보낸 사람. 시스템 이벤트면 NULL |
| `kind` | `text` `photo` `video` `voice` `emoticon` `file` `deleted` `shop` `link` `system_leave` `system_invite` `system_join` `system` |
| `content` | 본문. 여러 줄이면 `\n` 로 이어짐. `gin_trgm_ops` 인덱스 → `ILIKE '%단어%'` 빠름 |

## 결과

`우리동네.txt` (9.2MB, 141,339줄) → 1.4초에 적재.

| 항목 | 값 |
|------|-----|
| 메시지 | 139,677건 (참여자 5명, 2023-08-09 ~ 2024-08-02) |
| 날짜 구분선 | 303줄 (건너뜀) |
| 여러 줄 메시지 | 290건 (최대 29줄 / 500자) |
| 종류 | text 134,813 · photo 2,122 · link 1,289 · shop 926 · voice 248 · video 120 · emoticon 76 · deleted 42 · file 27 · system 14 |

- 같은 파일을 다시 넣으면 `kakao.rooms.source_file` 기준으로 방 1개, 메시지 수 동일, `(room_id, seq)` 중복 0.
- `ILIKE '%단어%'` 가 `messages_content_trgm_idx` (Bitmap Index Scan) 를 탄다.

## 배운 점

- 내보내기 txt 에는 초가 없다. 같은 분에 수십 개가 몰리니 순서 컬럼(`seq`)이 꼭 필요하다.
- 날짜 구분선은 그날 첫 메시지와 똑같은 시각 문자열이라, "`, ` 뒤가 없는 타임스탬프 줄"로만 구분된다.
- `<사진 읽지 않음>` 은 다음 줄에 한 번 더 찍히는 경우가 있어 첫 줄로 종류를 판정해야 한다.
- 안드로이드 내보내기는 첨부를 `sha256해시.jpg` 같은 파일명 줄로도 남긴다(1,099건, 여러 장이면 여러 줄). 벡터 검색 결과에 섞여 나와서 알았고, 확장자로 photo/video/voice 를 판정하게 했다.
- 시스템 줄(`님이 나갔습니다.`)은 ` : ` 구분자가 없다. 본문에 ` : ` 가 들어간 메시지(22건)는 첫 구분자로만 잘라야 한다.
- 맥 기본 `sed` 는 UTF-8 한글에 안전하지 않다. 프로파일링도 파이썬으로.
- **PostgreSQL 을 `--locale=C` 로 만들면 pg_trgm 이 한글에서 트라이그램을 못 뽑는다** (`show_trgm('수강신청')` = `{}`). 인덱스는 있는데 플래너가 순차 스캔의 33배 비용으로 계산해 한 번도 안 탔다. `--locale=C.UTF-8` 로 다시 initdb 하니 Bitmap Index Scan (heap 5블록). 인프라 compose 를 이렇게 고쳤다.

## 다음 단계

- [ ] 텍스트 메시지를 발화자·시간 간격 기준으로 묶어 청킹 (`02-chunking` 노트 적용)
- [ ] Elasticsearch(nori) 에 색인해 BM25 검색, pgvector 임베딩과 하이브리드
- [ ] 발화자·언급 대상·장소를 뽑아 Neo4j 지식그래프로
