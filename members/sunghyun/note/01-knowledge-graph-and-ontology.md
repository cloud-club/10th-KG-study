---
title: RAG, 지식 그래프와 온톨로지 기초
date: 2026-09-12
tags: [rag, knowledge-graph, triple, ontology, rdf, neo4j, bm25, vector-search]
status: in-progress
---

# 01. RAG, 지식 그래프와 온톨로지 기초

> 참고 자료:
>
> - 개인 Notion 1 Week
> - 온톨로지 세미나 PDF
> - PostgreSQL / pgvector / Elasticsearch / Neo4j 학습 내용

## 한 줄 요약

RAG는 필요한 문서 조각을 검색해 LLM에 전달하는 방식이고, 지식 그래프는 정보를 대상과 관계로 연결해서 표현하는 방식이다.  
Neo4j는 관계 탐색에 강하고, RDF와 온톨로지는 관계와 개념의 의미를 정의하고 추론하는 데 강하다.

---

## 핵심 개념

- RAG: 필요한 정보를 검색해서 LLM에 함께 전달하는 방식이다.
- Chunk: 긴 문서를 검색하기 좋은 의미 단위로 나눈 조각이다.
- Metadata: 문서명, 작성자, 날짜, 카테고리처럼 검색 범위를 줄이는 정보다.
- BM25: 키워드 기반으로 문서의 관련도를 계산하는 검색 방식이다.
- Embedding: 문장의 의미를 숫자 배열로 표현한 값이다.
- Vector Search: 의미가 가까운 문서를 찾는 검색 방식이다.
- 트리플(Triple): 하나의 정보를 주어 - 술어 - 목적어로 나타낸 것이다.
- 지식 그래프(Knowledge Graph): 여러 대상을 관계로 연결해서 표현한 그래프다.
- RDF: 데이터를 트리플 형태로 표현하기 위한 표준이다.
- Neo4j: Property Graph 방식으로 관계 탐색에 강한 그래프 DB다.
- 온톨로지(Ontology): 개념과 관계의 의미와 규칙을 정의한 모델이다.
- Reasoning: 온톨로지의 규칙으로 직접 저장하지 않은 사실을 도출하는 것이다.

---

# 1. RAG

LLM은 개인 Notion이나 회사 문서 내용을 기본적으로 알지 못한다.

모든 문서를 한 번에 넣는 것도 비효율적이므로, 질문과 관련된 내용만 먼저 검색해서 LLM에 전달한다.

~~~text
사용자 질문
   ↓
관련 문서 검색
   ↓
필요한 Chunk 선택
   ↓
질문 + 검색 결과
   ↓
LLM 답변
~~~

RAG는 특정 DB나 검색 제품 이름이 아니라 이 전체 흐름을 말한다.

---

## 왜 Chunk로 나눌까?

문서 하나 전체가 항상 필요한 것은 아니다.

예를 들어 Codebeamer 운영 가이드에서 Baseline에 대해 질문했다면 Baseline 부분 몇 문단만 필요할 수 있다.

~~~text
Codebeamer 운영 가이드

Chunk 1 - 사용자 관리
Chunk 2 - Tracker 설정
Chunk 3 - Baseline
Chunk 4 - Test Management
~~~

Chunk는 무조건 작을수록 좋은 것은 아니다.

- 너무 크면 관련 없는 내용까지 포함된다.
- 너무 작으면 앞뒤 문맥이 끊긴다.
- 보통 문단이나 섹션처럼 하나의 의미가 유지되는 단위가 적당하다.

---

## Metadata는 왜 필요할까?

Metadata는 검색 범위를 먼저 줄이는 데 사용한다.

~~~json
{
  "document": "Codebeamer 운영 가이드",
  "section": "Baseline",
  "year": 2026
}
~~~

역할을 나누면 다음과 같다.

~~~text
Metadata
→ 어디에서 찾을지 좁힘

Chunk Search
→ 그 안에서 어떤 내용이 필요한지 찾음
~~~

하나의 Chunk에는 보통 다음 정보가 같이 저장될 수 있다.

~~~text
Chunk
├─ text
├─ metadata
└─ embedding
~~~

Embedding만 저장하는 것이 아니라 원문과 Metadata도 함께 저장한다.

