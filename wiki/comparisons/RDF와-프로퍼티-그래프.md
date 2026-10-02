---
title: RDF 트리플스토어와 프로퍼티 그래프 — 둘 다 그래프인데 뭐가 다른가
type: comparison
tags: [comparison]
status: maintained
created: 2026-10-02
updated: 2026-10-02
members: [dldusgh318, do-dop, lys0611, e0ng, heebindev, sunghyun]
weeks: [1, 4]
---

> "KG를 만든다고 반드시 RDF를 써야 할까?" 아니다. RDF는 시스템 간 데이터 표현·연결(표준·식별·상호운용성)에서, 프로퍼티 그래프는 애플리케이션의 그래프 저장·조회(탐색·개발 편의)에서 출발했다. "RDF를 그래프 DB의 옛날 버전처럼 보면 안 된다. 풀려던 문제가 달랐다" (dldusgh318). 4주차에 여섯 멤버가 비교표를 만들었고, do-dop이 머리말에 못 박은 대로 **배타적 기능 차이가 아니라 각 모델이 강조해 온 설계 관점**이다.

## 비교표 (dldusgh318 9축 + do-dop·lys0611·e0ng·heebindev 합성)

| 축 | RDF 트리플스토어 | 프로퍼티 그래프 |
|---|---|---|
| 출발점 | 시스템 간 데이터 표현·연결 | 애플리케이션의 그래프 저장·조회 |
| 기본 단위 | 트리플 S–P–O. **모든 사실이 트리플** — `ex:p age 25`도 트리플 (e0ng) | 노드·관계에 키–값 속성. 라벨은 노드에 여러 개, 관계 타입은 하나 (do-dop) |
| 관계의 부가 정보 | 세 칸이 꽉 차 중간 노드·statement·reification이 필요 → [[RDF와-트리플]] | **엣지 속성**으로 바로. `서울 ──[이동: 거리, 비용]──> 부산`. 단 관계를 독립 개체로 다뤄야 하면 PG에서도 노드로 올린다 (dldusgh318) |
| 식별 | 외부에서도 식별 가능한 IRI, 다른 데이터셋 연결 전제, 전역 체계 관리 | 그래프 내부 식별로 충분, 한 앱의 DB 중심, 내부 ID·앱 키 |
| 의미 정의 | RDFS·OWL 어휘로 클래스·속성·추론 규칙 → [[온톨로지와-추론]] | 라벨·관계 이름이 곧 의미. 분류체계·공리는 애플리케이션 몫 |
| 질의어 | SPARQL — 트리플 패턴, `?변수` 공유로 조인 → [[SPARQL]] | Cypher — `(node)-[:EDGE]->(node)` 패턴. **GQL**은 2024년 ISO 표준이며 Cypher와 같은 언어가 아니다 (do-dop, dldusgh318) |
| 추론 생태계 | 형식 의미론, 추론기, 열린 세계 가정 | 없음에 가깝다. 쿼리·앱 로직으로 |
| 저장·탐색 | 트리플 인덱스 | Neo4j의 index-free adjacency — 시작 노드를 찾은 뒤 전체 엣지 테이블을 다시 뒤지지 않고 이웃으로 이동 (dldusgh318) |
| 대표 시스템·활용 | GraphDB, Apache Jena, Stardog, Neptune(RDF) · Wikidata, Linked Data | Neo4j · 소셜 그래프, 추천, Fraud Detection |
| 사용 목적 (lys0611이 첫 축으로) | 여러 데이터셋·공개 데이터 연결 | 관계 속성·경로 탐색 중심 |

## 갈리는 지점

