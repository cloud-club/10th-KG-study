---
title: 이 저장소 자체를 데이터로 한 GraphRAG — 청크 · 그래프 · LLM 위키 비교
date: 2026-10-20
tags: [graphrag, knowledge-graph, text2cypher, global-search, community-detection, hybrid-search, rrf, neo4j, elasticsearch, llm-wiki]
status: done
---

# 07. 이 저장소 자체를 데이터로 한 GraphRAG

> 관련 노트: [`../../notes/11-repo-graphrag-insights.md`](../../notes/11-repo-graphrag-insights.md)(설계·인사이트 정리) · `../../notes/08-llm-wiki.md`
> 위키: [GraphRAG](../../../../wiki/concepts/GraphRAG.md) · [Text2Cypher](../../../../wiki/concepts/Text2Cypher.md)
> **질의–답변 원문: [`QA.md`](QA.md)** — 질문 12개에 대한 세 방식의 답을 나란히 놓은 정성평가용 문서

## 목표

6주차에 멤버들이 남긴 열린 질문 세 가지를, 10기 저장소(`members/` 노트·실습 187편)를 데이터로 삼아 직접 확인한다.

1. **공정 비교** — 6주차에는 다섯 멤버 모두 그래프 범위가 청크 범위보다 좁았다. 여기서는 v1(청크)과 v2(그래프)가 **같은 전체 코퍼스**에서 출발한다.
2. **글로벌 서치** — "그래프가 작아서" 아무도 구현하지 못했다. 의미 그래프 위에서 Leiden 커뮤니티 탐지와 커뮤니티 요약을 처음으로 돌린다.
3. **LLM 위키는 무엇인가** — 우리가 6주간 운영한 `wiki/`는 같은 노트를 LLM이 미리 합성해 둔 층이다. 이것을 v3로 놓고 "인덱싱을 언제 누가 했나"의 차이로 비교한다.

## 환경