---

# 2. 검색 방식

## grep

grep은 입력한 문자열이나 패턴을 직접 찾는다.

~~~bash
grep -Rni "Baseline" data/
~~~

- 정확한 문자열 검색에 좋다.
- 같은 단어가 없으면 의미가 비슷해도 찾기 어렵다.
- 관련도 순위를 계산하는 검색엔진은 아니다.

---

## BM25

BM25는 검색어와 문서의 키워드 관련도를 계산한다.

보통 역색인(Inverted Index)을 사용한다.

~~~text
Baseline → 문서 1, 문서 5
Workflow → 문서 2, 문서 7
Test     → 문서 3, 문서 8
~~~

다음과 같은 검색에 강하다.

- 제품명
- 에러 코드
- 정확한 기술명
- 특정 키워드

Elasticsearch가 대표적으로 BM25 기반 검색을 제공한다.

---

## Vector Search

문장을 Embedding 모델로 숫자 배열로 변환한 뒤 의미가 가까운 문서를 찾는다.

~~~text
"서버 연결에 실패했다"
→ [0.12, 0.83, -0.31, ...]
~~~

같은 단어가 없어도 의미가 비슷하면 찾을 수 있다.

PostgreSQL에서는 pgvector를 이용해 벡터를 저장하고 검색할 수 있다.

---

## Hybrid Search

BM25와 Vector Search는 잘하는 일이 다르다.

~~~text
BM25
→ 키워드에 강함

Vector Search
→ 의미에 강함
~~~

따라서 둘의 결과를 함께 사용하는 Hybrid Search를 사용할 수 있다.

---

# 3. RDBMS와 그래프

RDBMS는 데이터를 행과 열로 저장한다.

정해진 형식의 데이터를 저장하고 조회할 때 잘 맞는다.

하지만 관계를 여러 단계 따라가는 일이 많아지면 조인이 복잡해질 수 있다.

그래프는 데이터 자체보다 데이터 사이의 관계를 중심으로 표현한다.

~~~text
노드(Node) = 대상
엣지(Edge) = 대상 사이의 관계
~~~

예:

~~~text
[이성현] --참여한다--> [RAG Study] --사용한다--> [PostgreSQL]
~~~

RDBMS가 나쁜 것이 아니라 문제의 성격이 다르다.

- 표와 정형 데이터 관리: RDBMS가 자연스럽다.
- 관계를 여러 단계 따라가기: Graph DB가 자연스럽다.

---

# 4. 트리플과 지식 그래프

트리플은 하나의 정보를 세 부분으로 표현한다.

~~~text
주어 - 술어 - 목적어
Subject - Predicate - Object
~~~

예:

~~~text
이성현 - 참여한다 - RAG Study
RAG Study - 사용한다 - PostgreSQL
~~~

트리플 하나를 그래프의 연결 하나라고 볼 수 있다.

트리플이 여러 개 연결되면 다음과 같은 그래프가 된다.

~~~text
[이성현]
   |
 참여한다
   ↓
[RAG Study]
   |
 사용한다
   ↓
[PostgreSQL]
~~~

이처럼 여러 대상과 관계를 연결한 구조가 지식 그래프다.

답을 찾기 위해 여러 관계를 연속해서 따라가는 질문을 Multi-hop Question이라고 한다.

예:

~~~text
이성현
→ 참여한 스터디
→ 사용하는 DB
→ 지원하는 벡터 기술
~~~

---

# 5. RDF

RDF는 정보를 Triple 형태로 표현하기 위한 표준이다.

RDF 자체는 저장소가 아니다.

예를 들어 Turtle 문법으로는 다음처럼 표현할 수 있다.

~~~turtle
@prefix ex: <https://example.com/> .

ex:seonghyeon ex:participatesIn ex:ragStudy .
ex:ragStudy ex:uses ex:postgresql .
~~~

RDF 데이터를 저장하는 전용 저장소를 보통 Triplestore라고 한다.

예:

- GraphDB
- Stardog
- Apache Jena
- Amazon Neptune의 RDF 기능

RDF 데이터는 주로 SPARQL로 조회한다.

---

# 6. URI와 Turtle

