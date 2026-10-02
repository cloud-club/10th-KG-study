---
title: 그래프 적재 — Postgres 테이블, Turtle, Neo4j MERGE
type: concept
tags: [concept, runbook]
status: maintained
created: 2026-10-02
updated: 2026-10-02
members: [dldusgh318, e0ng, heebindev, kdyann, Yeongeunn]
weeks: [5]
---

> 5주차에 그래프를 실제로 만든 다섯 멤버는 전원 **Triplestore를 쓰지 않았다.** 중립적인 추출·검토 결과 하나에서 PostgreSQL(엔티티·엣지·근거 테이블), Turtle/JSON-LD(표준 산출물), Neo4j(탐색·시각화) 세 형태로 변환한다 — "각 저장소에서 따로 추출하면 같은 사실이 다른 형태로 저장될 수 있다"(dldusgh318, Yeongeunn). 멱등 재적재는 `MERGE`가 아니라 **안정 ID 규칙이 먼저**이고, 가변 길이 경로는 방향·술어·출처로 제한해야 의미가 있다. 저장·질의 비용 비교는 Cypher 17줄 vs SQL 33줄(X01) 같은 줄 수로만 남아 있다.

## 세 저장소의 역할

| 저장소 | 역할 | 누가 |
|---|---|---|
| **PostgreSQL** | 1차 저장. 엔티티·엣지·근거를 분리한 테이블. 벡터 검색(pgvector)과 한 DB → [[RDF와-프로퍼티-그래프]] | 전원 |
| **Turtle / JSON-LD** | RDF 표준 표현 산출물. "새 그래프를 만드는 게 아니라 같은 스키마를 표준으로 적는 것" | dldusgh318, e0ng, heebindev, kdyann, Yeongeunn |
| **Neo4j** | 프로퍼티 그래프 탐색·Cypher·브라우저 시각화. 공용 compose의 5.26+APOC를 처음 실제로 쓴 주차 → [[로컬-인프라]] | 전원 (dldusgh318은 자체 compose에 추가) |

- kungbi의 "PostgreSQL = canonical, 그래프·벡터 = projection" 모델이 실습 다섯 건으로 사실상 채택됐다. 단 정본의 위치가 다르다 — kdyann·Yeongeunn은 git 밖의 **검토 파일**(`graph-reviewed.json`, 검토본 jsonl)이 정본이고 PG도 파생물이다. 원문 → 검토 파일 → 모든 저장소의 3단 → [[데이터-수집과-출처-추적]].
- RDF 트리플 수와 사실 수는 다른 단위다. kdyann 사실 38 → 트리플 589, Yeongeunn 관계 20 → 트리플 373, dldusgh318 엣지 157 → 트리플 295. 타입·이름·출처·근거·문자 위치가 트리플로 함께 들어간다.

## PostgreSQL 테이블