- **같은 단어, 다른 뜻**: PG의 property = 키–값 속성, RDF의 property = 트리플의 술어 (do-dop). 경로 길이는 노드 수가 아니라 **관계 수**로 센다 (do-dop).
- **"Neo4j는 스키마가 선택 사항"의 뜻**: 인덱스·제약조건 없이 넣을 수 있다는 뜻이지 라벨·관계·속성의 의미를 설계할 필요가 없다는 뜻이 아니다. 라벨 여러 개가 클래스 계층이나 추론 규칙을 자동으로 만들어주지도 않는다 (do-dop). lys0611 표는 "선택적"으로만 적어 반대로 읽힐 수 있다.
- **모델 ≠ 세계 가정**: "RDF = 열린 세계, PG = 닫힌 세계"로 외우지 않는다. OWA는 RDF의 형식 의미론·추론 생태계에서 중요한 관점이고 PG도 설계에 따라 불완전한 데이터를 다룬다 (dldusgh318) → [[온톨로지와-추론]].
- **성능 신화**: "Postgres는 3홉부터 느리다" 같은 고정 기준은 없다. 그래프 크기, 연결 밀도, 인덱스, 쿼리 형태에 달렸다 (dldusgh318). "조회 성능은 모델 이름만으로 결정되지 않는다" (do-dop). Postgres에서 홉마다 `edges` JOIN, 깊이가 가변이면 Recursive CTE → [[PostgreSQL과-pgvector-함정]].
- **변환은 파일이 아니라 의미의 문제** (do-dop): RDF ↔ PG 변환 시 정할 것 넷 — IRI를 어떤 키로 보존, 클래스·술어 → 라벨·관계 타입·속성, 관계의 근거·날짜·반복 사건, 자료형·언어 태그·다중 값. 변환 전후 같은 질문의 답이 유지되는지 확인한다.
- **두 모델의 수렴**: RDF 쪽은 statement에 정보를 붙이기 쉽게, PG 쪽은 GQL로 표준화. "대립하는 기술이 아니라 서로 다른 문제에서 출발해 발전해온 두 모델" (dldusgh318). "RDF·온톨로지로 의미를 설계하고 저장·질의는 PG로"도 가능하다 (do-dop).

> ⚠️ Contradiction: **기존 표의 강도.** [[지식그래프와-온톨로지]]에 있던 sunghyun의 4행 표는 "Neo4j: 추론은 쿼리·앱 로직 / RDF: 의미 규칙을 데이터 모델에"로 단정했고 heebindev·lys0611 표도 칸마다 단정형이다. do-dop은 "강조해 온 설계 관점"으로 명시적으로 완화하고 PG의 의미 모델링·RDF의 애플리케이션 사용을 모두 인정한다. 이 페이지는 do-dop의 완화를 머리말로 올리고 표는 합성했다.

## 관계형 모델도 관계를 표현한다 (do-dop)

- "RDBMS는 관계를 표현하지 못한다"는 틀린 설명이다. 자기 참조 외래키(`parent_id REFERENCES person(id)`)로 조직도·댓글 계층·카테고리를, 다대다·관계 속성은 관계 테이블로 표현한다. 정확한 설명은 **"관계 종류와 탐색 경로가 늘수록 JOIN 구조와 스키마 변경이 복잡해진다"**.
- 깊이를 모르는 계층은 `WITH RECURSIVE`. **데이터에 순환이 있으면 무한 반복** — 방문 노드 기록이나 깊이 제한이 필요하다.
- 역할 3분: RDBMS(표·정형 관리) / KG(관계 탐색) / 온톨로지(의미 정의, "저장소가 아니다"). lys0611의 RAG vs KG 4행표는 KG의 대표 문제를 "그래프 구축·엔티티 식별이 필요"로 **비용 쪽에** 둔다.

## 어느 쪽부터 — 스터디에서 갈린 판단

> ⚠️ Contradiction: 같은 "개인 문서(Notion) 데이터"에서 **sunghyun**(1주차)은 "Neo4j부터 시작하는 게 이해하기 쉽고, 의미 규칙·추론까지 가고 싶어지면 RDF로 다시 표현"이라 했고, **dldusgh318**(4주차, 2026-09-23 시점)은 PostgreSQL을 유지했다. 이유 셋: 이미 pgvector로 벡터 검색을 쓰고 있어 **한 저장소에서 벡터 검색과 그래프 탐색을 같이 실험**하기 쉽다, 목표가 그래프 DB 성능 검증이 아니라 관계 구조화가 Retrieval 실패를 줄이는지 확인하는 것이다, 데이터가 개인 문서 규모다. "Neo4j가 필요 없어서가 아니라 현재 실험의 규모와 목적에서는 Postgres의 단순함이 더 크다고 판단한 것." dldusgh318은 **5주차에 Neo4j 적재를 추가**해 이 판단을 스스로 확장했다 → [[지식그래프와-온톨로지]].

