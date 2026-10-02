---
title: RDF와 트리플 — 세 칸으로 사실을 쓰고, 세 칸이 모자랄 때
type: concept
tags: [concept, glossary]
status: maintained
created: 2026-10-02
updated: 2026-10-02
members: [dldusgh318, do-dop, e0ng, heebindev, lys0611, kdyann, Yeongeunn, yujeong430, kungbi]
weeks: [4, 5]
---

> 모든 사실을 주어–술어–목적어 세 칸으로 통일하는 데이터 모델. 개체는 IRI, 값은 Literal, 이름 없는 구조 노드는 Blank Node다. 핵심은 "그래프 모양"이 아니라 **서로 다른 데이터가 같은 대상을 참조할 수 있게 하는 것**(do-dop)이고, 실습에서 먼저 부딪히는 문제는 "세 칸에 목적·상태·기간이 안 들어간다"는 n항 관계다(dldusgh318). 저장·질의는 [[SPARQL]], 의미·추론은 [[온톨로지와-추론]], 프로퍼티 그래프와의 비교는 [[RDF와-프로퍼티-그래프]].

## 정의

- **RDF** = Resource(설명 대상) + Description(속성·관계) + Framework(S–P–O 공통 구조) (do-dop, e0ng). RDB가 스키마를 먼저 정하고 맞춰 넣는다면 RDF는 새 사실이 생기면 트리플을 추가한다 — 단일 구조, 유연한 확장, 데이터 연결 (dldusgh318). RDF 자체는 저장소가 아니다. 저장은 Triplestore(GraphDB, Apache Jena, Stardog, Neptune)가 한다.
- 관점 전환: `질문 → 관련 문서 검색`에서 `개체 → 관계 → 개체`로 (dldusgh318). "RDF의 초점은 한 개체의 정보를 한 행에 모으는 것이 아니라 여러 개체 사이의 사실과 관계를 공통 방식으로 표현·연결하는 것."

| 자리 | 허용 값 | 비고 |
|---|---|---|
| Subject | IRI, Blank Node | |
| Predicate | IRI | |
| Object | IRI, Blank Node, **Literal** | **Literal은 목적어 자리에만** 온다. 문자열을 다시 주어로 삼아 관계를 이어 붙일 수 없으므로 계속 설명할 대상은 IRI를 가진 Resource여야 한다 (dldusgh318) |

- **IRI**: RDF 1.1부터 URI보다 넓은 문자 집합의 식별자 (lys0611, do-dop). 표시 이름(어린 왕자 / The Little Prince / Le Petit Prince)과 달리 같은 대상을 계속 가리킨다. 웹페이지가 실재할 필요는 없다. **IRI는 식별자를 주는 방법일 뿐 동일성 판단을 대신하지 않는다** — 다른 데이터셋이 같은 사람을 다른 IRI로 부르면 문제는 Entity Resolution으로 돌아온다 (dldusgh318, do-dop).
- **Literal**: 타입과 언어 태그가 붙는다. `"25"^^xsd:integer`, `"2026-03-01"^^xsd:date`, `"민지"@ko`, `"Minji"@en` (e0ng). `xsd:`는 XML Schema 데이터타입 접두어. lys0611은 "Literal은 프로퍼티 그래프의 속성값에 가깝다"고 두 모델을 잇는다.
- **Blank Node**: 전역 식별자를 줄 필요가 없는 임시 자원. dldusgh318은 "이름도 없는 노드를 왜 만들지?"가 n항 관계의 중간 노드를 만들어 보고서야 이해됐다고 적었다.
- **네임스페이스와 접두어**: `@prefix ex: <https://example.com/> .`에서 `@prefix`는 선언 키워드, `ex:`는 접두어, URL이 네임스페이스 (e0ng). `http://www.wikidata.org/entity/Q8684` → `wd:Q8684` (lys0611). schema.org는 공통 의미 어휘(Person·Organization·Article·Event, name·birthDate·author·affiliation).
- **직렬화**: Turtle, N-Triples, JSON-LD, RDF/XML은 같은 RDF 그래프의 **문법**일 뿐이다 (do-dop, lys0611). Turtle은 사람이 읽기 편하고 JSON-LD는 웹에 편하다. Turtle 최소 문법 3개 — `;`(같은 주어 생략), `,`(같은 주어+술어 생략), `a`(= `rdf:type`) (dldusgh318).

