---
title: 프로퍼티 그래프와 RDF 트리플 스토어
date: 2026-09-27
tags: [property-graph, rdf, triple-store, neo4j]
status: in-progress
---

## 프로퍼티 그래프 vs RDF 트리플 스토어

!image.png

### 프로퍼티 그래프 Property Graph

노드와 관계 모두에 속성을 저장할 수 있는 그래프 모델

애플리케이션에서 연결된 데이터를 편리하게 저장하고 탐색하는 것에 초점을 둔다

- 현실의 개체(Entity) : Node
- 개체 사이의 관계 : Edge/Relationship로 연결

```
(철수:Person)
 ├─ name = "철수"
 └─ age = 25

        │
        │ WORKS_FOR
        │ since = 2024
        ↓

(네이버:Company)
 └─ name = "네이버"
```

`age`, `since` 같은 값들이 별도의 노드가 아니라 해당 노드/관계에 붙어 있는 Property이다.

#### Neo4j

Property Graph 모델을 사용하는 대표적인 그래프 데이터베이스

Node, Relationship, Property를 저장하고 **Cypher**를 이용해 그래프를 탐색·질의한다.

** Cypher : Neo4j에서 그래프 데이터를 조회하고 조작할 때 사용하는 질의 언어

```sql
MATCH   : 이런 그래프 패턴을 찾아라
(person:Person) : Person 노드
[:WORKS_FOR]    : WORKS_FOR 관계
(company:Company) : Company 노드

WHERE   : 그중 person.name이 "철수"인 것
RETURN  : 연결된 company를 반환
```

### RDF Graph

데이터의 의미를 표준화하여 표현하고, 서로 다른 지식을 연결하는 것에 초점을 둔다

** SPARQL 질의 언어 사용

- 기본적으로 **모든 사실을** Triple로 표현
- 하나의 개체에 대한 정보도 각각 독립적인 Triple로 표현

```
                  Person
                    ↑
                 rdf:type
                    │
25 ←── age ─────── 철수
                    │
                 worksFor
                    ↓
                  네이버
                    │
                 rdf:type
                    ↓
                 Company
```

Property Graph에서는 `age = 25` 같은 값을 **노드의 Property**로 붙일 수 있지만, 
RDF에서는 `철수 - age - 25` 역시 **하나의 Triple**로 표현된다

> 
> 
> 
> **Property Graph :** 개체와 관계를 중심으로 데이터를 직접 모델링
> **RDF :** 사실과 의미를 Triple 단위로 표현하고 연결
> 

