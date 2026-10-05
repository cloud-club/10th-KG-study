---
title: "프로퍼티 그래프와 RDF: 두 그래프 모델의 철학 차이"
date: 2026-09-24
tags: [rdbms, knowledge-graph, property-graph, rdf, traversal, cypher, sparql]
status: complete
---

# 프로퍼티 그래프와 RDF: 두 그래프 모델의 철학 차이

W4의 핵심 질문은 “검색은 문서를 찾는다. 사실과 관계를 찾으려면 무엇이 필요한가?”다. 이 문서는 관계형 데이터베이스를 배경으로, 프로퍼티 그래프와 RDF가 같은 사실을 어떻게 표현하고 무엇을 우선하는지 비교한다.

지식그래프가 필요한 이유를 이해하려면 관계형 데이터베이스도 관계를 표현할 수 있다는 사실에서 출발해야 한다. 차이는 **어떤 질문과 변경을 더 자연스럽게 처리하도록 설계되었는가**에 있다.

W4는 이론 주이므로 코드는 표현 방식을 비교하기 위한 읽기 예시다. DB 설치·적재·질의 실행은 W5에서 다룬다. RDF의 기본 용어는 [시맨틱 웹에서 지식그래프까지](04-semantic-web-to-knowledge-graph.md), 클래스와 추론은 [온톨로지와 추론](04-ontology-and-inference.md)을 참고한다.

## 먼저 보는 역할 비교

| 구분 | RDBMS | Knowledge Graph | Ontology |
|---|---|---|---|
| 핵심 | 행과 열로 데이터 관리 | 개체와 관계를 연결 | 개념과 관계의 의미 정의 |
| 기본 구조 | 테이블·행·열 | 노드·엣지 또는 트리플 | 클래스·속성·공리 |
| 주요 작업 | 저장·JOIN·필터·집계 | 관계·경로 탐색 | 분류·일관성 확인·추론 |
| 예시 | 직원 행의 `team_id` | 직원 → 소속 → 팀 | Team은 Organization의 하위 클래스 |

RDBMS와 그래프 데이터베이스는 데이터를 저장하고 조회하는 구현 방식이다. 온톨로지는 특정 저장소가 아니라 데이터에 사용할 개념과 관계의 의미를 정의하는 체계다.

## 1. RDBMS도 관계를 표현할 수 있다

관계형 데이터베이스는 외래키로 행 사이의 관계를 표현한다.

```sql
CREATE TABLE person (
    id INT PRIMARY KEY,
    name VARCHAR(50),
    parent_id INT REFERENCES person(id)
);
```

`parent_id`는 같은 테이블의 다른 행을 참조한다. 이를 자기 참조 외래키라고 하며 조직도, 댓글 계층과 카테고리 구조에도 사용할 수 있다.

| id | name | parent_id |
|---:|---|---:|
| 1 | 민수 | 2 |
| 2 | 어머니 | 3 |
| 3 | 할머니 | `NULL` |

부모가 여러 명이거나 관계 자체에 속성이 필요하면 별도의 관계 테이블을 만들 수 있다.

```sql
CREATE TABLE parent_relation (
    child_id INT REFERENCES person(id),
    parent_id INT REFERENCES person(id),
    PRIMARY KEY (child_id, parent_id)
);
```

따라서 “RDBMS는 관계를 표현하지 못한다”는 설명은 틀리다. 관계 종류와 탐색 경로가 늘어날수록 JOIN 구조와 스키마 변경이 복잡해질 수 있다는 것이 더 정확한 설명이다.

## 2. 깊이를 모르는 계층은 재귀적으로 탐색한다 — 보조 읽기

민수의 부모, 조부모와 그 위의 조상을 모두 찾으려면 몇 단계가 필요한지 미리 알 수 없다. PostgreSQL 같은 RDBMS에서는 재귀 CTE를 사용할 수 있다.

```sql
WITH RECURSIVE ancestors AS (
    SELECT id, name, parent_id
    FROM person
    WHERE id = 1

    UNION ALL

    SELECT p.id, p.name, p.parent_id
    FROM person p
    JOIN ancestors a ON p.id = a.parent_id
)
SELECT name
FROM ancestors
WHERE id <> 1;
```

재귀 CTE는 계층 탐색에 유용하지만, 데이터에 순환이 있으면 반복될 수 있다. 실무에서는 방문한 노드를 기록하거나 탐색 깊이를 제한해야 한다.

## 3. 프로퍼티 그래프: 노드·관계·속성

프로퍼티 그래프는 대상을 노드로, 대상 사이의 연결을 관계로 표현한다. 노드와 관계 양쪽에 키–값 속성을 붙일 수 있다. Neo4j는 이 모델을 사용하는 그래프 데이터베이스다.