## 세 칸이 모자랄 때 — n항 관계

- dldusgh318이 자기 포트폴리오 문서를 모델링하다 부딪힌 문제: "프로젝트 A가 Redis를 **작업 큐** 용도로 **실제 구현**했다"와 "프로젝트 B에서 Redis를 캐시 용도로 **제안만** 했다"를 `프로젝트 → USES → Redis` 2항 관계로는 구분할 수 없다. 알고 싶은 것이 네 가지(어느 프로젝트 / 어떤 기술 / 왜 / 어떤 상태)인데 칸은 셋이다.
- 해법은 **관계 자체를 노드로** 올리는 것. 중간 노드 `TechnologyUse`에 `PART_OF` / `USES_TECHNOLOGY` / `HAS_PURPOSE` / `HAS_STATUS` 네 관계를 매단다. RDF 용어로는 n-ary relation, reification과 같은 문제의식이고, Wikidata는 statement + qualifier + reference로 같은 문제를 푼다 → [[Wikidata와-DBpedia]]. 프로퍼티 그래프는 엣지 속성으로 바로 쓸 수 있다 → [[RDF와-프로퍼티-그래프]].
- do-dop의 반례: "민수가 같은 책을 1월과 3월에 각각 빌렸다." 프로퍼티 그래프는 `BORROWED {month:1}` 엣지를 두 개 만들면 되지만 **RDF 그래프는 집합이라 같은 트리플을 두 번 적어도 한 사건이다.** `ex:Loan1`, `ex:Loan2`를 자원으로 만들어야 구분된다. "표현할 수 없는 게 아니라 표현 방식이 다르다." 반납·연장·벌금이 붙으면 프로퍼티 그래프에서도 대출을 노드로 올리는 게 낫다.
- 인수 관계에 날짜·금액 붙이기 (do-dop): PG는 `(A)-[:ACQUIRED {announcedAt, price}]->(B)`, RDF는 `Acquisition01 ──acquirer/target/announcedAt` 사건 자원.

## 직렬화와 내보내기 (5주차)

- **RDF 모델은 하나, Turtle·JSON-LD·N-Triples·RDF/XML은 같은 그래프를 적는 다른 방법**이다 (dldusgh318, heebindev, kdyann, yujeong430). "Turtle은 도구가 아니라 RDF를 적는 문법", "RDF를 Turtle로 질의하는 것이 아니다" (Yeongeunn). RDF = 데이터 모델 / Turtle = 문법 / 트리플 스토어 = 저장·질의 시스템의 3분할 (yujeong430).
- **왜 표준으로 내보내나** (e0ng): `{"activity": "…", "organization": "Naver"}`는 우리 프로그램만 의미를 안다 — `activity`가 문자열인지 개체인지 어떤 관계인지 다른 프로그램은 모른다. 개체·관계의 의미를 IRI로 명시한다. "내부 DB 테이블 구조만 쓰면 다른 도구가 의미를 바로 알기 어렵다" (heebindev).
- JSON-LD 키워드: `@context`(용어↔IRI), `@id`, `@type`, 그리고 e0ng만 적은 `@value`(리터럴)·`@language`(언어 태그 — `"Naver 지원 준비"@ko`), 객체 참조 술어에는 `"@type": "@id"`를 명시. 네임스페이스를 종류별로 쪼갠 멤버(e0ng: `ex:`·`activity:`·`period:`)와 하나로 둔 멤버(dldusgh318 `kg:`, heebindev `os:`, kdyann `cg:`, Yeongeunn `kg:`)가 갈린다.
- **evidence를 어디에 두나**: `chunk_id`·`evidence`·`confidence`는 2항 트리플에 바로 붙지 않는다. dldusgh318은 Turtle·JSON-LD에서 **명시적으로 제외**하고 PG·Neo4j에만 뒀다(reification은 한 사실이 여러 보조 트리플로 늘어 파일·질의가 커진다). kdyann은 `rdf:Statement` reification으로 ttl에 넣었다. e0ng·heebindev·Yeongeunn은 ttl 포함 여부를 적지 않았다. "근거를 붙이려면 관계를 1급 객체로 올려야 한다"는 결론은 셋이 같다 → [[Wikidata와-DBpedia]].
- 산출 규모: dldusgh318 295트리플(엣지 157), kdyann 589(사실 38), Yeongeunn 373(관계 20) — **사실 수와 트리플 수는 다른 단위**다. Yeongeunn은 두 직렬화 파일을 다시 파싱한 그래프가 원래 RDF와 동형인지 검증했다 → [[그래프-적재-Postgres와-Neo4j]].
- 의미 보존 (yujeong430, do-dop): 변환 전후 "다시 읽었을 때 트리플이 같은가", 같은 질문의 답이 유지되는가를 확인한다. 스키마 진화 시 `extraction_run` 버전 기록 → [[LLM-트리플-추출]].

