---
title: 하이브리드 검색(BM25+벡터 RRF)과 개인 카톡 RAG 에이전트 v1 — Recall@k 비교와 못 답하는 질문
date: 2026-09-16
tags: [hybrid-search, reciprocal-rank-fusion, rag, recall-at-k, mrr, citation-grounding, multi-hop, hnsw, evaluation]
status: done
---

# 02. 하이브리드 검색(BM25+벡터 RRF)과 개인 카톡 RAG 에이전트 v1

> 관련 노트: [`04-hybrid-search-rrf-recall.md`](../../notes/04-hybrid-search-rrf-recall.md) · [`05-rag-loop-citation-multihop.md`](../../notes/05-rag-loop-citation-multihop.md)
> 앞 실습: [`01-ingest`](../01-ingest/README.md) — 이 실습은 W2가 만든 Postgres(`chunks`, `chunk_embeddings`)와 Elasticsearch(`kakao_chunks`)를 **읽기만** 한다. 데이터를 다시 적재하지 않는다.

## 목표

1. W2에서 따로 돌렸던 BM25(Elasticsearch·nori)와 벡터(pgvector·KURE-v1) 검색을 **애플리케이션 계층 RRF**로 합친다.
2. 정답 근거를 미리 라벨링한 평가셋으로 **BM25 / 벡터 / RRF의 Recall@k·MRR**을 같은 조건에서 비교한다.
3. 검색 결과를 `[C#]` 근거로 조립해 답하는 **읽기 전용 개인 데이터 에이전트 v1**을 만들고, 인용이 실제 제공한 근거 ID인지 코드로 검증한다.
4. 답할 수 없는 질문을 **실패 단계별**로 기록해 W4(지식 그래프)의 재료로 남긴다. → [`results/failures.md`](results/failures.md)

## 환경

- W2와 동일: Postgres 18.6 + pgvector 0.8.6 · Elasticsearch 9.5.3 + analysis-nori · Colima 4 CPU / 6 GiB
- Python 3.13 (`../01-ingest/.venv` 재사용) · psycopg 3 · elasticsearch-py 9 · sentence-transformers 6 (KURE-v1, 1024차원) · pytest 8
- 답변 생성 LLM: **선택.** `.env`의 `LLM_PROVIDER`가 `none`(기본)이면 검색·평가·컨텍스트 조립까지만 수행한다. OpenAI / Gemini / OpenAI 호환 로컬 서버(Ollama 등)를 붙일 수 있다. → `.env.example`
- 외부 키: 없음(기본값). 이 문서의 결과는 모두 로컬에서만 계산했다.

## 실행 방법

```bash
cd members/lys0611/labs/02-hybrid-rag-agent
cp .env.example .env                   # W2의 ../01-ingest/.env를 먼저 읽고 이 파일로 덮어씀
PY=../01-ingest/.venv/bin/python       # 또는 새 venv + pip install -r requirements.txt

$PY -m pytest -q                       # 순수 로직 테스트 23개 (DB·네트워크 불필요)

# 1) 질문 하나를 RRF로 검색하고 trace(방·시각·양쪽 순위·RRF 점수)만 본다
$PY src/cli.py "서버가 왜 안 켜져?" --room 팀리더 --retrieve-only
$PY src/cli.py "..." --retrieve-only --show-context     # LLM에 넘길 EVIDENCE 블록 확인 (원문 포함, 터미널에서만)

# 2) 평가셋 만들기: 후보 풀 → 사람이 라벨 → hash 기반 JSONL로 고정
$PY src/build_eval_pool.py data/private/questions.draft.jsonl      # BM25∪벡터 상위 50개씩을 RRF 순으로 모음
#   data/private/labels.json 에 qid → {evidence_id: [chunk_id, ...]} 를 사람이 작성
$PY src/make_eval_set.py data/private/labels.json                   # content_hash로 변환 + 스키마 검증

# 3) 세 방식 평가 (Recall@1/3/5/10, AllEvidence@k, MRR@10, p50 지연, HNSW 근사 손실)
$PY src/evaluate.py                                    # → results/retrieval-summary.md (공개), results/private/evaluation.json
$PY src/evaluate.py --candidate-k 10                   # 후보를 5~10개만 가져오면 어떻게 되는지
$PY src/evaluate.py --rank-constant 10                 # RRF c 민감도
$PY src/evaluate.py --exact-vector                     # HNSW 대신 정확 검색

# 4) 답변 생성 — 로컬 LLM(Ollama) 연결. 데이터가 노트북 밖으로 나가지 않는다
brew install ollama && brew services start ollama
ollama pull exaone3.5:7.8b                            # 4.8 GB, 한·영 이중언어 (LG AI Research)
ollama create kakao-rag -f ollama/Modelfile.exaone    # num_ctx 8192 — 기본 4096이면 근거 5개가 잘릴 수 있음
#   .env: LLM_PROVIDER=openai-compatible  LLM_MODEL=kakao-rag  LLM_BASE_URL=http://localhost:11434/v1  LLM_API_KEY=ollama
$PY src/cli.py "kubeflow 강의 원고 마감이 언제야?"      # 한 질문 → 답변 + [C#] + 인용 검증

# 5) 34문항 일괄 생성 → 사람이 채점 → 공개 집계
$PY src/generate_answers.py --dry-run                 # LLM 없이 경로만 점검 (stub 답변)
$PY src/generate_answers.py                           # → results/private/answers.jsonl, grading.csv
#   grading.csv 의 accuracy(0/0.5/1) · citation_precision · citation_recall · refusal_ok(0/1) 를 채운다
$PY src/summarize_grading.py                          # → results/generation-summary.md (숫자만)
```

