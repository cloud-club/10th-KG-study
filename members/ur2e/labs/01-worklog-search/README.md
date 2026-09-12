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

## 결과

`dataset/vault/` 26개 문서 → 청크 125개.

**1. 파서**
- 헤딩 없이 문서 전체를 한 청크로 처리한 것: 11개 (`##` 자체가 없는 `daily/`·`meetings/` 6개 + 구조화된 문서에서 첫 `##` 전 도입부 5개)
- 위키링크 26개 문서 전체 기준 해석 안 된 링크 0건
- `#todo` 같은 본문 인라인 태그가 프론트매터 `tags`와 합쳐져 뽑힘 (예: `daily/2026-01-14.md` → `apiserver, etcd, todo, 운영`)

**2. grep** — 확인한 대비:
- `"x509: certificate has expired"` (정확 토큰) → 2건 히트
- `"이미지 레지스트리를 왜 하나로 안 합쳤지"` (자연어) → **0건**. 문자열이 안 겹치면 완전히 무력하다는 걸 그대로 보여줌.

**3. Elasticsearch BM25(nori)** — 위 두 질문 모두 3건씩 히트, 관련 문서가 상위에 옴 (`이미지 레지스트리...` 질문 1위가 정답 문서 `decisions/이미지-레지스트리-harbor-vs-nexus.md#배경`). grep이 못 찾은 자연어 질문도 단어가 겹치면 찾아낸다는 걸 확인.

**4. pgvector** — `OPENAI_API_KEY` 확보 후 125청크 임베딩·색인, 검색까지 실행 완료. 세 유형 모두 1위가 정답 문서:
- `"이미지 레지스트리를 왜 하나로 안 합쳤지"` → 1위 `decisions/이미지-레지스트리-harbor-vs-nexus.md#배경` (유사도 0.4019)
- `"x509: certificate has expired 떴을 때 뭐부터 봤었나"` → 1위 `howto/kubeadm-인증서-갱신-절차.md#만료일 먼저 확인` (0.5472) — BM25 1위였던 troubleshooting 문서를 제치고 절차 문서가 1위로 올라온 점이 BM25와의 차이
- `"리더 선출이 리더가 죽어야만 일어나는 게 아니라는 내용 정리해둔 게 있었는데"` (단어가 문서와 거의 안 겹치는 개념 질문) → 1위 `learning/etcd-raft-리더선출-정리.md#선출이 일어나는 조건` (0.4768) — grep·BM25 모두 이 질문엔 약할 만한 케이스인데 벡터는 바로 찾음

**5. 세 방식 비교** (`src/evaluate.py`, `evaluation/queries.jsonl` 19건 전체, 문서 단위로 접어서 Hit@3/MRR 계산):

| | grep | BM25(nori) | pgvector |
|---|---:|---:|---:|
| **전체 Hit@3** (n=19) | 0.00 | 0.84 | 0.79 |
| **전체 MRR** | 0.00 | 0.82 | 0.67 |

유형별 MRR:

| type | n | grep | BM25 | pgvector |
|---|---:|---:|---:|---:|
| concept | 2 | 0.00 | 1.00 | 1.00 |
| cross-document | 2 | 0.00 | 1.00 | 0.50 |
| exact-token | 1 | 0.00 | 1.00 | 0.33 |
| low-signal | 1 | 0.00 | 1.00 | 1.00 |
| recall-command | 3 | 0.00 | 0.83 | 0.50 |
| recall-decision | 2 | 0.00 | 1.00 | 0.75 |
| recall-meeting | 2 | 0.00 | 1.00 | 0.75 |
| temporal | 1 | 0.00 | 0.00 | 0.25 |
| troubleshooting | 5 | 0.00 | 0.60 | 0.73 |

세 가지가 눈에 띈다.