- dldusgh318의 4주차 저장 구조: Node = `entities(entity_id, type, label, props JSONB)`, Edge = `edges(subject, predicate, object, chunk_id, evidence, confidence)`, 식별자 = 내부 문자열 ID, 관계 = 미리 정한 소수 Predicate, 추론 엔진 = 없음. **"RDF의 트리플이라는 사고방식은 참고하지만 실제 구현은 PostgreSQL 위의 작은 프로퍼티 그래프."** → [[실습-비교표]].
- do-dop의 모델 선택 5문항: 관계에 속성(날짜·근거)이 필요한가 / 여러 조직·데이터셋을 연결하는가 / 추론이 필요한가 / 어떤 질문을 반복해서 묻는가 / 측정 조건은 무엇인가. do-dop의 W4 화이트보드 절차: 대상·관계 구분 → 연결 그림 → **각 관계에 근거 문서가 있는지 표시하고 없는 관계를 추측으로 채우지 않는다** → PG의 노드/관계/속성 결정 → RDF의 IRI/리터럴/사건 자원 비교.

## 열린 질문

- 같은 데이터를 Neo4j와 RDF 양쪽으로 표현해 질의 표현과 결과를 비교한 멤버는 아직 없다(sunghyun 1주차 제안). dldusgh318 5주차의 Postgres → RDF(Turtle) → Neo4j 경로가 가장 가깝다.
- DDIA 2장(관계형·문서·그래프 모델)은 dldusgh318이 예고만 하고 다루지 않았고, lys0611의 [[저장-구조-LSM과-B-tree]]는 3장이다. 2장 자리는 공백.

## 관련

- [[지식그래프와-온톨로지]] · [[RDF와-트리플]] · [[온톨로지와-추론]] · [[SPARQL]] · [[로컬-인프라]] · [[PostgreSQL과-pgvector-함정]] · [[실습-비교표]] · [[저장-구조-LSM과-B-tree]]

## 출처

- dldusgh318 · RDF 트리플 스토어 vs Property 그래프 (2026-09-23) — [members/dldusgh318/notes/week4/05-rdfTriple-VS-property.md](../../members/dldusgh318/notes/week4/05-rdfTriple-VS-property.md); 4주차 요약 §5 — [00-summary.md](../../members/dldusgh318/notes/week4/00-summary.md)
- do-dop · 프로퍼티 그래프와 RDF: 두 그래프 모델의 철학 차이 — [members/do-dop/notes/04-relational-and-graph-data-models.md](../../members/do-dop/notes/04-relational-and-graph-data-models.md); 시맨틱 웹에서 지식그래프까지 (§10) — [04-semantic-web-to-knowledge-graph.md](../../members/do-dop/notes/04-semantic-web-to-knowledge-graph.md)
- lys0611 · 지식 그래프의 배경 (§5) — [members/lys0611/notes/06-knowledge-graph-foundations.md](../../members/lys0611/notes/06-knowledge-graph-foundations.md)
- e0ng · RDF·OWL·SPARQL과 그래프 모델 (§Property Graph vs RDF) — [members/e0ng/notes/04-2-knowledge-graph-basics.md](../../members/e0ng/notes/04-2-knowledge-graph-basics.md)
- heebindev · 지식 그래프의 배경과 기업 사례 (§7) — [members/heebindev/notes/04-knowledge-graph-background.md](../../members/heebindev/notes/04-knowledge-graph-background.md)
- sunghyun · RAG, 지식 그래프와 온톨로지 기초 — [members/sunghyun/note/01-knowledge-graph-and-ontology.md](../../members/sunghyun/note/01-knowledge-graph-and-ontology.md)
- 외부 (do-dop readings): Neo4j, RDF vs. property graphs (2024) https://neo4j.com/blog/knowledge-graph/rdf-vs-property-graphs-knowledge-graphs/ · Neo4j Graph database concepts https://neo4j.com/docs/getting-started/appendix/graphdb-concepts/ · Cypher Manual https://neo4j.com/docs/cypher-manual/current/ · PostgreSQL Recursive Queries https://www.postgresql.org/docs/current/queries-with.html#QUERIES-WITH-RECURSIVE · DDIA Ch.2 https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/ch02.html