```text
(톰 행크스:Person:Actor)
    ──ACTED_IN {role: "Forrest"}──▶ (포레스트 검프:Movie)
```

| 구성요소 | 의미 | 예시 |
|---|---|---|
| 노드 | 식별하고 관리할 대상 | 사람, 영화 |
| 라벨 | 노드의 분류. 하나의 노드에 여러 개 가능 | Person, Actor |
| 관계 | 출발 노드와 도착 노드를 연결 | 배우 → 영화 |
| 관계 타입 | 연결의 종류. 관계 하나에 정확히 하나 | ACTED_IN |
| 속성 | 노드 또는 관계의 키–값 정보 | 이름, 개봉 연도, 배역 |

배역은 배우 자체나 영화 자체가 아니라 “이 배우가 이 영화에서 맡은 역할”을 설명하므로 관계에 붙인다. 같은 두 노드 사이에 같은 타입의 관계가 여러 개 존재할 수도 있다.

Neo4j의 관계는 저장할 때 방향이 있지만, 조회할 때 방향을 무시할 수 있다. 라벨을 여러 개 붙이는 것만으로 클래스 계층이나 추론 규칙이 자동 정의되는 것은 아니다.

Neo4j에서 스키마가 선택 사항이라는 말은 인덱스와 제약조건을 미리 만들지 않고도 데이터를 넣을 수 있다는 뜻이다. 라벨·관계·속성의 의미를 설계할 필요가 없다는 뜻은 아니다. 인덱스는 조회 성능을, 제약조건은 데이터 무결성을 돕는다.

## 4. RDF: 트리플·공통 식별자·어휘

RDF는 사실을 주어·술어·목적어 트리플로 표현하는 데이터 모델이다. RDF 트리플 스토어는 이 모델의 데이터를 저장하고 질의하는 데이터베이스다. RDF와 트리플 스토어는 모델과 제품이라는 서로 다른 층위에 있다.

```turtle
@prefix ex: <https://example.org/> .

ex:TomHanks ex:actedIn ex:ForrestGump .
```

RDF는 대상뿐 아니라 관계도 IRI로 식별한다. 여러 데이터셋이 같은 IRI와 공통 어휘를 사용하면 같은 대상과 관계를 기준으로 정보를 연결할 수 있다. 문자열 이름이 같다는 이유만으로 같은 대상이 되지는 않으며, 다른 IRI를 사용한 같은 대상은 별도 연결·정규화가 필요하다.

RDF의 목표는 공통 모델로 데이터를 교환하고 여러 출처를 연결하는 것이다. RDFS와 OWL은 클래스·관계의 의미와 공리를 표현한다. RDF를 사용하기 위해 완성된 온톨로지가 반드시 필요한 것은 아니다.

용어도 구분해야 한다. 프로퍼티 그래프의 property는 키–값 속성이고, RDF의 property는 트리플의 술어다. RDF는 작성 문법이 아니며 Turtle과 JSON-LD는 RDF를 기록하는 직렬화 문법이다.

## 5. 두 진영의 철학 차이

아래 비교는 배타적인 기능 차이가 아니라 각 모델이 강조해 온 설계 관점이다. 프로퍼티 그래프도 데이터 교환과 의미 모델링에 사용할 수 있고, RDF도 애플리케이션의 저장·조회에 사용할 수 있다.

| 관점 | 프로퍼티 그래프 — Neo4j 계열 | RDF 트리플 스토어 |
|---|---|---|
| 중심 질문 | 연결된 데이터를 어떻게 모델링하고 조회할까? | 여러 출처의 대상과 의미를 어떻게 공유할까? |
| 기본 모델 | 노드·관계·속성 | 주어·술어·목적어 트리플 |
| 식별 | DB 내부 식별자와 애플리케이션 키. IRI도 속성으로 사용 가능 | IRI로 대상과 술어 식별. 빈 노드와 리터럴도 사용 |
| 관계의 부가 정보 | 관계에 속성을 직접 부여 | RDF 1.1에서는 사건 노드·재진술 등으로 모델링 |
| 의미 정의 | 애플리케이션 모델·코드·제약조건 중심 | 공통 어휘와 RDFS·OWL 의미론 활용 |
| 대표 질의 언어 | Cypher, GQL | SPARQL |
| 특히 살펴볼 강점 | 관계 속성, 경로 표현, 애플리케이션 모델링 | 데이터 교환, 공통 식별, 어휘 재사용, 추론 기반 |

GQL은 프로퍼티 그래프를 위한 ISO 표준 질의 언어이고, Cypher는 Neo4j에서 사용하는 관련 질의 언어다. 둘을 동일한 언어로 취급하지 않는다.