## 구조

```
02-hybrid-rag-agent/
├── README.md
├── requirements.txt · .env.example · .gitignore
├── src/
│   ├── common.py            W2 .env → W3 .env 순으로 설정 로드, RRF/HNSW/LLM 파라미터
│   ├── models.py            SearchFilters · RankedHit · FusedHit · Chunk · ContextItem · CitationCheck
│   ├── retrieval.py         bm25_search(ES) · vector_search(pgvector, strict_order iterative scan / exact) · fetch_chunks · 건수 정합성
│   ├── rrf.py               reciprocal_rank_fusion — content_hash 단위, 동점은 (점수, 최소순위, hash)로 고정
│   ├── hybrid.py            HybridSearchEngine: 가명화 → BM25 top-k ∥ 임베딩 → 벡터 top-k → RRF → 전체 청크 재조회
│   ├── embedding.py         질문 임베딩 (W2 문서 벡터와 같은 모델·정규화)
│   ├── privacy.py           질문 속 실명·전화·이메일을 로컬 매핑표로 치환 (외부 호출 전)
│   ├── context.py           겹치는(≥60%) 연속 청크 제거, 글자 예산 안에서 [C1..Ck] 조립
│   ├── citations.py         [C#] 추출·미제공 ID 검출·문장 단위 인용 커버리지
│   ├── llm.py               OpenAI / Gemini / OpenAI 호환 제공자 (기본 none)
│   ├── agent.py             읽기 전용 단일 턴 RAG (EVIDENCE는 데이터, 명령이 아니라는 시스템 프롬프트)
│   ├── cli.py               한 질문 실행 + trace 출력
│   ├── dataset.py           평가 JSONL 스키마 검증, 코퍼스 지문(fingerprint), gold hash 존재 확인
│   ├── metrics.py           evidence_recall@k · all_evidence@k · MRR · ANN recall
│   ├── build_eval_pool.py   라벨링용 후보 풀 (비공개)
│   ├── make_eval_set.py     labels.json(chunk_id) → eval.jsonl(content_hash)
│   ├── evaluate.py          세 방식 일괄 평가 + 마크다운 요약
│   ├── generate_answers.py  평가셋 전체에 답변 생성 → answers.jsonl + 채점표 grading.csv (--dry-run 지원)
│   └── summarize_grading.py 채점표 집계 → generation-summary.md
├── ollama/Modelfile.exaone  로컬 모델 정의 (exaone3.5:7.8b, num_ctx 8192, temperature 0)
├── tests/                   RRF·지표·데이터셋·인용·컨텍스트·에이전트(stub) 23개
├── data/private/            질문 원문·라벨·평가셋 — 커밋 제외
└── results/
    ├── retrieval-summary.md 공개 집계 결과 (evaluate.py 출력)
    ├── generation-summary.md 공개 생성 평가 집계 (summarize_grading.py 출력, 채점 후 생성)
    ├── failures.md          못 답하는 질문 목록과 W4 연결
    └── private/             질문별 결과 JSON·답변·채점표 — 커밋 제외
```

### 설계에서 정한 것