RDF에서는 대상을 정확히 구분하기 위해 URI를 사용할 수 있다.

~~~text
https://example.com/person/lee-seonghyeon
https://example.com/study/rag-study
~~~

URI는 웹 주소처럼 생겼지만 반드시 실제 웹페이지가 존재해야 하는 것은 아니다.

여기서는 대상을 구분하는 고유한 식별자 역할을 한다.

Turtle은 긴 URI를 사람이 읽기 쉬운 형태로 작성할 수 있게 해주는 RDF 문법이다.

~~~turtle
@prefix ex: <https://example.com/> .

ex:seonghyeon ex:participatesIn ex:ragStudy .
~~~

---

# 7. Neo4j와 RDF는 무엇이 다를까?

둘 다 그래프를 저장하고 탐색할 수 있다.

차이는 중심에 두는 것이 다르다.

## Neo4j

Neo4j는 Property Graph 방식을 사용한다.

~~~text
(:Person {name: "이성현"})
   |
   | PARTICIPATES_IN
   | since: "2026-09"
   ↓
(:Study {name: "RAG Study"})
~~~

노드와 관계에 Property를 붙이기 쉽다.

Neo4j가 잘 맞는 질문:

- 내가 참여한 프로젝트는?
- 그 프로젝트에서 사용한 기술은?
- 같은 기술을 사용하는 다른 프로젝트는?
- 두 노드 사이의 최단 경로는?

핵심은 다음과 같다.

> 어떤 관계를 따라가면 원하는 노드에 도착하는가?

즉 관계와 경로 탐색이 중심이다.

---

## RDF + Ontology

RDF와 Ontology는 대상과 관계의 의미를 표준적으로 정의하는 데 강하다.

예:

~~~text
Kubernetes rdf:type ContainerPlatform

ContainerPlatform
subClassOf
InfrastructureTechnology

InfrastructureTechnology
subClassOf
Technology
~~~

직접 다음 관계를 저장하지 않았더라도:

~~~text
Kubernetes rdf:type Technology
~~~

라고 판단할 수 있다.

핵심은 다음과 같다.

> 이 대상과 관계는 무슨 뜻이며, 그 의미로 무엇을 더 알 수 있는가?

즉 의미, 규칙, 추론이 중심이다.

---

# 8. 온톨로지

온톨로지는 지식 그래프에서 사용할 개념과 관계의 의미와 규칙을 정의한다.

예:

~~~text
개념
- Person
- Study
- Technology

관계
- participatesIn
- uses
~~~

관계가 어떤 대상을 연결할 수 있는지도 정의할 수 있다.

~~~text
participatesIn
Person → Study

uses
Study → Technology
~~~

개념의 계층도 정의할 수 있다.

~~~text
GraphDatabase
  ↓ subClassOf
Database
  ↓ subClassOf
Technology
~~~

온톨로지는 단순히 관계 이름을 통일하는 것보다 넓은 개념이다.

- 개념 종류
- 관계 의미
- 상위 / 하위 개념
- 동일 개념
- 역관계
- 규칙

등을 정의할 수 있다.

---

# 9. Reasoning

온톨로지 규칙을 이용해서 직접 저장하지 않은 사실을 도출하는 것을 Reasoning이라고 한다.

예:

~~~text
PostgreSQL rdf:type Database
Database subClassOf Technology
~~~

직접 다음 데이터를 저장하지 않았더라도:

~~~text
PostgreSQL rdf:type Technology
~~~

라고 추론할 수 있다.

Neo4j에서도 비슷한 결과를 쿼리나 애플리케이션 로직으로 구현할 수 있다.

차이는 RDF / Ontology에서는 이런 의미 규칙 자체를 데이터 모델에 정의할 수 있다는 점이다.

---

# 10. Neo4j와 RDF를 고르는 기준

데이터 크기보다 어떤 질문을 해결하려는지가 중요하다.

## Neo4j가 자연스러운 경우

관계와 탐색 경로가 명확하다.

~~~text
A → B → C
~~~

질문도 정의된 관계를 따라가면 답을 찾을 수 있다.

> 연결과 경로 탐색 중심

## RDF + Ontology가 자연스러운 경우

다음과 같은 의미 규칙이 중요하다.

