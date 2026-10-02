---
title: 지식그래프 적재와 Cypher 다중 홉
date: 2026-09-30
tags: [knowledge-graph, neo4j, cypher, postgres, rdf, triple-extraction]
status: in-progress
---

# 05. 지식그래프 적재와 Cypher 다중 홉

> 관련 노트: `../../notes/05-1-closed-schema.md`, `../../notes/05-2-llm-information-extraction.md`, `../../notes/05-3-rdf-serialization.md`

## 목표

3~4주차(`03-04-personal-data-agent`)에서 이미 적재한 노션 청크로 지식그래프를 만들어,
- 트리플을 추출하고 (Postgres 엔티티/엣지/근거 + Turtle) 두 형태로 저장하고
- Neo4j에 MERGE로 적재하고
- W3 RAG가 답 못 했던 다중 홉 질문을 Cypher로 다시 풀어보고
- 브라우저로 직접 그래프를 본다

닫힌 스키마(클래스 `Period·Activity·Document·Organization·Topic`, 술어 8종)는
`../03-04-personal-data-agent/src/kg/extract_triples.py`에서 CQ→Bottom-up→Middle-out
과정을 거쳐 설계한 걸 그대로 가져왔다. 이 랩은 그 스키마로 실제 저장·질의까지 간다.

## 환경

- 언어 / 런타임: Python 3.13
- 주요 라이브러리: `psycopg`, `neo4j`, `rdflib`, `python-dotenv`
- 인프라: 레포 루트 공용 `docker-compose.yml`(Postgres 17+pgvector, Neo4j 5.26+APOC) — 이 랩 전용 컨테이너는 없다
- 임베딩/LLM: OpenAI `gpt-4.1-mini` (Topic 추출에만 사용)
- 외부 서비스 / 키: 레포 루트 `.env`의 `OPENAI_API_KEY`

## 1. 트리플 추출 쇼케이스

`src/extract_triples.py`가 청크를 Period/Activity/Document/Organization으로 그룹핑하고
(폴더 경로 + `Status:`/`type:` 필드로 결정적 추출), Topic 하나만 LLM에게 트리플 JSON으로
뽑게 한다.

```bash
cd members/e0ng/labs/05-graph-store
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 레포 루트 .env에 OPENAI_API_KEY 필요
python src/extract_triples.py --dry-run   # 구조만 미리보기 (LLM 호출 없음)
python src/extract_triples.py             # 실제 추출 + data/graph.ttl 저장
```

실행하면 활동마다 이렇게 찍힌다.
```
  추출된 트리플: {'subject': '졸전', 'predicate': 'schema:about', 'object': '가구 GLB/USDZ 변환 파이프라인'}
[2026 1학기] 졸전 -> 가구 GLB/USDZ 변환 파이프라인  (36개 Document에 복사)
```

## 2. 저장 — Postgres(엔티티/엣지/근거) + Turtle

```bash
python src/store_postgres.py
```

`src/schema.sql`에 정의한 3개 테이블에 들어간다.
- `kg_entities(id, types[], name)` — `types`가 배열인 이유: "git 정리"처럼 문서 한 장이
  활동 전체를 대표하면 `{Activity, Document}` 이중 타입이 된다
- `kg_edges(subject_id, predicate, object_id | object_literal)` — 대상이 엔티티면
  `object_id`, 리터럴(상태·주제 등)이면 `object_literal`
- `kg_evidence(edge_id, source)` — 엣지 하나가 어느 노션 페이지에서 나왔는지

Turtle은 `data/graph.ttl`에 같이 저장된다(1번 실행 결과).

## 3. Neo4j 적재 — MERGE

```bash
python src/load_neo4j.py
```

`id`로 `MERGE`하므로 여러 번 돌려도 노드·관계가 늘지 않는다(직접 확인: 246개 → 재실행 후 246개
그대로). 리터럴 술어(`status`, `activityKind`, `activityScope`, `about`)는 노드 속성으로,
엔티티 간 관계(`occursInPeriod`, `hasDocument`, `relatedToOrganization`)는 관계로 적재한다.
관계 타입은 `occursInPeriod` → `OCCURS_IN_PERIOD`처럼 Cypher 관례(UPPER_SNAKE_CASE)로 변환한다.

## 4. Cypher 질의 — `queries/explore.cypher`

```bash
docker compose exec neo4j cypher-shell -u neo4j -p kgstudy2026
```

**1-hop**
```cypher
MATCH (a:Activity {name: "졸전"})-[:HAS_DOCUMENT]->(d:Document)
RETURN d.name AS document LIMIT 5;
```

**가변 길이 경로(`1..3`)**
```cypher
MATCH (org:Organization {name: "KB 국민은행"})<-[*1..3]-(n)
RETURN DISTINCT labels(n) AS types, n.name AS name;
```