- Python 3.12 (`.venv`), `requirements.txt`
- 공용 인프라 `docker-compose.yml`의 Neo4j 5.26 + APOC, Elasticsearch 9.1 + nori
- LLM·임베딩: OpenAI 호환 게이트웨이 하나로 모두 부른다. 루트 `.env`에 `LLM_BASE_URL`·`LLM_API_KEY`를 둔다.
  - **추출 `gpt-5.6-terra`**(추론 모델, effort 기본값 medium). `gpt-5.4-mini`와의 비교는 아래 [추출 모델 비교](#추출-모델-비교--mini-vs-terra)
  - 생성·요약 `gpt-5.4-mini`, 임베딩 `gemini-embedding-2`(3072차원), 채점 `claude-sonnet-5-5`(생성과 다른 계열)
  - 모델 바꾸기: `GRAPHRAG_EXTRACT_MODEL` · `GRAPHRAG_EXTRACT_EFFORT` · `GRAPHRAG_CHAT_MODEL` · `GRAPHRAG_EMBED_MODEL`

## 실행 방법

```bash
docker compose up -d neo4j elasticsearch        # 저장소 루트에서
cd members/sese2204/labs/07-repo-graphrag
uv venv -p 3.12 .venv && VIRTUAL_ENV=.venv uv pip install -r requirements.txt
cd src
python load_structure.py   # 구조 층 + 위키 층 → Neo4j (DB 를 비우고 다시 적재)
python embed_index.py      # 청크 임베딩 → ES(nori BM25 + dense_vector) · Neo4j 벡터 인덱스, 위키 청크 인덱스
python extract.py          # 의미 층 추출 (note·lab 문서, terra 368회 호출) → outputs/extract.json
python load_semantic.py    # 사전 · 추출 결과 → Neo4j
python communities.py      # Leiden + 커뮤니티 요약 → (:Community)
python ask.py "질문"        # v1 · v2 · v3 동시 답변 (--mode, --route, --show)
python eval.py             # 질문 12개 × 3방식 채점 → outputs/eval.json
python qa_report.py        # 채점 결과 → ../QA.md (정성평가용 질의–답변)
python judge_extract.py --n 60 ../outputs/extract.json   # 추출 정확도를 원문과 대조
```

모든 LLM·임베딩 호출은 `outputs/*.jsonl`에 캐시된다. 같은 입력이면 다시 부르지 않으니 파이프라인을 처음부터 다시 돌려도 결과가 같다. `outputs/`는 git에 올리지 않는다.

### 다른 곳에서 보기 — `snapshot/`

**LLM 키 없이 그래프만 보기**: Neo4j만 있으면 된다.

```bash
docker compose up -d neo4j                      # 저장소 루트에서
cd members/sese2204/labs/07-repo-graphrag
uv venv -p 3.12 .venv && VIRTUAL_ENV=.venv uv pip install -r requirements.txt
cd src && python snapshot.py load               # 기존 Neo4j 데이터는 지운다. 노드 3,017 · 관계 12,701 (terra 그래프)
```

그다음 Neo4j Browser(http://localhost:7474)에서 `demo.cypher`의 쿼리를 하나씩 실행한다. 스냅샷에는 임베딩이 없어서(약 200MB, GitHub 파일 한도 초과) 벡터 인덱스는 비어 있다. `demo.cypher`는 임베딩을 쓰지 않는다.

**키가 있으면 같은 결과로 재빌드**: `cp ../snapshot/cache/*.jsonl ../outputs/` 뒤에 위 실행 순서대로 돌린다. 추출(terra·mini 둘 다)·커뮤니티 요약·Dataset 매핑·답변·채점은 캐시에서 나오고, 임베딩만 새로 부른다(청크 2,048 + 위키 409 + 질문). 채점 원본 1~5회차와 추출 정확도 기록은 `snapshot/results/`에 있다.

스냅샷을 갱신하려면 파이프라인을 돌린 뒤 `python snapshot.py export`.

### 사내망에서 겪은 것

- `docker compose build elasticsearch`가 nori 설치에서 `PKIX path building failed`로 실패했다. 사내망 SSL 가로채기 때문에 컨테이너 안의 Java가 인증서를 믿지 않는다. 호스트에서 `analysis-nori-9.1.0.zip`을 받아 `file://`로 설치한 임시 이미지를 같은 태그(`kg-study/elasticsearch:9.1.0`)로 빌드하고 `--no-build`로 띄웠다. 공용 Dockerfile은 고치지 않았다.
- Neo4j GDS도 기동할 때 내려받는 구조라 같은 문제가 생긴다. 그래서 커뮤니티 탐지는 GDS 대신 **igraph + leidenalg**로 계산하고 결과만 Neo4j에 썼다.
- 게이트웨이의 `qwen3-embedding-*`은 `not available`이라 `gemini-embedding-2`를 썼다.

## 구조

```
src/
├── common.py          경로·클라이언트·JSON 캐시·임베딩
├── corpus.py          소재 수집·청킹·주차 추정
├── load_structure.py  구조 층 + 위키 층 적재
├── embed_index.py     ES·Neo4j 인덱스
├── entities.yaml      닫힌 엔티티 사전 (Technique 46 · Tool 18)
├── extract.py         의미 층 추출 + 검증
├── judge_extract.py   추출 정확도 채점 (원문 대조)
├── load_semantic.py   의미 층 적재 + Dataset 정규화
├── communities.py     Leiden + 커뮤니티 요약
├── ask.py             v1 · v2(local/aggregate/global) · v3
├── questions.yaml     평가 질문 12개 + gold
├── eval.py            채점
├── qa_report.py       QA.md 생성
└── snapshot.py        스냅샷 내보내기·불러오기
snapshot/              graph.json.gz(임베딩 제외 그래프) · cache/(LLM 캐시) · results/(채점·추출 정확도 원본)
QA.md                  질의–답변 원문 (자동 생성)
demo.cypher            Neo4j Browser 시연용 쿼리
```

## 스키마 — 어떻게 정했나

5주차 [폐쇄 스키마 설계](../../../../wiki/concepts/폐쇄-스키마-설계.md)의 순서(**질문 → 필요한 관계 → 스키마**)를 따랐다. 핵심은 **LLM이 정하는 범위를 최소로 줄이는 것**이다.

| 층 | 노드 · 관계 | 누가 만드나 |
|---|---|---|
| 구조 | `(Member)-[:WROTE]->(Document)-[:HAS_CHUNK]->(Chunk)`, `TAGGED→Tag`, `IN_WEEK→Week` (Member 14 · Document 187 · Chunk 2,048 · Tag 156) | 파서 (결정적) |
| 사전 | `Technique` 46 · `Tool` 18, `PART_OF` 17, `(Chunk)-[:MENTIONS]->` 5,562 | 사람이 정한 사전 + 별칭 매칭 (결정적) |
| 의미 | `Finding` 225 (`kind`: measured 197 / cited 28), `Pitfall` 223, `Dataset` 9 · `ABOUT` 426 · `COMPARED_WITH {outcome}` 100 · `ON_DATA` 86 · `OCCURS_IN` 413 · `MITIGATED_BY` 83 · `EVIDENCED_BY→Chunk` 448 | LLM 추출(terra) + 검증 |
| 커뮤니티 | `Community` 12 (요약 대상), `IN_COMMUNITY` 493 | Leiden + LLM 요약 |
| 위키 (v3 전용) | `WikiPage` 53 · `LINKS_TO` 585 · `CITES→Document` 582 · `Contradiction` 20 | 파서 |

전체 노드 3,017개, 관계 1만 2,701개 (`main` `162b822` 기준).

- **누가 확인했는지는 LLM에 묻지 않는다.** `Finding`→`Chunk`→`Document`→`Member` 경로로 정해진다. `(Member)-[:REPORTED]->(Finding)`은 그 경로를 접어 둔 파생 관계다.
- **"측정했다"와 "정리했다"를 구분한다.** 위키 규칙(CLAUDE.md)을 그대로 스키마에 옮겨 `Finding.kind`(measured·cited)로 둔다.
- **`Finding`은 중간 노드다.** 값을 조건과 함께 남기기 위해서다(dldusgh318의 `TechnologyUse` 방식).
- **엔티티 이름은 사전으로 닫았다.** 위키 페이지 이름과 노트 태그 156개를 보고 직접 큐레이션했다. 위키에서는 **이름만** 가져오고 내용은 가져오지 않았다. 추출 결과의 사전 밖 이름 누수는 0건이다.
- **검증을 통과한 것만 채택한다.** `evidence`가 해당 청크 원문에 실제로 없으면 버렸다(terra 97건 탈락, 그중 52건이 원문 대신 요약을 적은 경우). 스키마에 맞지 않는 사실은 억지로 넣지 않고 `review_queue`(23건)에 모았다(heebindev 처방).
- **청크 공동 언급은 커뮤니티 투영에 넣지 않는다.** `RAG`·`지식그래프` 같은 허브가 전부를 한 덩어리로 묶기 때문이다.

### 범위

- `members/<id>/`의 notes·labs md·readings·README, `main` `162b822`(PR #45 머지 후) 기준 187편. 1~4회차는 `fd8b7f6` 기준 177편이었다. 미머지 PR(#6·#42)은 넣지 않았다.
- **이 실습 자신(`labs/07-repo-graphrag/`)과 정리 노트(`notes/11-…`)는 뺐다.** 질문·gold·답변이 그대로 들어 있어서 코퍼스에 섞이면 정답이 샌다. PR #50·#51을 머지한 뒤 재빌드하다가 이 문서들이 코퍼스에 들어간 것을 발견했고, `corpus.py`의 `SELF` 규칙으로 막았다.
- 실습 데이터(`dataset/`·`note-templates/`)는 소재가 아니라서 뺐다.
- 주차는 **추정치**다. 제목의 "N주차"(22편) → 경로의 `weekN`(24편) → 날짜 구간(141편) 순으로 정한다. 노트를 몰아서 올린 멤버(sunghyun 1~4주차가 09-30 커밋)는 날짜만으로 틀리기 때문에 제목을 먼저 본다.

## 추출 모델 비교 — mini vs terra

처음에는 `gpt-5.4-mini`로 추출했다(이 비교는 PR #45 머지 전 177편 기준이다). 질문 채점에서 그래프 쪽 오답을 추적하다 보니, 원인이 추출에 있었다. 그래서 추출한 사실 하나하나를 원문 청크와 대조해 채점했다(심판 `claude-sonnet-5-5`, `judge_extract.py`). 추출만 `gpt-5.6-terra`로 바꿔 같은 방식으로 비교했다.

| 원문 대조 (전체에서 무작위, seed 42) | gpt-5.4-mini | gpt-5.6-terra |
|---|---:|---:|
| Finding 내용이 원문과 맞음 (60건) | 82% | 88% |
| 측정/인용 구분이 맞음 (60건) | 58% | **100%** |
| **승패 방향이 맞음** (방향 있는 것만 30건) | **13%** | **90%** |
| Pitfall 내용이 원문과 맞음 (40건) | 85% | 95% |
| 실제로 부딪힌 함정임 (40건) | 35% | 88% |
| 개수: Finding / 직접 측정 / Pitfall | 923 / 279 / 495 | 215 / 187 / 204 |
| 토큰: 입력 / 출력(추론 포함) | 87만 / 32.3만 | 87만 / **16.0만** (추론 6.3만) |
| 시간 (8병렬, 337회) | 2분 30초 | 3분 |

- **mini의 승패 방향은 사실상 무작위였다.** 원문에 없는 비교를 지어내고(예: RRF 정의만 있는 청크에 "점수 정규화에 이겼다"), "목표·계획" 절을 결과로 뽑았다. 처음에 "dldusgh318 사례에서 방향이 뒤집혔다"고 적은 것은 사례 하나가 아니라 전반적인 문제였다.
- **terra는 덜 뽑고 정확하게 뽑는다.** 출력이 절반이라 단가 차이만큼만 비용이 늘었다. 대신 인용(cited) Finding은 28건만 남았다. 프롬프트가 인용도 뽑으라고 했지만 terra는 직접 실험에 집중했다. "누가 무엇을 공부했나"는 `MENTIONS`가 따로 담고 있다.
- terra의 오답은 대부분 "청크에 없는 정보 덧붙이기"였다. 옆 청크의 청크 수나 데이터 이름을 끌어오는 식이다.
- 표본 7편(`extract.py --sample 7`) 결과도 같은 방향이었다. 승패 방향 정확도가 mini 1/10, terra 7/8.

## 질의 — 세 방식

| | 근거 | 경로 |
|---|---|---|
| **v1** 청크 하이브리드 | `members/` 청크 2,048 | nori BM25 top-50 + kNN top-50 → RRF(k=60) → 8청크. 3주차와 같은 조건 |
| **v2** GraphRAG | v1 청크 + 구조·의미 그래프 | LLM이 경로 **분류만** 하고 질의는 코드가 정한다. **local**: 질문의 엔티티(사전 매칭) → Finding·Pitfall 확장 → 질문 유사도로 재정렬 15개 + 진입 청크 5개. **aggregate**: Text2Cypher(쓰기 구문·v3 라벨 거절, READ 세션, 1회 수정 재시도, 0행이면 local로 폴백). **global**: 커뮤니티 요약 Map(관련도 30 이상) → Reduce |
| **v3** LLM 위키 | `wiki/` 청크 409 | 위키 청크 RRF 6개 + 위키링크 1홉 이웃 요약 5개 (동점은 이름순) |

## 결과

질문 12개(6주차 분류: 단일 사실 · 교차 멤버 · 멀티홉 · 집계 · 글로벌 · 모순 · 근거 없음). gold는 원문과 대조해 사람이 확정했다(`questions.yaml`의 `gold_source`). **답변 원문은 [`QA.md`](QA.md)(5회차)에 있다.**

### 점수 — 참고만 한다

| 회차 | 바꾼 것 | v1 | v2 | v3 |
|---|---|---:|---:|---:|
| 1 | mini 추출 | 6.5 | 8.0 | 7.5 |
| 2 | + Text2Cypher 처방(정규 이름 목록, 0행 폴백) | 6.5 | 7.5 | 7.5 |
| 3 | + terra 추출 | 6.5 | 8.0 | 6.5 |
| 4 | + v3 이웃 동점 순서 고정 | 6.5 | 8.0 | 6.5 |
| 5 | + PR #45 머지(문서 177 → 187, 자기 문서 제외), Q07 gold 갱신 | 5.0 | 7.0 | 6.0 |

correct 1 · partial 0.5. 판정은 각 회차 1회.

**점수 차이는 노이즈와 구별되지 않는다.** 3회차에 v3는 코드도 데이터도 그대로인데 7.5에서 6.5로 떨어졌다. v1 답은 12개가 모두 2회차와 같았는데, v3 답은 12개가 모두 달랐다. v3가 쓰는 위키링크 이웃 쿼리에 동점 순서가 정해져 있지 않아서, DB를 스냅샷에서 다시 불러오며 컨텍스트가 바뀐 것으로 보인다. 4회차에 이름순으로 고정한 뒤에는 두 번 돌려 같은 점수가 나왔다. 아무것도 바꾸지 않아도 1점이 흔들리는 셈이니, 질문 12개로 0.5~1점 차이를 말할 수 없다.

5회차에 세 방식이 함께 내려간 것은 노이즈가 아니라 **데이터가 늘어서 생긴 실제 퇴행**이다(아래 Q01). 1~4회차의 Q07 gold(dldusgh318 10)는 새 코퍼스에서 17로 바뀌어 갱신했다. 그래서 아래 정성 관찰과 추출 정확도 지표를 본다.

### 정성 관찰 (5회차 답변 기준, [`QA.md`](QA.md))

| 질문 유형 | 관찰 |
|---|---|
| **단일 사실** (Q01) | **데이터가 늘자 퇴행했다.** 4회차까지 셋 다 맞혔는데, PR #45로 dldusgh318의 6주차 결과표가 들어오자 v1은 그 표의 "v1/v2" 수치(0.5/0.5, 0.333…)를 **kdyann의 결과로 읽었다.** 청크 머리에 작성자 경로가 있었는데도 그랬다. 6주차에 모든 멤버가 "v1/v2"라는 같은 이름을 썼기 때문이다. v2는 정답 청크(kdyann 결과표)가 새 문서들에 밀려 진입 청크 5개 밖으로 빠지면서 "근거 없음"이 됐다. v3만 위키 덕분에 그대로 맞혔다 |
| **단일 사실** (Q02) | 세 방식이 거의 같은 답을 냈다. 셋 다 "4/9 → 3/9"만 말하고 원인(Task→Test Case 직접 연결로 13개를 18개로 셈)을 빠뜨렸다. 답이 한 문서에 있으면 그래프는 덧붙일 것이 없다 |
| **교차 멤버** (Q03) | 성격이 셋 다 다르다. v1은 Yeongeunn 한 명을 찾고 "다른 멤버의 근거는 없다"고 **단정**했다. v3는 위키 덕분에 **다섯 이름을 모두 댔지만** 조건·수치가 빠졌고, lys0611·e0ng은 "RRF가 이긴 사례"라며 스스로 모순됐다. v2(Text2Cypher)는 3명만 찾았지만 **조건과 수치가 정확**하다(lys0611 R@10 RRF 0.907 < BM25 0.926, do-dop BM25 1위 → RRF 11위). do-dop을 gold는 "정규화 융합 비교라 별개"로 뺐지만, 그래프가 근거로 든 것은 실제로 BM25 단독 1위 문서가 RRF에서 11위로 밀린 사례다. gold의 경계가 좁았던 것에 가깝다 |
| **교차 멤버** (Q04) | 셋 다 흔들렸다. lys0611처럼 지표마다 BM25와 벡터가 번갈아 이긴 멤버가 있어서, "누가 더 나았다고 측정했나"는 답이 하나로 정해지지 않는 질문이었다. v2는 lys0611을 양쪽에 넣었다. 데이터로는 맞지만 답으로는 모순이다. 질문 설계의 문제다 |
| **멀티홉** (Q05) | 세 방식 모두 heebindev를 정확히 지목했다. heebindev 실습 README 한 곳에 다 적혀 있어서 청크 검색으로 충분했다. 5회차 v1은 새로 들어온 dldusgh318의 Text2Cypher 기록과 heebindev를 구분해 "dldusgh318은 이 문제를 언급한 근거가 없다"고까지 밝혔다. "멀티홉이면 그래프"가 아니라는 6주차 결론과 같다 |
| **집계** (Q06·Q07) | **v2만 답했다.** 생성된 Cypher가 짧고 정확하다(`MATCH (m)-[:WROTE]->(d) WHERE d.kind='lab' … count`). 주목할 점은 v1·v3가 Q07에서 숫자를 지어내지 않고 **"근거 없음"으로 멈췄다**는 것이다. v1은 Q06에서 GraphRAG 노트를 쓴 멤버 4명을 추측해 틀렸다(4회차에는 5명) |
| **집계·함정** (Q08) | v1·v3는 "구현한 멤버 없음"을 근거와 함께 깔끔하게 답했다. v2는 Cypher가 0행이라 local로 폴백했다. 그런데 답변 **첫 문장에서 "heebindev와 sunghyun이 구현한 것으로 확인된다"고 했다가 뒤에서 뒤집었다.** 엔티티 주변 사실(커뮤니티 탐지를 *언급한* 멤버)이 생성 모델을 오도했다. 그래프 컨텍스트가 "관련 있음"과 "해당함"을 구분하지 않는 함정이다 |
| **글로벌** (Q09) | 어느 방식도 gold(사람이 쓴 최종 정리)와 겹치지 않았다. 각자 **자기 렌즈**로 답했다. v1은 검색된 두 멤버(dldusgh318·sese2204)의 파이프라인 교훈, v2는 커뮤니티 요약에서 나온 검색·평가 실패 패턴, v3는 위키 허브의 KG 중심 교훈이었다. "공통 교훈"은 정답이 하나인 질문이 아니라서 정성으로 읽어야 한다 |
| **글로벌** (Q10) | v3만 순서를 맞혔다. 위키 허브에 주차 타임라인이 있기 때문이다. v2 global은 커뮤니티에 시간 정보가 없어 순서를 재구성하다 틀렸고, v1은 순서를 뒤집었다 |
| **모순** (Q11) | 셋 다 do-dop의 57청크/69청크 역전을 맞혔다. **v1이 가장 정확했다**(R@5 100% vs 96.7% 수치까지). 원문 청크에 수치가 그대로 있었다. v3는 역전의 메커니즘(q009 점수 쏠림)을 가장 잘 설명했다 |
| **근거 없음** (Q12) | v1·v2는 "근거 없음". **v3만 함정에 걸렸다.** 위키의 "KURE(bge-m3를 한국어로 파인튜닝한 모델)" 문장을 보고 "lys0611이 파인튜닝된 모델로 비교했다"며 lys0611을 지목했다. 1~3회차에는 맞혔던 문항이다. 이웃 페이지 구성이 바뀌자 걸렸다 |

## 인사이트 요약

자세한 설계와 해석은 [노트 11](../../notes/11-repo-graphrag-insights.md)에 정리했다.

- **그래프는 세기·모으기에서만 이긴다.** 집계는 v2만 풀었고, 교차 멤버 질문에서는 그래프만 정확한 조건과 수치를 붙였다. 답이 한 문서에 있으면 청크로 충분하다.
- **그래프 품질의 상한은 추출 모델이다.** mini의 승패 방향 정확도 13%는 그래프 위의 모든 비교 질문을 오염시킨다. 추출에는 좋은 모델을 쓰고, 답변 생성은 싼 모델로 충분했다.
- **경로 선택과 컨텍스트 해석이 다음 병목이다.** "누구이고 어떤 조건"이라는 표현은 aggregate로 갔다. 폴백한 local에서는 언급만 한 멤버를 해당자로 읽었다(Q08).
- **위키(v3)는 사람이 미리 답을 쓴 질문에 강하고, 그 문장에 끌려간다.** 타임라인(Q10)은 혼자 맞혔고, 모델 설명 문장(Q12)에는 걸렸다.
- **질문 12개로는 정답률을 비교할 수 없다.** 아무것도 바꾸지 않아도 1점이 흔들렸다. 비교는 추출 정확도 같은 단계별 지표와 정성 읽기로 한다.
- **데이터가 늘면 검색은 경쟁하고, 같은 이름은 섞인다.** 문서 10편이 늘자 정답 청크가 밀려나고(v2), 여러 멤버가 같은 이름("v1/v2")으로 쓴 결과표가 남의 결과로 읽혔다(v1). do-dop이 기록한 "엔티티 혼동(다른 회사의 사실을 섞어 답함)"이 우리 스터디 데이터에서 재현됐다.

## 함정 · 주의

- **v3는 공정한 경쟁자가 아니다.** 위키는 같은 노트를 읽고 LLM이 합성한 결과이고, 일부 gold의 출처(Q03·Q04·Q11)가 위키 자체다. v3가 잘했다는 결과는 "미리 합성해 둔 질문에는 답이 있다"는 뜻이지 검색 성능이 아니다.
- **gold도 판단이다.** Q03의 do-dop처럼 gold가 경계를 좁게 잡은 곳이 있고, Q04처럼 결과가 섞인 멤버를 한쪽으로 분류한 곳이 있다. 심판은 그 gold로만 채점한다.
- **Dataset 정규화가 처음에 틀렸다.** "lab 노트"·"개인 노트"처럼 데이터 종류를 특정할 수 없는 표현 42개가 전부 `옵시디언 노트`로 묶였다. 정규화 프롬프트에 "출처가 명시된 경우만" 규칙을 넣어 null로 돌렸다. LLM 정규화는 `outputs/datasets.json`을 사람이 한 번 봐야 한다.
- **evidence 검증은 문자열 일치만 본다.** 근거 문구가 원문에 있어도 승패 방향이나 단위(문항 하나 vs 평균)까지 맞는다는 보장은 없다. 그래서 원문 대조 채점(`judge_extract.py`)을 따로 둔다.
- **민감 정보:** 노트에는 개인 문서 제목 같은 것이 섞여 있다. 추출 프롬프트가 데이터를 유형으로만 적게 하지만, Finding의 `evidence`·`value`에는 원문이 그대로 들어간다. 원문은 이미 공개 저장소에 있는 멤버 노트이고, 이 README에는 옮기지 않았다.

## 다음 할 일

- Text2Cypher 사후 검증: "구현·측정" 질문인데 `kind` 필터가 없으면 거절하는 규칙(질의 의도–쿼리 대조).
- 그래프 컨텍스트에 "언급"과 "해당"을 구분하는 표시를 붙이기(Q08). 예: 사실마다 `kind`와 관계 종류를 앞에 적는다.
- 라우터 오분류 대응: local과 aggregate를 둘 다 돌려 합치기.
- 글로벌 요약에 기법을 가로지르는 교훈과 시간 축을 담을 상위 계층 요약.
- terra의 인용(cited) 재현율 — 인용만 따로 뽑는 패스를 둘지.