- **검색·평가 단위는 청크, ID는 `content_hash`.** 숫자 `chunk_id`는 재청킹하면 바뀌지만 hash는 본문이 같으면 같다. 평가셋은 hash로 저장하고, 실행 전에 gold hash가 현재 코퍼스에 있는지 확인해 “조용히 0점”이 되는 일을 막는다(`dataset.assert_gold_exists`). 실행 시작 때 Postgres 청크·임베딩·ES 문서 수가 같은지도 확인한다.
- **RRF는 Elasticsearch 내장이 아니라 파이썬에서.** 임베딩이 pgvector에만 있어 ES의 `rrf` retriever를 쓸 수 없다. 두 저장소가 같은 `chunk_id`/`content_hash`를 공유하므로 순위만 받아 합치면 된다.
- **후보 50개씩 → 최종 5개.** 최종 5개를 보여준다고 각 검색기에서 5개만 가져오면, 한쪽 6~10위에 있던 정답은 융합 기회조차 없다.
- **동점 고정.** BM25는 `_score desc, chunk_id asc`, 벡터는 완전 동점만 `chunk_id`, RRF는 `(점수 desc, 두 순위 중 최소, hash)`. 같은 입력이면 항상 같은 순서가 나와야 평가가 재현된다.
- **방 필터가 있는 HNSW는 `hnsw.iterative_scan = strict_order`.** 필터는 인덱스 스캔 뒤에 적용되므로 `ef_search`만큼 뽑은 후보 중 해당 방 청크가 적으면 `LIMIT`을 못 채운다. pgvector 0.8부터 필요할 때 탐색을 이어가는 옵션이 있다([pgvector README](https://github.com/pgvector/pgvector#iterative-index-scans)).
- **LLM에는 스니펫이 아니라 전체 청크.** RRF가 끝난 뒤 Postgres에서 본문을 다시 읽어 `[C1]..[C5]`로 조립한다. 연속 청크가 60% 이상 겹치면 하나만 남긴다(overlap 3건 때문에 같은 대화가 두 번 들어가는 것을 막기 위해).
- **답변 검증은 구조만.** `[C99]`처럼 제공하지 않은 ID가 있으면 예외, 사실 문장에 인용이 하나도 없으면 예외, 거절 문장은 인용 없이 통과. “인용이 붙었다 ≠ 근거가 그 주장을 지지한다”이므로 실제 지지 여부는 사람이 따로 판정한다. 일괄 생성(`generate_answers.py`)에서는 예외 대신 `citation_unknown` 열에 기록해 배치가 끊기지 않게 했다.
- **로컬 LLM은 컨텍스트 크기를 모델에 박아 둔다.** Ollama 기본 컨텍스트는 4,096 토큰이고 OpenAI 호환 `/v1` 경로로는 `num_ctx`를 넘길 수 없다([Ollama FAQ](https://docs.ollama.com/faq), [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)). 근거 5개(최대 6,000자)와 시스템 프롬프트가 4,096을 넘으면 앞부분이 조용히 잘리므로, `Modelfile`에 `PARAMETER num_ctx 8192`를 넣어 `kakao-rag`라는 이름으로 만들어 쓴다. 평균 청크가 292~363자라 실제 컨텍스트는 대개 2,000토큰 안쪽이고, 8,192는 상한 6,000자를 감안한 값이다. 메모리 16 GiB에서 Colima 6 GiB를 쓰는 상태라 7.8B Q4(4.8 GB) + KV 캐시(8k 기준 약 1 GB)가 들어가며, 부족하면 `exaone3.5:2.4b`로 내린다. Qwen3처럼 thinking 모드가 있는 모델은 답변 앞에 사고 과정이 섞여 인용 검증이 흔들릴 수 있어 1차 선택에서 제외했다.

## 결과

### 평가셋 (2026-09-16 고정, `data/private/eval.jsonl`, 비공개)

| 유형 | 개수 | 검색 평가 | 설명 |
|---|---:|---:|---|
| exact — 정확 표현·단일 사실 | 12 | 12 | 명령어·고유명사·특정 문구가 그대로 들어 있는 질문. W2 질문 4개 포함 |
| semantic — 표현 불일치 | 12 | 12 | 답 청크에 질문 단어가 거의 없는 질문(“서버가 왜 안 켜져?” ↔ “재부팅해서 active되지 않고”) |
| hard — 다중 홉·시간·집계·답 없음 | 10 | 3 | 근거 2개가 필요한 3개만 Recall 대상. 집계 3개는 qrels를 만들 수 없어 제외, 답 없음 4개는 거절 성공률로 따로 본다 |

라벨링 절차: (1) BM25·벡터 각 top-50을 RRF 순으로 모은 후보 풀을 읽고 (2) 원문 주변 메시지(`messages`)와 grep으로 실제 답을 확인한 뒤 (3) 답을 직접 지지하는 청크만 gold로 두고, overlap으로 같은 근거가 두 청크에 걸치면 한 evidence group의 대체 후보로 넣었다. 후보 풀에서 라벨을 뽑았으므로 세 방식 모두 후보에 없던 정답은 놓칠 수 있는 **pooling bias**가 있다(세 방식이 같은 풀을 썼으니 상대 비교에는 공평하다). 초안 34문항 중 절반가량은 풀을 읽은 뒤 정답이 하나로 정해지도록 질문을 다시 썼다(예: “점심 메뉴 추천해 줘” → “점심으로 뭐 주문했어?”). 다시 쓴 질문의 라벨은 본문을 읽고 정했으므로 검색 순위와는 독립적이며, 그중 2문항은 세 방식 모두 top-10에서 놓쳤다.

### 세 방식 비교 (평가 가능 27문항, candidate_k=50, RRF c=60, HNSW ef_search=100)

`Evidence Recall@k` = 필요한 evidence group 중 top-k에서 하나라도 찾은 비율의 질문 평균. `AllEvidence@k` = 모든 group을 찾은 질문 비율. 전체 표는 [`results/retrieval-summary.md`](results/retrieval-summary.md).

| 방식 | Recall@1 | Recall@3 | Recall@5 | Recall@10 | AllEvidence@5 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| BM25 (nori) | 0.648 | 0.796 | 0.833 | **0.926** | 0.815 | 0.773 |
| 벡터 (KURE-v1, HNSW) | 0.685 | 0.778 | 0.815 | 0.870 | 0.778 | 0.778 |
| **RRF** | **0.759** | **0.907** | **0.907** | 0.907 | **0.889** | **0.864** |

| 유형 (n) | BM25 R@5 | 벡터 R@5 | RRF R@5 |
|---|---:|---:|---:|
| exact (12) | 1.000 | 1.000 | 1.000 |
| semantic (12) | 0.667 | 0.667 | 0.833 |
| hard·다중 홉 (3) | 0.833 | 0.667 | 0.833 |

지연(질문당 p50): BM25 5.5 ms · 질문 임베딩 26.4 ms · pgvector 8.1 ms · RRF 0.1 ms · 합계 40.1 ms. HNSW top-10과 정확 검색 top-10의 겹침은 27문항 평균 **1.000** — 1,922개 규모·ef_search=100에서는 근사 손실이 관측되지 않았다(`--exact-vector` 결과도 동일).

### 읽는 법

- **RRF가 이긴 자리는 top-1~5.** 두 검색기가 서로 다른 후보를 올려도(W2에서 top-5 교집합이 0~2개였다) 양쪽에 모두 등장한 청크가 위로 올라온다. “돈 언제까지 보내야 해”는 BM25 7위·벡터 10위였던 정답이 RRF 2위가 됐고, “클러스터 연결이 안 될 때”는 3위·3위 → 1위, “서버가 왜 안 켜져?”는 BM25 7위를 벡터 1위가 끌어올려 1위를 지켰다.
- **Recall@10에서는 BM25가 RRF보다 높다(0.926 vs 0.907).** RRF는 한쪽에만 있는 후보를 아래로 밀기 때문에, BM25 8위에만 있던 “Lab8 실습 변경의 구현 세부”(q032 두 번째 근거)가 RRF 11위로 내려갔다. 융합은 상위 정밀도를 사고 꼬리 재현율을 조금 판다. `--candidate-k 10`, `--rank-constant 10`으로 바꿔도 Recall은 그대로고 MRR만 0.864 → 0.858로 소폭 움직였다. 27문항이라 이 차이는 해석하지 않는다.
- **exact 12문항은 셋 다 1.0.** 이 데이터에서 “정확한 문구가 있으면 무엇으로 찾아도 된다”는 W2의 관찰이 재현됐다. 차이는 전부 semantic과 다중 홉에서 났다.
- **셋 다 놓친 semantic 2문항**은 RRF 39위·65위였다. “교수님이 웹 화면에 추가하라고 한 문구”(정답은 목록형 지시 청크)와 “실습 파트를 누가 뭘 맡았어?”(정답은 `IAM - A / VPC, LB, DNS - B` 같은 표 형태 한 줄)다. 질문의 자연어와 답의 **구조화된 표 형태** 사이에 어휘도 임베딩도 다리를 놓지 못했다. 이건 검색기 튜닝이 아니라 “누가 무엇을 맡았다”는 관계를 구조로 뽑아야 하는 문제다 → W4.
- **HNSW 근사 손실 0** 은 규모가 작아서다. 전체 벡터 1,922개는 정확 검색도 8 ms 안에 끝나므로, 이 규모에서 HNSW는 성능 장치가 아니라 다음 단계 실험용이다.

### 에이전트 v1 상태

- 검색 → RRF → 중복 제거 → 전체 청크 재조회 → `[C#]` 조립 → 인용 검증까지는 실제 데이터로 확인했다(`cli.py --retrieve-only`). 다중 홉 질문 “교수님이 요청한 이론 교재 수정을 누가 반영했어?”는 요청 청크(팀리더 방)와 반영 청크(프로젝트팀 방)가 각각 RRF 1·2위로 함께 컨텍스트에 들어왔다. 두 방을 잇는 bridge 질문도 검색 단계는 통과할 수 있다는 예다.
- **LLM 답변 생성은 아직 실행하지 않았다.** 2026-09-16 기준 로컬 LLM 서버도, API 키도 없는 상태였고 개인 카톡을 무료 클라우드 티어에 보내지 않기로 한 W1 원칙을 유지했다. 생성 경로는 stub 제공자로 테스트(`tests/test_agent.py`, `generate_answers.py --dry-run` 34문항 통과)했고, 미제공 인용 ID 검출·거절 문장 처리는 `tests/test_citations.py`로 검증했다. 다음 단계는 위 실행 방법 4)·5)대로 Ollama의 `kakao-rag`를 붙여 34문항을 생성하고 `grading.csv`를 채점한 뒤 `results/generation-summary.md`를 만드는 것이다. 채점 항목은 [`results/failures.md`](results/failures.md) 3절과 같다.

## 배운 점

- **평가셋을 먼저 고정하는 일이 구현보다 오래 걸렸다.** W2의 10개 질문은 “누가 이겼나”를 사람이 보는 용도라 정답 청크가 없었다. Recall을 계산하려면 질문마다 “어느 청크가 답을 지지하는가”를 원문을 읽고 정해야 했고, 그 과정에서 질문 절반을 다시 썼다(“점심 메뉴 추천해 줘”는 정답이 존재하지 않는 질문이었다).
- **overlap 청킹은 평가 단위를 흔든다.** 같은 대화가 두 청크에 걸쳐 있으면 어느 쪽을 찾아도 정답이다. 물리 청크가 아니라 evidence group을 단위로 삼아야 한다.
- **RRF는 “최선의 후보를 위로”가 아니라 “양쪽이 동의하는 후보를 위로”다.** 그래서 top-1~5에서 강하고, 한쪽만 아는 정답은 밀려난다. 최종 k가 작을수록 유리하다.
- **grep은 Recall@k 표에서 빠졌다.** grep은 메시지 단위·순위 없음이라 청크 단위 Recall과 비교할 수 없다. 0세대 시연은 W2 `search.py`에 남겨 두었다.
- **공용 인프라로 옮길 때.** `main`의 `infra/`는 `pgvector/pgvector:pg17`(볼륨 `/var/lib/postgresql/data`)과 ES 9.1이다. 이 실습의 데이터는 W2 compose(pg18, `/var/lib/postgresql`, ES 9.5.3)의 볼륨에 있으므로 옮기려면 `run_pipeline.sh`로 다시 적재하거나 `pg_dump`를 써야 한다. 코드는 `DATABASE_URL`·`ES_URL`만 바꾸면 된다.

## 다음 단계

- [ ] Ollama `kakao-rag`(exaone3.5:7.8b)로 34문항 답변을 생성하고(`generate_answers.py`) 정확도(0/0.5/1)·인용 precision/recall·답 없음 거절률을 `grading.csv`에 채점한 뒤 `summarize_grading.py`로 집계한다. 클라우드 모델을 쓸 경우에만 가명화 누락(제3자 실명) 재처리가 선행돼야 한다.
- [ ] 에이전틱 재질의(최대 2 hop·3회 검색)를 hard 5문항에만 적용해 flat RAG와 AllEvidence@k·비용을 비교한다. 목적은 해결이 아니라 query drift가 어디서 생기는지 관찰하는 것.
- [ ] 평가셋을 50문항으로 늘리고, 라벨러 2인 일치도(gold 청크 기준)를 기록한다.
- [ ] 청크 헤더(방·날짜·참여자) 유무가 벡터 검색에 미치는 영향을 같은 평가셋으로 비교한다.
- [ ] W4: `results/failures.md`의 관계·집계·시간 유효성 실패를 `PERSON–ASSIGNED–LAB`, `PERSON–WORKS_AT–COMPANY(valid_from/to)` 같은 그래프 스키마로 옮긴다.