| 멤버 | 테이블 | 특징 |
|---|---|---|
| dldusgh318 | `entities(entity_id, type, label, props JSONB)`, `edges(subject, predicate, object, props)` + 중복 방지 인덱스, `ON CONFLICT DO NOTHING` | 엣지 `props`에 `chunk_id`·`evidence`·`confidence`·`extraction_run`. 적재 75·157 |
| e0ng (PR #36 미머지) | `kg_entities(id, types[], name)`, `kg_edges(subject_id, predicate, object_id \| object_literal)`, `kg_evidence(edge_id, source)` | `types` 배열(한 문서가 활동 전체를 대표하면 `{Activity, Document}`), 리터럴과 엔티티 참조를 컬럼으로 분기. 246·304·237 |
| heebindev | `kg_entities`, `kg_relations`, `kg_evidence` | 38·8·8. "트리플 저장은 되지만 여러 관계를 반복해 따라가는 질의는 조인이 계속 는다" |
| kdyann | 문서·엔티티·엣지·근거 | 39·65·38·38. 근거는 `rdf:Statement` reification으로 `sourcePost`·`quote`·`start`·`end` |
| Yeongeunn | `yeongeunn_kg.entities(id, class, label)`, `assertions(…, qualifiers, review_status)`, `evidence(assertion_id, chunk_id, quote, source_version)` | 15·20·29. 관계와 근거 분리, `review_status`·`source_version` 컬럼 → [[Wikidata와-DBpedia]] |

- JSONL 통과 수 > DB 수인 세 가지 이유 (dldusgh318): 정규화 병합, 같은 청크 중복 제거, 관계가 부족한 중간 노드 제외. 통계를 읽을 때 "DB 술어 수 < JSONL 통과 수"는 버그가 아니다.
- 멤버 간 노드 격리: 공용 Neo4j에서 전용 라벨 + `run` 속성(`KGStudyYeongeunn`, kdyann `W5_FACT`), PG는 전용 스키마(`yeongeunn_kg`) 또는 접두사.

## Neo4j 적재 — MERGE와 멱등성

- `CREATE`는 실행마다 새로 만들어 중복이 생기고 `MERGE`는 패턴이 있으면 찾고 없으면 만든다. **그러나 `MERGE`만으로 중복이 해결되지 않는다** — "같은 실체에 같은 ID" 규칙이 먼저 있어야 한다(heebindev, kdyann). `MERGE`는 별칭 동일성을 판단하지 않는다 → [[엔티티-신원해소]].
- 노드는 `id`로 `MERGE`하고 `label`·`purpose`·`status`는 `SET`. **관계는 `(subject, predicate, object, chunk_id)`의 SHA-256 `edge_key`로 `MERGE`** — 같은 두 노드 사이라도 근거 청크가 다르면 관계를 따로 보존(멀티엣지). `--verify-idempotency`로 같은 배치를 두 번 실행해 개수 불변 확인 (dldusgh318: 2회 재적재 75·96 불변).
- 멱등 실측: e0ng 246 → 재실행 246, Yeongeunn 동일 스냅샷 2회 적재 건수 유지, kdyann `MERGE`+제약. heebindev는 "중복 생성을 **줄일 수 있다**"고만 썼다.
- **RDF 리터럴 ↔ 프로퍼티 그래프 속성의 변환 규칙을 코드로 명시해야 한다.** RDF에서는 `:activityScope "개인"`도 트리플 한 줄이지만 Neo4j에서는 노드 속성이다 (e0ng `literal_by_subject`). 리터럴 술어는 속성으로, 엔티티 간 술어는 관계로. 관계 타입은 `occursInPeriod → OCCURS_IN_PERIOD`처럼 UPPER_SNAKE_CASE로 명시 매핑 (e0ng, Yeongeunn `callsService → CALLS_SERVICE`).
- Turtle·JSON-LD를 다시 파싱한 그래프가 원래 RDF 그래프와 동형(isomorphic)인지 검증 (Yeongeunn). PG·Turtle·Neo4j 세 곳의 건수 일치 확인 (heebindev 38·8).

## 질의 — Cypher vs SQL

- 같은 질문의 줄 수 (dldusgh318, 주석·빈 줄 제외, Cypher : PostgreSQL): 프로젝트→기술 10:17 / X01 브릿지 17:33 / X03 상태 비교 16:35 / `REPLACES` 연쇄 7:26 / 공유 기술 경로 11:41 / X01+근거 35:51. 가변 길이는 Cypher `[:REPLACES*1..3]` vs **순환 방지 배열을 둔 재귀 CTE**. 프로젝트 간 한 단계가 관계 4개이므로 Cypher `*4..8` = PG 2단계 재귀.
- Yeongeunn은 카드 관련 3-hop을 Postgres JOIN으로도 실행해 **Cypher와 같은 행**이 나오는지 교차 검증했다.
- **가변 길이 경로 `*1..3`은 길이만 맞는 경로를 다 준다.** 관계 방향·술어·출처 집합·시간 조건·중복 경로를 함께 제한해야 한다 (kdyann). "경로가 길어질수록 결과가 매우 많아지므로 최대 길이를 정한다" (heebindev). kdyann의 자기검증: "야구" 6개 경로는 내 글 4건의 조합 `4×3÷2`이지 추천 결과가 아니다.
- **0건 진단 순서** (dldusgh318): 관계 타입별 건수 → 중간 노드의 방향 → 실제 적재된 속성 값 → `entity_id` 중복 → 브릿지가 다른 프로젝트까지 연결되는지. "작업 큐"로 찾으면 실제 값이 "큐 기반 비동기 처리"라 0건 — 문자열 속성은 자유 텍스트다.
- `COUNT(*)`가 아니라 `COUNT(DISTINCT project)` — 과잉 생성된 중간 노드가 답을 부풀린다 → [[엔티티-신원해소]].
- "해당 서비스를 호출한다"는 정보만으로 그 서비스의 **모든** API를 호출했다고 해석하면 안 된다 (Yeongeunn).

## 함정 · 주의

- 공용 Neo4j 비밀번호·자체 compose 자격증명을 문서에 평문으로 적은 멤버가 있다. 위키에는 옮기지 않는다. heebindev처럼 `.env`의 `NEO4J_PASSWORD`로 참조하는 표기가 안전하다.
- dldusgh318의 자체 compose에 Neo4j를 추가하면 공용 Neo4j(7687/7474)와 포트가 겹쳐 동시 실행이 안 될 수 있다 → [[로컬-인프라]].
- `--run-name`을 재사용하면 입력·후보를 덮어쓴다 (Yeongeunn). 재개 로직은 성공한 `chunk_id`를 건너뛰고 실패 행만 재시도 (dldusgh318).
- 시각화가 보기 좋다고 추출한 사실이 정확하다는 뜻은 아니다 (heebindev). 발표 화면에서 전체 그래프·노드 확장 기능은 쓰지 않는다 (dldusgh318).

## 열린 질문

- SPARQL endpoint(Jena·Fuseki·GraphDB)를 띄워 Turtle 산출물을 실제로 질의한 멤버가 없다. Turtle은 아직 "내보내기"일 뿐이다 → [[SPARQL]].
- Postgres 재귀 CTE가 깊어질 때의 실제 성능은 아무도 재지 않았다. "3홉부터 느리다" 같은 기준은 없다 → [[RDF와-프로퍼티-그래프]].

## 관련

- [[LLM-트리플-추출]] · [[엔티티-신원해소]] · [[폐쇄-스키마-설계]] · [[RDF와-트리플]] · [[RDF와-프로퍼티-그래프]] · [[로컬-인프라]] · [[PostgreSQL과-pgvector-함정]] · [[데이터-수집과-출처-추적]] · [[RAG-vs-그래프-질의]]

## 출처

- dldusgh318 · 인수인계 (§1-3 적재, §5 Neo4j), 질의 비교 — [members/dldusgh318/labs/01-three-generations/WEEK5_HANDOFF.md](../../members/dldusgh318/labs/01-three-generations/WEEK5_HANDOFF.md), [WEEK5_queries.md](../../members/dldusgh318/labs/01-three-generations/WEEK5_queries.md); 실행 절차 (§4 Neo4j 멱등, §통계 해석) — [README.md](../../members/dldusgh318/labs/01-three-generations/README.md); W5-3 RDF 형식 — [notes/week5/03-rdf-format.md](../../members/dldusgh318/notes/week5/03-rdf-format.md)
- e0ng · 지식그래프 적재와 Cypher 다중 홉 — [members/e0ng/labs/05-graph-store/README.md](../../members/e0ng/labs/05-graph-store/README.md) (PR #36 미머지)
- heebindev · 문서에서 지식 그래프 만들기 (§3–6) — [members/heebindev/labs/03-triple-extraction-kg/README.md](../../members/heebindev/labs/03-triple-extraction-kg/README.md); 데이터 파이프라인 (§6·§8·§9) — [notes/05-rdf-owl-data-pipeline.md](../../members/heebindev/notes/05-rdf-owl-data-pipeline.md)
- kdyann · 내 인스타그램 캡션에서 지식 그래프 만들기 — [members/kdyann/labs/05-content-graph/README.md](../../members/kdyann/labs/05-content-graph/README.md); RDF·OWL 데이터 파이프라인 — [notes/05-rdf-owl-data-pipeline.md](../../members/kdyann/notes/05-rdf-owl-data-pipeline.md)
- Yeongeunn · 트리플 추출·적재 실습 — [members/Yeongeunn/labs/05-triple-extraction/README.md](../../members/Yeongeunn/labs/05-triple-extraction/README.md); 미니 온톨로지와 트리플 추출 (§9–11) — [notes/10-week5-triple-pipeline.md](../../members/Yeongeunn/notes/10-week5-triple-pipeline.md)
- 외부: Neo4j Cypher MERGE https://neo4j.com/docs/cypher-manual/current/clauses/merge/ · Variable-length paths https://neo4j.com/docs/cypher-manual/current/patterns/variable-length-paths/ · W3C Turtle https://www.w3.org/TR/turtle/ · JSON-LD 1.1 https://www.w3.org/TR/json-ld11/
