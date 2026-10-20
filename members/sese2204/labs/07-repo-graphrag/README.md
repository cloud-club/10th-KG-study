---
title: 이 저장소 자체를 데이터로 한 GraphRAG — 청크 · 그래프 · LLM 위키 비교
date: 2026-10-20
tags: [graphrag, knowledge-graph, text2cypher, global-search, community-detection, hybrid-search, rrf, neo4j, elasticsearch, llm-wiki]
status: in-progress
---

# 07. 이 저장소 자체를 데이터로 한 GraphRAG

> 관련 노트: `../../notes/08-llm-wiki.md` · 위키 [GraphRAG](../../../../wiki/concepts/GraphRAG.md) · [Text2Cypher](../../../../wiki/concepts/Text2Cypher.md)

## 목표

6주차에 멤버들이 남긴 열린 질문 세 가지를, 10기 저장소(`members/` 노트·실습 177편)를 데이터로 삼아 직접 확인한다.

1. **공정 비교** — 6주차에는 다섯 멤버 모두 그래프 범위가 청크 범위보다 좁았다. 여기서는 v1(청크)과 v2(그래프)가 **같은 전체 코퍼스**에서 출발한다.
2. **글로벌 서치** — "그래프가 작아서" 아무도 구현하지 못했다. 노드 1,482개 규모의 의미 그래프에서 Leiden 커뮤니티 탐지와 커뮤니티 요약을 처음으로 돌린다.
3. **LLM 위키는 무엇인가** — 우리가 6주간 운영한 `wiki/`는 같은 노트를 LLM이 미리 합성해 둔 층이다. 이것을 v3로 놓고 "인덱싱을 언제 누가 했나"의 차이로 비교한다.

## 환경

- Python 3.12 (`.venv`), `requirements.txt`
- 공용 인프라 `docker-compose.yml`의 Neo4j 5.26 + APOC, Elasticsearch 9.1 + nori
- LLM·임베딩: OpenAI 호환 게이트웨이 하나로 모두 부른다. 루트 `.env`에 `LLM_BASE_URL`·`LLM_API_KEY`를 둔다(모델 바꾸기: `GRAPHRAG_CHAT_MODEL`·`GRAPHRAG_EMBED_MODEL`)
  - 생성·추출 `gpt-5.4-mini`, 임베딩 `gemini-embedding-2`(3072차원), 채점 `claude-sonnet-5-5`(생성과 다른 계열)

## 실행 방법

```bash
docker compose up -d neo4j elasticsearch        # 저장소 루트에서
cd members/sese2204/labs/07-repo-graphrag
uv venv -p 3.12 .venv && VIRTUAL_ENV=.venv uv pip install -r requirements.txt
cd src
python load_structure.py   # 구조 층 + 위키 층 → Neo4j (DB 를 비우고 다시 적재)
python embed_index.py      # 청크 임베딩 → ES(nori BM25 + dense_vector) · Neo4j 벡터 인덱스, 위키 청크 인덱스
python extract.py          # 의미 층 추출 (note·lab 문서, 337회 호출) → outputs/extract.json
python load_semantic.py    # 사전 · 추출 결과 → Neo4j
python communities.py      # Leiden + 커뮤니티 요약 → (:Community)
python ask.py "질문"        # v1 · v2 · v3 동시 답변 (--mode, --route, --show)
python eval.py             # 질문 12개 × 3방식 채점 → outputs/eval.json
```

모든 LLM·임베딩 호출은 `outputs/*.jsonl`에 캐시된다. 같은 입력이면 다시 부르지 않으니 파이프라인을 처음부터 다시 돌려도 결과가 같다(재실행해 Finding 923 · Pitfall 495가 그대로 나오는 것을 확인했다). `outputs/`는 git에 올리지 않는다.

### 다른 곳에서 보기 — `snapshot/`

**LLM 키 없이 그래프만 보기**: Neo4j만 있으면 된다.

```bash
docker compose up -d neo4j                      # 저장소 루트에서
cd members/sese2204/labs/07-repo-graphrag
uv venv -p 3.12 .venv && VIRTUAL_ENV=.venv uv pip install -r requirements.txt
cd src && python snapshot.py load               # 기존 Neo4j 데이터는 지운다. 노드 3,860 · 관계 17,888
```

