---
title: RDFS와 OWL
date: 2026-09-27
tags: [rdfs, owl, schema, ontology, inference]
status: in-progress
---

## RDFS/OWL

RDF : 데이터를 트리플로 표현한다

RDFS : 데이터의 클래스, 속성, 계층 구조를 정의한다 → RDF 데이터를 위한 스키마 어휘

OWL : 더 복잡한 의미, 관계, 제약을 표현한다 → 온톨로지 표현 언어

⬇️

Inference : 명시된 사실 + 정의된 규칙으로 새로운 사실을 도출한다

### RDF/RDFS

RDF의 어휘

: “이 리소스는 어떤 타입이다”라는 기본적인 분류 표현

- rdf:type - 리소스가 어떤 클래스에 속하는지 표현
- rdf:Property - 리소스가 속성(Property)임을 표현

```
철수 ── type ──→ BackendDeveloper
:철수 rdf:type :BackendDeveloper .
```

RDFS의 어휘

: 타입[Class]들 사이의 구조와 계층을 정의

- rdfs:Class - 클래스 정의
- rdfs:subClassOf - 클래스 간 상속/포함 관계
- rdfs:subPropertyOf - 속성 간 상위·하위 관계
- rdfs:domain - 해당 속성의 주어가 속하는 클래스
- rdfs:range - 해당 속성의 목적어가 속하는 클래스

```
개발자 ── subClassOf ──→ 사람  # 개발자는 사람에 상속[포함]
:Developer rdfs:subClassOf :Person .

백엔드개발자 ── subClassOf ──→ 개발자 # 백엔드개발자는 개발자에 상속[포함]
:BackendDeveloper rdfs:subClassOf :Developer .
```

**`rdf:type` vs `rdfs:subClassOf`** 

**`rdf:type`**

인스턴스 → 클래스의 관계

```
철수  ── rdf:type ──→ BackendDeveloper
```

철수라는 개별 개체[인스턴스]가 BackendDeveloper라는 클래스에 속함

**`rdfs:subClassOf`** 

클래스 → 클래스

```
BackendDeveloper ── rdfs:subClassOf ──→ Developer
```

BackendDeveloper라는 클래스가 Developer라는 클래스의 하위 클래스

즉, 모든 BackendDeveloper는 Developer

**전체 연결**

```
철수
 │
 └─ rdf:type → BackendDeveloper
                    │
                    └─ rdfs:subClassOf → Developer
                                              │
                                              └─ rdfs:subClassOf → Person
```

⬇️

추론

```
:철수 rdf:type :Developer .
:철수 rdf:type :Person .
```

<aside>
👀

RDFS는 계층 관계를 표현하는데 특화되어있다.

하지만 아래와 같은 더 자세한 논리조건을 표현하고 싶을 때 RDFS의 한계가 드러난다.

- 부모와 자식은 서로 반대 방향의 관계다.
- A와 B가 같은 사람임을 표현하고 싶다.
</aside>

### OWL

- owl:sameAs - 동일한 개체
- owl:equivalentClass - 두 클래스가 동등함
- owl:differentFrom - 서로 다른 개체
- owl:inverseOf - 역관계
- owl:SymmetricProperty - 대칭 관계
- owl:TransitiveProperty - 추이 관계

OWL에서는 
"어떤 조건을 만족하면 이 클래스에 속한다”라는 
정의를 만들 수 있다

```
Parent
= Person이면서
  hasChild 관계를 최소 1개 이상 가진 존재
```

1) Person이다.

2) 최소 한 명의 child가 있다.

```
:Parent owl:equivalentClass [           # Parent 클래스는 뒤의 조건을 만족하는 클래스와 동등
    rdf:type owl:Class ;                # 뒤의 [ ... ]가 하나의 OWL 클래스
    owl:intersectionOf (                # 아래 조건들을 모두 만족해야 함 (AND)
        :Person                         # 조건 1 : Person 클래스에 속해야 함
        [
            rdf:type owl:Restriction ;  # 조건 2 : Property에 대한 제약(Restriction)으로 정의
            owl:onProperty :hasChild ;  # 제약 적용
            owl:minCardinality 1        # hasChild 관계가 최소 1개 이상 존재해야 함
        ]
    )                                   # intersectionOf 조건 끝
] .                                     # Parent 클래스 정의 끝
```

```
Parent
  │
  └─ equivalentClass
           ↓
        [조건]
           │
           ├─ Person
           │
           │       AND
           │
           └─ hasChild 최소 1개
```

### 스키마 vs 온톨로지

#### 스키마 Schema

데이터의 구조를 정의한 규칙

어떤 데이터가 존재하고,
어떤 속성을 가지며,
어떤 형태로 저장되는가?

```
Developer라는 타입이 있다.
Developer에는 name이라는 속성이 있다.
name의 값은 문자열이다.
company의 값은 Company 타입이다.
```

#### 온톨로지 Ontology

도메인에 존재하는 개념과 관게, 그 의미 정의

어떤 개념이 존재하고, 
개념들이 서로 **어떤 관계를 가지며, 
그 관계가 무엇을 의미하는가?**

```
BackendDeveloper는 Developer다.
Developer는 Person이다.
hasParent와 hasChild는 역관계다.
Developer와 Company는 서로 다른 종류의 개념이다.
```

#### ** OWL ≠ Ontology

```
Ontology = 무엇을 정의할 것인가
OWL      = 그것을 어떻게 표현할 것인가
```