- **grep은 전 유형 0.00.** 원본 질문 문자열을 그대로 grep에 넣었기 때문이다 — `exact-token` 질문도 실제로는 `"x509: certificate has expired 떴을 때 뭐부터 봤었나"`처럼 자연어 꼬리가 붙어 있어서 문서 원문과 완전히 일치하지 않는다. 순수 토큰만 잘라서 넣으면(`"x509: certificate has expired"`) grep도 찾는다는 건 이전 단계에서 이미 확인했다. 즉 grep의 약점은 "토큰 검색을 못 한다"가 아니라 **질문을 검색어로 다듬는 과정이 필요하다는 것**이고, 이 다듬는 과정 자체가 자동화하기 어렵다.
- **temporal(시간 필터) 유형은 BM25·pgvector 둘 다 실패.** "1월에 etcd 관련해서 무슨 일 있었지" 질문에 둘 다 `meetings/2026-02-05-...`(2월 문서, etcd 키워드가 많이 나옴)를 1위로 올렸다. **날짜 필터를 아예 구현 안 했기 때문**이다 — 지금 검색은 `content`만 보고 `date` 필드는 색인만 해두고 검색 조건으로 쓰지 않는다. 다음에 고칠 지점.
- **cross-document·recall-command에서 pgvector가 BM25보다 낮다.** 예를 들어 "아직 안 해봤거나 미뤄둔 일들 뭐 있었지"(Q-012, 여러 문서의 `#todo`를 모아야 하는 질문)는 BM25가 1위로 정답을 찾았는데 pgvector는 다른 결정 문서를 1위로 올렸다. 임베딩이 "미뤄둔 일"이라는 표현을 각 문서의 구체적인 todo 내용보다 결정 문서의 일반적인 뉘앙스에 더 가깝게 봤을 가능성이 있다 — 벡터 검색이 항상 이기는 게 아니라는 걸 보여주는 사례.

결과는 `data/ur2e/processed/eval_results.jsonl`에 질문별 원본 수치로 저장 (`.gitignore` 대상 — vault·queries.jsonl로부터 다시 만들 수 있는 산출물).

**6. GUI(`src/app.py`)로 청크 크기 실험** — grep+BM25만으로(무료) `heading` 방식과 `fixed` 방식 여러 크기를 같은 19문항에 돌린 결과:

| 청크 설정 | 청크 수 | 평균 길이(자) | BM25 Hit@3 | BM25 MRR |
|---|---:|---:|---:|---:|
| `heading` (기본, `##` 단위) | 125 | 163 | **0.84** | **0.82** |
| `fixed_300_50` | 96 | 261 | 0.79 | 0.77 |
| `fixed_800_100` | 41 | 563 | 0.79 | 0.74 |
| `fixed_1500_100` | 27 | 803 | 0.79 | 0.77 |

`##` 소제목 단위(`heading`)가 글자 수로 균등하게 자른 모든 `fixed` 설정보다 나았다. 이 데이터셋은 문서마다 `요약/증상/확인 내용/조치`처럼 이미 의미 단위로 나뉘어 있어서, 그 경계를 그대로 청크 경계로 쓰는 게 임의의 글자 수로 자르는 것보다 유리했다 — "청크 안에 한 가지 이야기만 담기"가 크기 자체보다 중요하다는 뜻. `fixed` 설정끼리는 크기를 늘려도(300→1500) BM25 점수가 크게 안 바뀌는데, 이건 `fixed` 청킹이 문장을 중간에서 자르면서 생기는 손해와 문맥을 더 담는 이득이 이 정도 규모의 데이터셋에서는 서로 상쇄됐기 때문으로 보인다.

GUI에서 슬라이더로 `fixed` 크기를 바꿔가며 같은 비교를 직접 해볼 수 있다.

## 배운 점