**아하 모먼트** — W3에서 RAG가 "역량검사" 청크와 "KB 국민은행" 청크를 따로 검색해 하나로
못 이었던 질문을, 그래프에서는 경로 하나로 바로 답한다.
```cypher
MATCH (org:Organization {name: "KB 국민은행"})<-[:RELATED_TO_ORGANIZATION]-(a:Activity)-[:HAS_DOCUMENT]->(d:Document)
RETURN a.name AS activity, d.name AS document, a.status AS status;
```
실제 결과:
```
"KB 국민은행 지원 준비", "KB 국민은행"
"KB 국민은행 지원 준비", "자기소개서"
"KB 국민은행 지원 준비", "역량검사"
```
검색은 "비슷한 청크를 찾는" 확률적 과정이라 연결을 놓칠 수 있지만, 그래프는 `RELATED_TO_ORGANIZATION`
→ `HAS_DOCUMENT` 두 관계를 정해진 순서로 순회할 뿐이라 놓칠 수가 없다 — 이게 W3에서 못 답했던
이유(끊긴 홉)와 지금 안 끊기는 이유(관계가 그래프에 미리 저장돼 있음)의 차이다.

## 5. 브라우저로 시각화

Neo4j는 자체 브라우저 UI가 있어 따로 만들 게 없다.

```bash
open http://localhost:7474
# 로그인: neo4j / kgstudy2026
```

접속 후 위 Cypher를 그대로 붙여넣으면 노드-관계 그래프로 바로 그려진다. 전체 그래프를 보려면:
```cypher
MATCH (n) RETURN n LIMIT 100;
```

## 구조

```
05-graph-store/
├── requirements.txt
├── .gitignore                # data/*.ttl(개인 데이터) 제외
├── data/                     # graph.ttl 생성 위치, Git 제외
├── src/
│   ├── common.py             # 레포 루트 .env 로드, 3~4주차 청크 재사용, OpenAI 호출
│   ├── extract_triples.py    # 1) 추출 + 그래프 자료구조 조립 + Turtle 저장
│   ├── schema.sql             # Postgres 3테이블 스키마
│   ├── store_postgres.py     # 2) Postgres 적재
│   └── load_neo4j.py         # 3) Neo4j MERGE 적재
├── queries/
│   └── explore.cypher        # 4) 1-hop / 가변 길이 / 다중 홉 질의
└── tests/
    └── test_extract_triples.py
```

## 결과

- 엔티티 246개, 엣지 304개, 근거(evidence) 237개 — Postgres 3테이블에 실제 저장 확인
- Organization 5개(KB 국민은행·Naver·리코·페이타랩·필드유) 정확히 분리됨
- `git 정리`처럼 한 활동이 여러 기간(1학기·Winter)에 걸쳐도 같은 엔티티로 합쳐지고, 두 기간 모두
  `OCCURS_IN_PERIOD`로 연결되는 것 확인
- Neo4j MERGE 재실행해도 노드 수 246개 그대로(중복 없음) 확인
- 자동 테스트 12개 통과(중복 타입 버그의 회귀 테스트 포함)

## 배운 점

- **엔티티 ID가 활동 이름에서만 나오면, 다른 그룹(기간이 다른 같은 이름)이 같은 ID로 합쳐질 수
  있다.** 처음엔 이걸 놓쳐서 `git 정리`가 `:Activity, :Document, :Document`처럼 타입이 중복
  저장됐다. `add_entity()`를 항상 거치게(직접 리스트를 건드리지 않게) 고쳐서 해결했고, 테스트로
  회귀를 막았다.
- **RDF 트리플과 Property Graph(Neo4j)는 리터럴 값을 다루는 방식이 다르다.** RDF에서는
  `activity_git_정리 :activityScope "개인"`처럼 리터럴도 트리플 한 줄이지만, Neo4j에서는
  노드의 속성(property)으로 붙인다. 같은 그래프를 두 저장소에 넣으려면 이 변환 규칙을 코드로
  명시해야 했다(`load_neo4j.py`의 `literal_by_subject` 부분).
- 검색(RAG)과 그래프 순회의 차이가 실습으로 체감됐다 — 같은 "KB 역량검사" 다중 홉 질문을
  W3에서는 벡터 유사도로 청크 두 개를 각각 찾아야 했지만, 여기서는 미리 저장된 관계 두 개를
  따라가기만 하면 됐다.

## 다음 단계

- [ ] `queries/explore.cypher`의 나머지 질의(4, 5)도 브라우저에서 직접 그려보고 스크린샷 추가
- [ ] Topic(LLM 추출) 포함해서 `extract_triples.py` 전체 실행 후 결과 캡처
- [ ] `data/evaluation/multihop_w4_bridge.jsonl`(3~4주차 다중 홉 실패 목록)의 나머지 사례도
      이 그래프로 재현되는지 확인