## 멤버들이 확인한 것

- 4주차 노트는 전부 정리·설계이고, 실제 트리플을 추출·적재한 결과는 5주차 — 다섯 멤버가 Turtle을 내보냈다 → [[지식그래프와-온톨로지]].
- dldusgh318의 설계 결정(2026-09-23): RDF를 그대로 구현하지 않는다. 트리플 중심 → `entities`/`edges` 분리, 값도 Object → 목적·상태는 JSONB 속성, 관계 출처 별도 모델링 → **엣지에 `chunk_id`·`evidence`를 직접 저장**, RDF 표준 호환 → 검색·평가 편의 우선. 3주차 Citation 재검증 경험의 연장으로 `Graph Fact → 원본 Chunk → 실제 Evidence` 사슬을 남긴다 → [[데이터-수집과-출처-추적]].
- do-dop은 트리플 구성요소별 허용 값 표와 직렬화 관계도를 정리했고, e0ng은 Literal 타입·언어 태그와 네임스페이스 분해를 가장 자세히 썼다. heebindev는 `heebindev –참여한다→ KG 스터디 –사용한다→ PostgreSQL` 2-hop 예제로 최소 문법만 다뤘다.

## 함정 · 주의

- 문자열이 같다고 같은 대상이 아니고, 다른 IRI를 쓴 같은 대상은 별도 연결·정규화가 필요하다 (do-dop). `owl:sameAs`는 표현 방법을 줄 뿐 판단을 대신하지 않는다 → [[온톨로지와-추론]].
- RDF를 쓰기 위해 완성된 온톨로지가 반드시 필요한 것은 아니다 (do-dop).
- 예시 주어로 실명·소속을 쓰지 않는다. 멤버 노트 여럿이 본인 실명과 소속 기관을 RDF 예시에 썼는데, 위키에는 `ex:person`·github id로 옮긴다 (CLAUDE.md 민감 정보).
- **접두어 선언만으로 온톨로지가 생기지 않는다** — 접두어는 표기 편의이고 의미는 따로 정의한다 (kdyann). `calls`·`emits`는 선택한 관계 이름이지 RDF 내장 명령이 아니다. "관계를 기록하는 것과 실제 서비스 호출을 실행하는 것은 다르다" (Yeongeunn).
- 리터럴 3형 (kdyann): `ex:person`(대상) / `"이름"@ko`(언어 태그) / `"2026-09-28"^^xsd:date`(자료형). 어떤 값을 리터럴로 둘지의 기준: "그 주제에 교재·다른 주차·설명을 더 연결하려면 주제 자체에 식별자를 부여한다" (yujeong430). "접두어 글자가 달라도 풀어 쓴 IRI가 같으면 같은 대상" (yujeong430).

## 열린 질문

- 여러 멤버의 그래프를 합칠 때 IRI 체계를 어떻게 맞출 것인가 — 내부 ID(`project:a`, `technology:redis`)로 시작한 dldusgh318 실습은 전역 식별을 고려하지 않았다 → [[시맨틱-웹에서-지식그래프까지]] 환류.

## 관련

