# 프로젝트 Notion 검색

## 개요

금융 프로젝트의 Notion 문서를 PostgreSQL과 Elasticsearch에 적재하고, BM25로 검색한 근거를 Gemini에 전달해 답변을 생성했다.

## 데이터 및 처리

| 항목 | 내용 |
|---|---|
| 입력 | Notion export의 Markdown 628개 |
| 전처리 | NFC 정규화, 이미지 표기·링크 URL 제거 |
| 청킹 | 1,200자, 200자 겹침 |
| 결과 | 1,477개 청크 |
| 검색 | Elasticsearch nori + BM25 |
| 답변 생성 | Gemini, 근거 기본 3개와 인용 번호 |

```text
Notion Markdown → 전처리·청킹 → PostgreSQL / Elasticsearch
질문 → BM25 검색 → 중복 제거 → 근거 조립 → Gemini 답변
```

## 저장 구조

| 저장 위치 | 데이터 | 용도 |
|---|---|---|
| PostgreSQL `yeongeunn_notion.chunks` | 청크 ID, 페이지 ID, 제목, 출처, 시작 위치, 본문 | 청크·출처 관리 |
| Elasticsearch `yeongeunn-notion-v1` | 동일 청크와 제목·본문의 검색 인덱스 | nori 분석 및 BM25 검색 |

두 저장소에 같은 청크 ID를 사용했다. 질의 시에는 Elasticsearch의 `_source`에서 검색된 본문을 가져온다. [저장 구조와 청킹 정리](../../notes/02-week2-search-generations.md)

- 원본: `data/Yeongeunn/raw/Erumpay_notion/`
- 가공 파일: `data/Yeongeunn/processed/notion-chunks.jsonl`

## 실행

Python 3.9 이상, Docker Compose의 PostgreSQL·Elasticsearch를 사용한다. Python 코드는 표준 라이브러리로 작성했다. [공용 인프라](../../../../infra/README.md)를 실행한 뒤 레포 루트에서 아래 명령을 실행한다.

```bash
python3 members/Yeongeunn/labs/03-notion-ingest/src/notion_search.py prepare
python3 members/Yeongeunn/labs/03-notion-ingest/src/notion_search.py ingest
python3 members/Yeongeunn/labs/03-notion-ingest/src/notion_search.py count
python3 members/Yeongeunn/labs/03-notion-ingest/src/notion_search.py search --query '<질문>'
```

Gemini API 키는 루트 `.env`의 `GEMINI_API_KEY`에 설정한다.

```bash
python3 members/Yeongeunn/labs/03-notion-ingest/src/rag.py preview --query '<질문>'
python3 members/Yeongeunn/labs/03-notion-ingest/src/rag.py ask --model gemini-3.1-flash-lite --query '<질문>'
```

| 명령 | 동작 |
|---|---|
| `prepare` | Markdown을 파싱해 청크 JSONL 생성 |
| `ingest` | 파싱·가공 후 PG와 ES에 적재 |
| `count` | 저장소별 청크 수 확인 |
| `search` | BM25 상위 5개 결과 출력 |
| `preview` | 검색 근거를 로컬에서 확인 |
| `ask` | 질문과 근거 본문을 Gemini API에 전달해 답변 생성 |

사용 가능한 모델은 `rag.py models`로 확인할 수 있다. 실습에는 `gemini-3.1-flash-lite`를 사용했다.

## 결과

- Markdown 628개를 1,477개 청크로 나누어 적재했다.
- BM25 검색에서 관련 문서 조각과 점수를 확인했다.
- 상위 검색 결과에 같은 내용의 복제 페이지가 포함됐다. RAG에서는 후보 30개 중 공백을 정규화한 본문이 같은 항목을 제거하고 근거 3개를 선택했다.
- Gemini 답변과 근거 번호, 로컬 출처 목록을 출력했다.

## 구현상 한계

- 문자 단위 분할로 표·코드·조건문이 청크 경계에서 잘릴 수 있다.
- ID 기준 upsert는 지원하지만 원본 삭제·축소에 따른 이전 청크 삭제는 지원하지 않는다.
- PG와 ES 사이에 단일 트랜잭션이 없어 부분 적재가 발생할 수 있다.
- 기본 마스킹은 일부 숫자·토큰·이메일을 처리하며, 인용 검사는 번호 유효성만 확인한다.

## 예정

- grep 고정 문자열 검색 기준선 비교
- 임베딩·벡터 검색
- RRF 하이브리드 검색
- 정답 근거를 지정한 질문셋과 Recall@5 비교
- 다중 홉 질문의 검색 결과와 실패 유형 기록
