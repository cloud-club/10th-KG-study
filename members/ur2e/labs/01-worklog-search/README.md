---
title: 옵시디언 작업기록 자연어 검색
date: 2026-09-12
tags: [obsidian, rag, search, elasticsearch, pgvector]
status: in-progress
---

# 01. 옵시디언 작업기록 자연어 검색

## 목표

옵시디언에 쌓아둔 내 작업 기록(장애 대응, 절차 메모, 결정 기록, 학습 정리 등)을 "그때 그거 어떻게 했었지" 같은 자연어 질문으로 되찾는 것이 목표입니다. 특정 장애 사례에만 맞춘 검색이 아니라, 형식이 제각각인 개인 vault 전체를 대상으로 합니다.

실제 vault는 사내망에 있어서 지금은 이를 닮은 가정 데이터셋(`dataset/`)으로 파서·검색을 먼저 완성하고, 나중에 `OBSIDIAN_VAULT_PATH`만 바꿔 실제 vault에 붙이는 방식으로 진행합니다.

## 환경

- 언어 / 런타임: Python 3.12
- 주요 인프라: PostgreSQL + pgvector, Elasticsearch + nori (루트 `docker-compose.yml`)
- GUI: Streamlit (`requirements.txt`에 포함, `.venv`에 설치)
- 외부 서비스 / 키: 임베딩 API 키가 필요하면 `.env.example` 참고

## 데이터셋

`dataset/` 아래에 가정 vault, 평가 질문, 기록 템플릿이 있습니다. 문서 형식(프론트매터 유무, `##` 소제목 유무, 날짜 출처 등)을 폴더마다 다르게 섞어둔 이유와 파서가 지켜야 하는 계약은 [dataset/README.md](dataset/README.md)에 정리했습니다.

```
dataset/
├── README.md          # 데이터셋 설계, 파서 계약, 평가 방법
├── vault/              # 옵시디언 vault로 바로 열림 (daily/troubleshooting/howto/decisions/learning/meetings)
├── evaluation/
│   └── queries.jsonl   # 평가 질문 19건
└── note-templates/     # 앞으로 실제 기록을 쓸 때 쓸 템플릿
```

## 실행 방법

```bash
cd 01-worklog-search
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

cd src
python3 parse_vault.py                        # 1. 파서 (의존성 없음)
python3 search_grep.py "<질문>"                # 2. grep
python3 index_elasticsearch.py                # 3. BM25 색인 (docker compose up -d 필요)
python3 search_elasticsearch.py "<질문>"
OPENAI_API_KEY=sk-... python3 index_pgvector.py   # 4. 벡터 색인 (OpenAI 키 필요)
OPENAI_API_KEY=sk-... python3 search_pgvector.py "<질문>"
OPENAI_API_KEY=sk-... python3 evaluate.py         # 5. 세 방식을 질문 19건 전체로 비교

streamlit run app.py                          # 6. GUI (청크 크기 등 파라미터 실험용)
```

파서 결과(`data/ur2e/processed/chunks_*.jsonl`)는 `.gitignore` 대상 — vault에서 언제든 다시 만들 수 있는 산출물이라 커밋하지 않는다.

### GUI (`src/app.py`)

`streamlit run app.py`는 **반드시 `src/` 안에서** 실행합니다 (다른 스크립트들을 상대 import 하기 때문).

사이드바에서 청크 방식을 고릅니다:
- **`## ` 소제목 단위** — 지금까지 CLI로 쓰던 기본 전략. 크기 파라미터 없음.
- **고정 글자 수** — `##` 구조를 무시하고 지정한 글자 수(+겹침)로 균등하게 자르는 비교용 전략. 슬라이더로 청크 크기(100~2000자)·겹침을 바로 바꿔볼 수 있다.

**청크 생성 + 색인**을 누르면 그 설정으로 Elasticsearch 인덱스를 새로 만듭니다(설정마다 별도 인덱스명 `ur2e_worklog_chunks_<설정키>` — 예: `..._fixed_300_100`). pgvector는 체크박스를 켜야만 같이 재색인합니다 — OpenAI 임베딩 호출이라 켤 때마다 비용이 든다는 걸 체크박스 옆에 그대로 적어뒀습니다. 켜지 않으면 grep/BM25만으로 실험할 수 있어서 무료·로컬로 청크 크기를 마음껏 바꿔볼 수 있습니다.

화면 구성:
1. 청크 통계 (문서 수, 청크 수, 평균/최소/최대 길이)
2. 질문 하나를 골라(평가셋 19건 중 선택 또는 직접 입력) grep/BM25/(pgvector) 결과를 나란히 비교
3. **지금 청크 설정으로 19문항 전체 재평가** — Hit@3/MRR을 다시 계산. 청크 크기를 바꿔서 재색인한 뒤 이 버튼을 다시 누르면 숫자가 바로 바뀌는 걸 볼 수 있다.

## 구조

```
01-worklog-search/
├── README.md
├── requirements.txt
├── dataset/
└── src/
    ├── common.py               # 경로·설정 (vault, chunks 출력, ES/PG 접속 정보)
    ├── parse_vault.py          # 1. md → 청크 JSONL 파서
    ├── search_grep.py          # 2. grep(부분 문자열, 순위 없음)
    ├── index_elasticsearch.py  # 3. nori BM25 색인
    ├── search_elasticsearch.py #    nori BM25 검색
    ├── embed.py                # 4. OpenAI 임베딩 호출
    ├── index_pgvector.py       #    pgvector 색인 (HNSW + 코사인)
    ├── search_pgvector.py      #    pgvector 검색
    ├── evaluate.py             # 5. 세 방식을 queries.jsonl 전체로 비교 (Hit@3, MRR)
    └── app.py                  # 6. GUI (Streamlit) — 청크 크기 등 파라미터 실험
```