- 실제 개인 vault는 형식이 통일돼 있지 않다. 파서가 특정 프론트매터 필드를 필수로 가정하면 실제 vault에 붙이는 순간 깨진다.
- `# 제목` 줄을 title로 뽑아놓고 본문에서 안 지우면, `##` 구조가 있는 문서마다 "제목 한 줄짜리" 청크가 매번 생긴다 — 처음 돌렸을 때 25개 문서가 전부 헤딩 없는 청크로 잡혀서 발견했다.
- `[[위키링크]]`는 확장자 없는 파일명만 담고 있어서, vault 전체를 먼저 훑어 stem → 경로 매핑을 만들어야 실제 경로로 해석된다.
- grep과 BM25를 같은 질문 두 개로 나란히 돌려보니 차이가 숫자가 아니라 "찾음/못 찾음"으로 바로 보였다.
- BM25는 단어가 겹쳐야 하는 한계가 있는데, "리더 선출이 리더가 죽어야만 일어나는 게 아니라는 내용" 같이 문서 원문과 단어가 거의 안 겹치는 질문에서 pgvector가 바로 정답을 1위로 찾은 걸 보고 grep→BM25→벡터 순으로 "무엇을 못 찾던 게 다음 단계에서 풀리는지"가 눈에 보였다.
- 다만 같은 질문에서 방식마다 1위 문서가 달랐다(`x509` 질문: BM25는 증상 섹션, 벡터는 절차 문서). 정답이 여러 개(`expected_supporting`)인 이유이기도 하고, 한 방식만 믿으면 안 되는 이유이기도 하다 — 다음 단계에서 숫자로 비교해봐야 함.
- 질문 유형(정확 토큰 회상 / 명령어 회상 / 결정 회상 / 개념 회상 / 시간 필터 / 복수 문서 종합)에 따라 grep·BM25·벡터 검색의 강약이 다르다. 한 방식만으로는 전체를 못 풀게 평가셋을 구성했다.
- 19건 전체로 돌려보니 예상과 다른 지점이 있었다: `temporal` 유형은 BM25·pgvector 둘 다 0.00이었다. "1월에"라는 조건을 두 방식 다 무시하고 내용 유사도로만 순위를 매기기 때문이다 — **검색 엔진이 좋아져도 `date` 필드를 조건으로 안 쓰면 시간 질문은 못 푼다**는 걸 숫자로 확인했다. grep이 개념적으로 약할 거라 예상한 지점 말고, 구현이 아직 안 된 지점(날짜 필터)이 드러난 것.
- pgvector가 항상 이기지는 않았다. `cross-document`·`recall-command`에서 BM25보다 낮았다 — 벡터 검색도 만능이 아니라는 걸 직접 확인.
- 청크 크기를 실험할 수 있게 만들려고 GUI에서 메모리 상의 `Chunk` 객체를 검색 함수에 바로 넘겼는데, 검색 함수들은 전부 `chunks.jsonl`을 다시 읽어서 만든 dict를 기대하고 있어서 `'Chunk' object is not subscriptable` 에러가 났다. dataclass와 dict를 섞어 쓰면 이런 식으로 터진다는 걸 실제로 겪었다 — `to_dicts()` 변환 함수를 하나 두고 경계를 분명히 했다.
- 청크 "크기"만 실험해보면 결론이 반대로 나올 수도 있었다. `##` 단위(평균 163자)가 훨씬 큰 `fixed` 설정들(261~803자)보다 전부 나았던 건 크기가 작아서가 아니라 **의미 단위(증상/조치 등)가 청크 경계와 일치해서**였다 — 크기 자체보다 "청크 안에 한 가지 이야기만 담기"가 더 중요하다는 걸 숫자로 확인.

## 다음 단계

- [x] `src/parse_vault.py`: md → 청크 JSONL 파서 (제목 폴백, `##` 없는 문서 처리, 인라인 `#태그`/`[[링크]]` 추출)
- [x] grep 베이스라인
- [x] Elasticsearch(nori) BM25 검색
- [x] pgvector 벡터 검색
- [x] `evaluation/queries.jsonl` 기준 Hit@3 / MRR을 질문 유형별로 측정
- [x] GUI(`src/app.py`)로 청크 방식·크기를 바꿔가며 재색인·재검색·재평가
- [ ] 검색 결과에 날짜 필터 반영 (`temporal` 유형이 지금 0.00인 원인)
- [ ] Claude Code가 검색 결과를 근거로 답을 정리하는 RAG 흐름
- [ ] 실제 vault 경로로 교체 검증 (사내망)