### 같은 사실을 두 방식으로 표현하기

“민수가 같은 책을 1월과 3월에 각각 빌렸다”를 생각해보자.

프로퍼티 그래프는 별개의 관계 두 개에 정보를 붙일 수 있다.

```text
(민수)-[BORROWED {month: 1}]->(책 A)
(민수)-[BORROWED {month: 3}]->(책 A)
```

RDF 그래프는 트리플의 집합이다. 다음 트리플을 두 번 적어도 두 대출 사건이 구분되지 않는다.

```turtle
ex:Minsu ex:borrowed ex:BookA .
```

대출 사건을 각각 자원으로 표현하면 구분할 수 있다.

```turtle
ex:Loan1 ex:borrower ex:Minsu ;
         ex:book ex:BookA ;
         ex:month 1 .

ex:Loan2 ex:borrower ex:Minsu ;
         ex:book ex:BookA ;
         ex:month 3 .
```

RDF로 표현할 수 없는 것이 아니라 표현 방식이 다르다. 반납·연장·벌금처럼 대출 자체를 가리키는 정보가 늘어나면 프로퍼티 그래프에서도 대출을 별도 노드로 만드는 선택이 유용하다.

## 6. Cypher와 SPARQL: 둘 다 관계 패턴을 찾는다

Cypher는 Neo4j의 그래프 질의 언어다. SQL처럼 조회·생성·수정에 사용하며, 노드와 관계 패턴을 그림과 비슷한 문법으로 적는다.

```cypher
MATCH (actor:Person {name: "Tom Hanks"})-[:ACTED_IN]->(movie:Movie)
RETURN movie.title;
```

뜻은 “이름이 Tom Hanks인 사람에서 출연 관계를 따라 영화 제목을 찾는다”다. 괄호는 노드, 대괄호는 관계, 화살표는 방향이다.

SPARQL도 트리플 패턴을 이용해 같은 종류의 질문을 표현할 수 있다.

```sparql
PREFIX ex: <https://example.org/>

SELECT ?title WHERE {
  ex:TomHanks ex:actedIn ?movie .
  ?movie ex:title ?title .
}
```

`?movie`와 `?title`은 패턴에 맞는 값을 찾을 변수다. 두 언어 모두 관계 패턴을 찾는다. SPARQL 자체를 추론기라고 부르면 안 된다. 온톨로지 추론 결과를 질의에 반영할지는 저장소의 추론 지원과 설정 등에 달려 있다.

그래프의 관계를 따라 이동하는 작업은 traversal(탐색), 그 연결의 순서는 path(경로)다. 경로 길이는 노드 수가 아니라 관계 수로 센다. 가변 길이 경로와 실제 질의 실행은 W5에서 다룬다.

## 7. 지식그래프의 의미 모델과 확장

### 개체·관계와 의미 정의

지식그래프에서 데이터를 함께 해석하려면 개체와 관계의 이름이 무엇을 뜻하는지 정의해야 한다. 이 의미 정의는 라벨과 관계 설명, 분류체계, 온톨로지 등으로 표현할 수 있다.

| 표현 수준 | 정의하는 내용 | 예시 |
|---|---|---|
| 라벨과 관계 이름 | 대상의 종류와 연결의 의미 | Person, Book, wrote |
| 분류체계 | 개념의 상하위 구조 | Book은 CreativeWork의 하위 개념 |
| 온톨로지 공리 | 개념·관계 사이의 논리적 규칙 | wrote와 writtenBy는 역관계 |

단순한 관계 조회에는 라벨과 관계 설명으로 모델을 시작할 수 있다. 여러 데이터셋의 개념을 맞추거나 규칙에 따라 새 사실을 도출해야 할 때는 분류체계와 온톨로지 공리를 추가한다.

### 점진적 확장과 모델 변경

프로퍼티 그래프와 RDF 모두 데이터와 의미 모델을 점진적으로 확장할 수 있다. 새로운 관계를 추가할 때는 이름과 방향, 연결할 대상의 종류, 부가 정보의 표현 방식을 정한다.

예를 들어 책 대출 관계에 대출일만 기록하다가 반납·연장·벌금 정보가 필요해지면, 대출을 독립된 사건으로 모델링할 수 있다. 이때 기존 데이터를 새 구조로 변환하고 관련 질의도 수정해야 한다. 이런 변경은 두 모델 모두에서 발생할 수 있다.

### 저장 모델과 온톨로지의 조합

온톨로지는 개념과 관계의 의미를 정의하고, 데이터베이스는 사실을 저장하고 질의한다. RDF와 온톨로지로 의미를 정의하면서 프로퍼티 그래프를 서비스의 탐색 모델로 사용하는 구성도 가능하다.