- [[지식그래프와-온톨로지]] · [[온톨로지와-추론]] · [[SPARQL]] · [[Wikidata와-DBpedia]] · [[RDF와-프로퍼티-그래프]] · [[데이터-수집과-출처-추적]] · [[시맨틱-웹에서-지식그래프까지]]

## 출처

- dldusgh318 · RDF 기본 — 문서가 아니라 사실과 관계를 저장하려면? (2026-09-23) — [members/dldusgh318/notes/week4/01-rdf.md](../../members/dldusgh318/notes/week4/01-rdf.md); 4주차 요약 §1 — [00-summary.md](../../members/dldusgh318/notes/week4/00-summary.md)
- do-dop · 시맨틱 웹에서 지식그래프까지 (§3 RDF, §10) — [members/do-dop/notes/04-semantic-web-to-knowledge-graph.md](../../members/do-dop/notes/04-semantic-web-to-knowledge-graph.md); 프로퍼티 그래프와 RDF (§대출 예시) — [04-relational-and-graph-data-models.md](../../members/do-dop/notes/04-relational-and-graph-data-models.md)
- e0ng · RDF·OWL·SPARQL과 그래프 모델 (§RDF 기본) — [members/e0ng/notes/04-2-knowledge-graph-basics.md](../../members/e0ng/notes/04-2-knowledge-graph-basics.md)
- heebindev · 지식 그래프의 배경과 기업 사례 (§3–4) — [members/heebindev/notes/04-knowledge-graph-background.md](../../members/heebindev/notes/04-knowledge-graph-background.md)
- lys0611 · 지식 그래프의 배경 (§2) — [members/lys0611/notes/06-knowledge-graph-foundations.md](../../members/lys0611/notes/06-knowledge-graph-foundations.md)
- kdyann · 온톨로지 모델링 (§RDF·Turtle) — [members/kdyann/notes/04-2-ontology-modeling.md](../../members/kdyann/notes/04-2-ontology-modeling.md); RDF·OWL 데이터 파이프라인 (§직렬화) — [notes/05-rdf-owl-data-pipeline.md](../../members/kdyann/notes/05-rdf-owl-data-pipeline.md)
- Yeongeunn · 지식 그래프와 온톨로지 (§RDF), 트리플 파이프라인 (§6층 구분, §10 직렬화) — [members/Yeongeunn/notes/09-week4-ontology-background.md](../../members/Yeongeunn/notes/09-week4-ontology-background.md), [notes/10-week5-triple-pipeline.md](../../members/Yeongeunn/notes/10-week5-triple-pipeline.md)
- yujeong430 · 시맨틱 웹에서 지식 그래프까지 (§IRI·리터럴), RDF 데이터 파이프라인 개념 (§8–12 직렬화) — [members/yujeong430/notes/10-semantic-web-to-knowledge-graph.md](../../members/yujeong430/notes/10-semantic-web-to-knowledge-graph.md), [notes/11-rdf-data-pipeline-concepts.md](../../members/yujeong430/notes/11-rdf-data-pipeline-concepts.md) (PR #19 미머지)
- kungbi · W4 지식 그래프의 배경 (§RDF 트리플 타입 규칙, 그림 3) — [members/kungbi/notes/02-knowledge-graph-background.md](../../members/kungbi/notes/02-knowledge-graph-background.md)
- 5주차 직렬화: dldusgh318 · W5-3 RDF 형식 — [members/dldusgh318/notes/week5/03-rdf-format.md](../../members/dldusgh318/notes/week5/03-rdf-format.md); e0ng · RDF 직렬화 포맷 — [members/e0ng/notes/05-3-rdf-serialization.md](../../members/e0ng/notes/05-3-rdf-serialization.md) (PR #34 미머지); heebindev · 데이터 파이프라인 (§7) — [members/heebindev/notes/05-rdf-owl-data-pipeline.md](../../members/heebindev/notes/05-rdf-owl-data-pipeline.md)
- 외부: RDF 1.1 Primer https://www.w3.org/TR/rdf11-primer/ · RDF 1.1 Concepts https://www.w3.org/TR/rdf11-concepts/ · Turtle https://www.w3.org/TR/turtle/ · JSON-LD 1.1 https://www.w3.org/TR/json-ld11/