그다음 Neo4j Browser(http://localhost:7474)에서 `demo.cypher`의 쿼리를 하나씩 실행한다. 스냅샷에는 임베딩이 없어서(약 200MB, GitHub 파일 한도 초과) 벡터 인덱스는 비어 있다. `demo.cypher`는 임베딩을 쓰지 않는다.

**키가 있으면 같은 결과로 재빌드**: `cp ../snapshot/cache/*.jsonl ../outputs/` 뒤에 위 실행 순서대로 돌린다. 추출·커뮤니티 요약·Dataset 매핑·채점은 캐시에서 나오고, 임베딩만 새로 부른다(청크 1,928 + 위키 409 + 질문). 채점 원본은 `snapshot/results/`에 있다.

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
├── load_semantic.py   의미 층 적재 + Dataset 정규화
├── communities.py     Leiden + 커뮤니티 요약
├── ask.py             v1 · v2(local/aggregate/global) · v3
├── questions.yaml     평가 질문 12개 + gold
├── eval.py            채점
└── snapshot.py        스냅샷 내보내기·불러오기
snapshot/              graph.json.gz(임베딩 제외 그래프) · cache/(LLM 캐시) · results/(채점 원본)
demo.cypher            Neo4j Browser 시연용 쿼리
```

## 스키마 — 어떻게 정했나

5주차 [폐쇄 스키마 설계](../../../../wiki/concepts/폐쇄-스키마-설계.md)의 순서(**질문 → 필요한 관계 → 스키마**)를 따랐다. 핵심은 **LLM이 정하는 범위를 최소로 줄이는 것**이다.

| 층 | 노드 · 관계 | 누가 만드나 |
|---|---|---|
| 구조 | `(Member)-[:WROTE]->(Document)-[:HAS_CHUNK]->(Chunk)`, `TAGGED→Tag`, `IN_WEEK→Week` | 파서 (결정적) |
| 사전 | `Technique` 46 · `Tool` 18, `PART_OF` 17, `(Chunk)-[:MENTIONS]->` 5,362 | 사람이 정한 사전 + 별칭 매칭 (결정적) |
| 의미 | `Finding` 923 (`kind`: measured 279 / cited 644), `Pitfall` 495, `Dataset` 12 · `ABOUT` · `COMPARED_WITH {outcome}` · `ON_DATA` · `OCCURS_IN` · `MITIGATED_BY` · `EVIDENCED_BY→Chunk` | LLM 추출 + 검증 |
| 커뮤니티 | `Community` 12 (요약 대상), `IN_COMMUNITY` | Leiden + LLM 요약 |
| 위키 (v3 전용) | `WikiPage` 53 · `LINKS_TO` 585 · `CITES→Document` 564 · `Contradiction` 20 | 파서 |

- **누가 확인했는지는 LLM에 묻지 않는다.** `Finding`→`Chunk`→`Document`→`Member` 경로로 정해진다. `(Member)-[:REPORTED]->(Finding)`은 그 경로를 접어 둔 파생 관계다.
- **"측정했다"와 "정리했다"를 구분한다.** 위키 규칙(CLAUDE.md)을 그대로 스키마에 옮겨 `Finding.kind`(measured·cited)로 둔다.
- **`Finding`은 중간 노드다.** 값을 조건과 함께 남기기 위해서다(dldusgh318의 `TechnologyUse` 방식).
- **엔티티 이름은 사전으로 닫았다.** 위키 페이지 이름과 노트 태그 156개를 보고 직접 큐레이션했다. 위키에서는 **이름만** 가져오고 내용은 가져오지 않았다. 추출 결과의 사전 밖 이름 누수는 0건이다.
- **검증을 통과한 것만 채택한다.** `evidence`가 해당 청크 원문에 실제로 없으면 버렸다(268건 탈락, 그중 230건이 원문 대신 요약을 적은 경우). 스키마에 맞지 않는 사실은 억지로 넣지 않고 `review_queue`(303건)에 모았다(heebindev 처방).
- **청크 공동 언급은 커뮤니티 투영에 넣지 않는다.** `RAG`·`지식그래프` 같은 허브가 전부를 한 덩어리로 묶기 때문이다.

### 범위

- `members/<id>/`의 notes·labs md·readings·README, `main` `fd8b7f6` 기준. 미머지 PR(#6·#42·#45)은 넣지 않았다.
- 실습 데이터(`dataset/`·`note-templates/`)는 소재가 아니라서 뺐다.
- 주차는 **추정치**다. 제목의 "N주차"(18편) → 경로의 `weekN`(21편) → 날짜 구간(138편) 순으로 정한다. 노트를 몰아서 올린 멤버(sunghyun 1~4주차가 09-30 커밋)는 날짜만으로 틀리기 때문에 제목을 먼저 본다.

## 질의 — 세 방식

| | 근거 | 경로 |
|---|---|---|
| **v1** 청크 하이브리드 | `members/` 청크 1,928 | nori BM25 top-50 + kNN top-50 → RRF(k=60) → 8청크. 3주차와 같은 조건 |
| **v2** GraphRAG | v1 청크 + 구조·의미 그래프 | LLM이 경로 **분류만** 하고 질의는 코드가 정한다. **local**: 질문의 엔티티(사전 매칭) → Finding·Pitfall 확장 → 질문 유사도로 재정렬 15개 + 진입 청크 5개. **aggregate**: Text2Cypher(쓰기 구문·v3 라벨 거절, READ 세션, 1회 수정 재시도, 0행이면 local로 폴백). **global**: 커뮤니티 요약 Map(관련도 30 이상) → Reduce |
| **v3** LLM 위키 | `wiki/` 청크 409 | 위키 청크 RRF 6개 + 위키링크 1홉 이웃 요약 5개 |

## 결과

질문 12개(6주차 분류: 단일 사실 · 교차 멤버 · 멀티홉 · 집계 · 글로벌 · 모순 · 근거 없음). gold는 원문과 대조해 사람이 확정했다(`questions.yaml`의 `gold_source`). 판정은 `claude-sonnet-5-5`가 1회 했다.

| | 1회차 | 2회차 (Text2Cypher 처방 후) | 근거 없는 단정 (2회차) |
|---|---:|---:|---:|
| v1 청크 | 6.5 / 12 | 6.5 / 12 | 4 |
| v2 GraphRAG | **8.0** / 12 | 7.5 / 12 | 5 |
| v3 LLM 위키 | 7.5 / 12 | 7.5 / 12 | 2 |

✅ correct(1) · △ partial(0.5) · ❌ wrong(0) · ⚠ 근거 없는 단정. v2 칸의 `코드`는 실제로 탄 경로다.

| # | 유형 | v1 | v2 | v3 |
|---|---|---|---|---|
| Q01 | 단일 사실 | ✅ | ✅ `local` | ✅ |
| Q02 | 단일 사실 | △ | △ `local` | △ |
| Q03 | 교차 멤버 | ❌⚠ | △⚠ `aggregate→local` (1회차 ❌) | △ |
| Q04 | 교차 멤버 | △ | ❌⚠ `aggregate→local` (1회차 ❌) | ❌⚠ |
| Q05 | 멀티홉 | ✅ | ✅ `local` | ✅ |
| Q06 | 집계(구조) | ❌⚠ | ✅ `aggregate` | ❌⚠ |
| Q07 | 집계(구조) | ❌ | ✅ `aggregate` | ❌ |
| Q08 | 집계(함정) | ✅ | ❌⚠ `aggregate` (1회차 ✅) | ✅ |
| Q09 | 글로벌 | ❌⚠ | △ `global` | △ |
| Q10 | 글로벌 | △⚠ | △⚠ `global` | ✅ |
| Q11 | 모순 | ✅ | △⚠ `local` | ✅ |
| Q12 | 근거 없음 | ✅ | ✅ `aggregate→local` | ✅ |

### 확인한 것

- **집계는 그래프만 풀었다.** Q06·Q07(태그·문서 수)은 v2만 맞혔다. v1·v3는 검색된 몇 개 청크로 세다가 틀리거나 근거 없이 단정했다. 6주차 네 멤버의 결론("Top-k 검색으로는 집계 불가")이 같은 코퍼스에서도 그대로 나왔다.
- **교차 멤버 질문에서 v2가 가장 많이 찾지만, 추출 품질이 상한이다.** 예비 실행에서 local 경로로 들어간 Q03 취지의 질문에 v1은 1명, v3는 1명, v2는 4명(수치·조건까지, 원문 대조로 모두 일치)을 찾았다. 그러나 정답 5명을 다 찾지는 못했고, 같은 멤버가 k마다 이기고 지는 경우(lys0611 R@10, e0ng 36문항)는 Finding 하나에 한쪽 결과만 담겨 놓쳤다.
- **경로 선택이 결과를 가른다** (6주차 sunghyun과 같은 결론). Q03·Q04는 "누구이고 어떤 조건"이라는 표현 때문에 라우터가 aggregate로 보냈다. 1회차에서 Text2Cypher는 오류 없이 **0행**을 냈다. 원인은 둘이었다. 관계 속성 `outcome`을 노드(`f.outcome`)에서 찾았고, 사전에 없는 이름 `'벡터 검색'`을 썼다(정규 이름은 `임베딩`). 0행을 "없다"로 단정하지 않고 "근거 없음"으로 멈춘 것은 설계대로다.
- **처방이 다른 곳을 깨뜨렸다.** 프롬프트에 정규 이름 목록과 속성 위치를 넣고 0행이면 local로 폴백하게 하자 Q03은 ❌에서 △로 올랐다. 그런데 Q08은 ✅에서 ❌로 떨어졌다. 새 Cypher가 `kind='measured'` 필터를 빼먹어서, 커뮤니티 탐지를 *인용만 한* 멤버 셋을 "구현했다"고 지목했다. 총점은 8.0에서 7.5로 내려갔다. 질문 12개에 프롬프트를 맞추면 과적합이 되므로 여기서 멈추고 두 회차를 모두 기록한다.
- **추출이 승패 방향을 뒤집는다.** Q04의 오답을 추적하니, dldusgh318의 Finding은 claim이 "Vector Search가 BM25보다 더 적절했다"인데 `COMPARED_WITH.outcome`이 `lose`로 저장돼 있었다. 질문 하나의 정성 비교가 평균 R@5(BM25 우세)와 섞인 문제도 겹쳤다. `COMPARED_WITH` 107건의 방향 정확도는 아직 세지 않았다.
- **글로벌 서치가 처음으로 의미 있는 묶음을 냈다.** Leiden(modularity 0.642)이 사람이 정한 주차 커리큘럼과 거의 같은 묶음을 스스로 찾았다: 검색 융합(C0) · 그래프 추출·정규화(C1) · RAG 근거(C2) · RDF·OWL·SPARQL(C3) · 검색의 세 세대(C4) · GraphRAG(C5) · Text2Cypher(C6) · 평가(C7) · 청킹·리랭커(C8) · 쿼리 재작성(C9). 다만 Q09·Q10 답은 △였다. 요약이 기법별로 나뉘어 있어서 "평가 수치는 정답셋에 좌우된다", "멀티홉 ≠ 그래프" 같은 **기법을 가로지르는 교훈**은 어느 커뮤니티에도 온전히 담기지 않았다.
- **LLM 위키(v3)는 사람이 합성해 둔 질문에 강하다.** 흐름 요약(Q10)과 모순(Q11)은 v3만 정확히 맞혔다. 위키가 이미 그 질문의 답을 한 페이지로 써 두었기 때문이다. 반대로 집계(Q06·Q07)에서는 근거 없이 숫자를 단정했다. 위키는 미리 만든 글로벌 요약이지 쿼리할 수 있는 구조가 아니다.
- **근거 없음 질문(Q12)은 세 방식 모두 맞혔다.** 파인튜닝은 KURE 같은 외부 모델 설명에만 나오는데, 아무도 "KURE를 쓴 멤버가 파인튜닝했다"고 잘못 답하지 않았다.

## 함정 · 주의

- **수치는 통계가 아니다.** 질문 12개, 실행 1회, 채점 1회다. 6주차 dldusgh318이 보였듯 1회 실행은 판정을 뒤집을 수 있다.
- **v3는 공정한 경쟁자가 아니다.** 위키는 같은 노트를 읽고 LLM이 합성한 결과이고, 일부 gold의 출처(Q03·Q04·Q11)가 위키 자체다. v3가 잘했다는 결과는 "미리 합성해 둔 질문에는 답이 있다"는 뜻이지 검색 성능이 아니다.
- **Dataset 정규화가 처음에 틀렸다.** "lab 노트"·"개인 노트"처럼 데이터 종류를 특정할 수 없는 표현 42개가 전부 `옵시디언 노트`로 묶였다. 정규화 프롬프트에 "출처가 명시된 경우만"이라는 규칙을 넣어 null로 돌렸다. LLM 정규화는 `outputs/datasets.json`을 사람이 한 번 봐야 한다.
- **evidence 검증은 문자열 일치만 본다.** 근거 문구가 원문에 있어도 승패 방향(위 dldusgh318 사례)이나 단위(문항 하나 vs 평균)까지 맞는다는 보장은 없다. 5주차 kdyann의 경고와 같다.
- **민감 정보:** 노트에는 개인 문서 제목 같은 것이 섞여 있다. 추출 프롬프트가 데이터를 유형으로만 적게 하지만, Finding의 `evidence`·`value`에는 원문이 그대로 들어간다. `outputs/`와 Neo4j는 로컬에만 두고, 이 README에는 옮기지 않았다.

## 다음 할 일

- `COMPARED_WITH` 방향 검증: claim과 outcome의 일치를 별도 패스로 확인하거나, outcome을 추출하지 말고 `winner` 엔티티를 직접 적게 바꾼다.
- Text2Cypher 사후 검증: "구현·측정" 질문인데 `kind` 필터가 없으면 거절하는 규칙(질의 의도-쿼리 대조).
- 글로벌 요약에 기법을 가로지르는 교훈을 담을 상위 계층(커뮤니티의 커뮤니티) 요약.
- 실행 3회 + 다수결, 질문 수 확대.