두 모델 사이에서 데이터를 변환할 때는 다음 매핑을 정해야 한다.

- RDF의 IRI를 프로퍼티 그래프에서 어떤 키로 보존할지
- RDF의 클래스와 술어를 노드 라벨·관계 타입·속성에 어떻게 대응시킬지
- 관계의 근거·날짜·반복 사건을 어떻게 표현할지
- 자료형·언어 태그·여러 값 등 원본 정보를 어떻게 유지할지

파일을 변환하는 것과 의미를 보존하는 것은 별개의 작업이다. 매핑 규칙을 정하고 변환 전후에 같은 질문의 답이 유지되는지 확인해야 한다.

### 질의와 추론의 요구사항

저장된 연결을 찾는 작업과 규칙으로 새 사실을 도출하는 작업은 요구사항을 따로 정한다. OWL 프로파일마다 지원하는 표현과 계산 특성이 다르므로 필요한 추론 규칙에 맞춰 선택한다.

조회 성능은 모델 이름만으로 결정되지 않는다. 데이터 크기, 질의 패턴, 인덱스, 실행 계획과 추론 설정이 영향을 주므로 실제 사용할 데이터와 질문으로 비교한다.

## 8. 모델 선택과 W4 화이트보드 질문

| 판단 질문 | 검토할 내용 |
|---|---|
| 관계마다 날짜·역할·점수가 필요한가? | 관계 속성으로 표현할지, 사건 노드로 만들지 |
| 여러 조직의 데이터를 연결해야 하는가? | 공통 IRI·어휘·교환 형식·매핑이 필요한지 |
| 계층·역관계·동치 추론이 필요한가? | 어떤 공리와 추론 지원이 필요한지 |
| 반복해서 답할 질문은 무엇인가? | 실제 질의 패턴과 데이터 범위를 정의했는지 |
| 정확도와 성능은 어떻게 확인할 것인가? | 정답 경로·근거·측정 조건을 정했는지 |

W3에서 못 답한 질문 하나를 골라, 설치 없이 화이트보드에 다음을 그려본다.

1. 질문에 등장하는 대상과 관계를 구분한다.
2. 답을 얻으려면 어떤 대상들을 어떤 관계로 연결해야 하는지 그린다.
3. 각 관계에 근거 문서가 있는지 표시한다. 없는 관계를 추측으로 채우지 않는다.
4. 프로퍼티 그래프에서는 무엇을 노드·관계·속성으로 둘지 정한다.
5. RDF에서는 무엇을 IRI·리터럴·사건 자원으로 표현할지 비교한다.

그래프에 경로가 없다는 것은 현재 데이터로 답을 찾지 못했다는 뜻이다. 현실에 그 관계가 없다는 증명은 아니다.

## 핵심 정리

1. RDBMS도 관계와 계층을 표현할 수 있다.
2. 연결 종류와 경로 탐색이 핵심일 때 그래프 모델이 더 자연스럽다.
3. 온톨로지는 데이터베이스 제품이 아니라 개념과 관계의 의미를 정의한다.
4. 프로퍼티 그래프와 RDF는 철학과 강점이 다르며 함께 사용할 수도 있다.
5. Cypher와 SPARQL은 모두 관계 패턴을 질의하며, 질의와 추론은 구분해야 한다.
6. 관계 속성·공통 식별자·의미 공유·질의 패턴을 기준으로 모델을 선택한다.

## 참고자료

- [Designing Data-Intensive Applications, Chapter 2 — O'Reilly](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/ch02.html)
- [PostgreSQL Recursive Queries](https://www.postgresql.org/docs/current/queries-with.html#QUERIES-WITH-RECURSIVE)
- [RDF 1.1 Primer — W3C](https://www.w3.org/TR/rdf11-primer/)
- [RDF Concepts — W3C](https://www.w3.org/TR/rdf11-concepts/)
- [Linked Data — Tim Berners-Lee](https://www.w3.org/DesignIssues/LinkedData.html)
- [OWL 2 Profiles — W3C](https://www.w3.org/TR/owl2-profiles/)
- [SPARQL 1.1 Query Language — W3C](https://www.w3.org/TR/sparql11-query/)
- [SPARQL 1.1 Property Paths — W3C](https://www.w3.org/TR/sparql11-query/#propertypaths)
- [Graph database concepts — Neo4j](https://neo4j.com/docs/getting-started/appendix/graphdb-concepts/)
- [RDF vs. property graphs — Neo4j, 2024](https://neo4j.com/blog/knowledge-graph/rdf-vs-property-graphs-knowledge-graphs/)
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/current/)
