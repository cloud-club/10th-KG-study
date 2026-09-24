---
title: 옵시디언 작업기록 Hybrid RAG와 지식 그래프
tags: [obsidian, rag, hybrid-search, rrf, elasticsearch, pgvector, knowledge-graph, ragas]
status: in-progress
---

# 01. 옵시디언 작업기록 Hybrid RAG와 지식 그래프

## 목표

옵시디언에 쌓아둔 내 작업 기록(장애 대응, 절차 메모, 결정 기록, 학습 정리 등)을 "그때 그거 어떻게 했었지" 같은 자연어 질문으로 되찾는 것이 목표입니다. 특정 장애 사례에만 맞춘 검색이 아니라, 형식이 제각각인 개인 vault 전체를 대상으로 합니다.

실제 vault는 사내망에 있어서 지금은 이를 닮은 가정 데이터셋(`dataset/`)으로 파서·검색을 먼저 완성하고, 나중에 `OBSIDIAN_VAULT_PATH`만 바꿔 실제 vault에 붙이는 방식으로 진행합니다.

3주차에는 2주차의 BM25·pgvector 검색을 **RRF(Reciprocal Rank Fusion)** 로 결합하고,
선택한 검색 결과를 근거로만 답하는 챗봇을 추가했습니다. 4주차 설계 초안으로 장애·원인·조치·결정과
원문 청크를 연결한 작은 작업기록 지식 그래프도 같은 UI에서 탐색합니다.

## 현재 구현 범위

- 청크 방식·크기·겹침 변경과 실제 청크 미리보기
- grep / BM25 / pgvector / Hybrid RRF 동일 질문 비교
- 네 검색 방식의 Hit@3·MRR 전체 평가
- RAGAS의 Context Recall·Faithfulness·Factual Correctness 평가 설계와 샘플 미리보기
- BM25 / Vector / Hybrid 중 검색 방식을 고르는 근거형 챗봇
- 답변의 `[C1]` 인용과 실제 검색 청크 대조
- `Incident`, `System`, `Symptom`, `Cause`, `Action`, `Decision`, `Todo`, `Document` 그래프 v1
- 질문과 관련된 노드의 1-hop 관계 및 엣지 근거 시각화

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
OPENAI_API_KEY=sk-... python3 hybrid_search.py "<질문>" # 6. BM25+Vector RRF

streamlit run app.py                          # 7. 청킹·검색·챗봇·그래프 통합 UI

cd ../tests
../.venv/bin/python -m unittest discover -v  # 순수 로직 테스트(DB·API 불필요)
```

파서 결과(`data/ur2e/processed/chunks_*.jsonl`)는 `.gitignore` 대상 — vault에서 언제든 다시 만들 수 있는 산출물이라 커밋하지 않는다.

### GUI (`src/app.py`)

`streamlit run app.py`는 **반드시 `src/` 안에서** 실행합니다 (다른 스크립트들을 상대 import 하기 때문).

사이드바에서 청크 방식을 고릅니다:
- **`## ` 소제목 단위** — 지금까지 CLI로 쓰던 기본 전략. 크기 파라미터 없음.
- **고정 글자 수** — `##` 구조를 무시하고 지정한 글자 수(+겹침)로 균등하게 자르는 비교용 전략. 슬라이더로 청크 크기(100~2000자)·겹침을 바로 바꿔볼 수 있다.

**청크 생성 + 색인**을 누르면 그 설정으로 Elasticsearch 인덱스를 새로 만듭니다(설정마다 별도 인덱스명 `ur2e_worklog_chunks_<설정키>` — 예: `..._fixed_300_100`). pgvector는 체크박스를 켜야만 같이 재색인합니다 — OpenAI 임베딩 호출이라 켤 때마다 비용이 든다는 걸 체크박스 옆에 그대로 적어뒀습니다. 켜지 않으면 grep/BM25만으로 실험할 수 있어서 무료·로컬로 청크 크기를 마음껏 바꿔볼 수 있습니다.

화면 구성:
1. **청킹** — 통계와 문서별 실제 청크 경계·본문 미리보기
2. **검색 비교** — 같은 질문의 grep/BM25/Vector/Hybrid RRF 결과와 원래 순위 비교
3. **챗봇** — 검색 방식 선택, LLM에 전달한 근거, `[C#]` 인용 답변
4. **지식 그래프** — 노드·엣지·관계 근거를 Graphviz로 탐색
5. **평가** — 19문항 Hit@3/MRR 재계산과 RAGAS 답변 평가 구조 확인

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
    ├── hybrid_search.py        # 5. BM25+Vector RRF 결합
    ├── rag_agent.py            # 6. 근거 조립, 답변 생성, 인용 검증
    ├── knowledge_graph.py      # 7. 그래프 검증·부분 그래프·Graphviz
    ├── evaluate.py             # 8. 네 방식을 queries.jsonl 전체로 비교
    └── app.py                  # 9. 청킹·검색·챗봇·그래프 통합 GUI
```