- 어떤 개념의 하위 종류인가?
- 서로 다른 이름이 같은 개념인가?
- 이 관계의 반대 관계는 무엇인가?
- 직접 저장하지 않은 사실도 규칙상 참인가?

> 의미, 규칙, 추론 중심

모호한 자연어 질문을 RDF가 자동으로 더 잘 이해하는 것은 아니다.

자연어 질문의 해석은 보통 LLM이나 검색 계층이 담당하고, RDF와 Ontology는 해석된 질문에 사용할 의미 구조를 제공한다.

---

# 11. 개인 Notion 데이터에는 어떻게 적용할까?

현재 목표라면 Neo4j부터 시작하는 것이 이해하기 쉽다.

예:

~~~text
이성현 → 참여한다 → RAG Study
RAG Study → 사용한다 → PostgreSQL
RAG Study → 공부한다 → Knowledge Graph
Project A → 사용한다 → Kubernetes
~~~

Neo4j에서는 이런 연결을 바로 시각적으로 확인하고 탐색할 수 있다.

현재 생각할 수 있는 구조는 다음과 같다.

~~~text
                    Notion
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
       Chunking                Entity 추출
          │                       │
          ▼                       ▼
 PostgreSQL + pgvector          Neo4j
          │                 Knowledge Graph
          │                       │
   Vector Search             관계 탐색
          │                       │
          └───────────┬───────────┘
                      ▼
                     RAG
                      │
                      ▼
                     LLM
~~~

필요하면 Elasticsearch를 추가해 BM25 검색을 사용할 수 있다.

이후 의미 규칙과 추론까지 확장하고 싶다면 같은 데이터를 RDF / Ontology로 표현해 볼 수 있다.

---

## 예시 / 코드

RDF 데이터를 SPARQL로 조회하면 다음과 같은 형태가 된다.

~~~sparql
PREFIX ex: <https://example.com/>

SELECT ?technology
WHERE {
  ex:seonghyeon ex:participatesIn ?study .
  ?study ex:uses ?technology .
}
~~~

이 쿼리는 다음 관계를 따라간다.

~~~text
이성현
→ 참여한 스터디
→ 사용하는 기술
~~~

---

## 핵심 표현

~~~text
RAG
→ 필요한 정보를 검색해서 LLM에게 전달하는 방식

Metadata
→ 어디에서 찾을지 좁힘

Chunk Search
→ 어떤 내용이 필요한지 찾음

BM25
→ 키워드 검색

Vector Search
→ 의미 검색

Knowledge Graph
→ 대상을 관계로 연결한 지식 구조

Neo4j
→ 어떤 관계를 따라가면 되는가?

RDF + Ontology
→ 이 관계와 개념은 무슨 뜻이고,
   그 의미로 무엇을 더 알 수 있는가?

Reasoning
→ 의미 규칙을 이용해 직접 저장하지 않은 사실을 도출
~~~

---

## 궁금한 점 / 더 알아볼 것

- [ ] 실제 Notion 문서를 어떤 기준으로 Chunking할까?
- [ ] BM25와 Vector Search 결과를 어떻게 비교할까?
- [ ] Notion에서 Entity와 Relation을 자동으로 어떻게 추출할까?
- [ ] Neo4j에서 개인 Knowledge Graph를 어떤 구조로 시작할까?
- [ ] 같은 데이터를 RDF로 표현하면 Neo4j와 어떻게 다를까?
- [ ] RDFS와 OWL은 온톨로지에서 각각 어떤 역할을 할까?
- [ ] Graph RAG는 Vector RAG와 실제로 어떻게 결합될까?

---

## 스터디에서 나눌 이야기

- 같은 문장을 각자 Triple로 만들었을 때 Entity와 Relation이 어떻게 달라지는지 비교한다.
- 개인 Notion 데이터에서 어떤 항목을 Entity로 볼지 기준을 정해본다.
- 같은 질문을 BM25와 Vector Search로 검색해서 결과를 비교한다.
- 같은 데이터를 Neo4j와 RDF로 각각 표현해서 차이를 확인한다.
- 관계 탐색만으로 충분한 질문과 Ontology 기반 추론이 필요한 질문을 직접 만들어본다.
