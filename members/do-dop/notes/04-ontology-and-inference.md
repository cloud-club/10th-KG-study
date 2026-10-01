---
title: "온톨로지와 추론: 저장된 사실에서 새로운 지식으로"
date: 2026-09-24
tags: [rdf, turtle, rdfs, owl, ontology, inference, tbox, abox]
status: complete
---

# 온톨로지와 추론: 저장된 사실에서 새로운 지식으로

이 문서는 RDF, Turtle, RDFS, OWL과 온톨로지의 역할을 구분하고, 저장된 사실에서 새로운 사실을 도출하는 추론이 무엇인지 설명한다.

역사적 배경과 Linked Data의 흐름은 [시맨틱 웹에서 지식그래프까지](04-semantic-web-to-knowledge-graph.md)에서 먼저 확인할 수 있다.

## 먼저 구분해야 할 개념

| 개념 | 한 줄 정의 | 담당하는 역할 |
|---|---|---|
| Knowledge Graph | 개체와 관계로 표현한 지식 | 실제 사실을 연결하고 탐색한다. |
| RDF | 주어-서술어-목적어로 사실을 표현하는 데이터 모델 | 그래프의 공통 표현 규칙을 제공한다. |
| Turtle | RDF를 사람이 읽기 쉽게 기록하는 문법 | RDF 그래프를 텍스트 파일로 저장한다. |
| RDFS | 클래스·속성·계층을 정의하는 기본 어휘 | 데이터의 기본 의미 구조를 정의한다. |
| OWL | 더 풍부한 논리와 제약을 표현하는 온톨로지 언어 | 역관계·동치·대칭성 등의 공리를 정의한다. |
| Ontology | 도메인의 개념·관계·규칙을 명시한 지식 체계 | 그래프에 사용되는 말의 의미를 정의한다. |
| Reasoning | 사실과 규칙에서 새로운 사실을 도출하는 과정 | 명시되지 않은 지식을 얻는다. |

이 개념들은 대체 관계가 아니다. RDF로 실제 사실과 온톨로지를 함께 표현할 수 있고, 추론기는 그 둘을 이용해 새로운 사실을 도출한다.

    실제 사실 + 개념과 규칙 → 추론 → 새로 도출된 사실
      ABox        TBox

## 1. RDF는 데이터 모델이고 Turtle은 작성 문법이다

RDF 그래프의 기본 단위는 트리플이다.

    Subject ──Predicate──▶ Object
    생텍쥐페리 ──저술했다──▶ 어린 왕자

| 구성요소 | 의미 | 가능한 값 |
|---|---|---|
| Subject | 설명하려는 대상 | IRI 또는 Blank Node |
| Predicate | 속성이나 관계 | IRI |
| Object | 연결된 대상 또는 값 | IRI, Blank Node 또는 Literal |

Turtle은 이 RDF 트리플을 적는 여러 직렬화 문법 중 하나다.

```turtle
@prefix ex: <https://example.org/> .

ex:SaintExupery ex:wrote ex:TheLittlePrince .
ex:TheLittlePrince ex:publishedYear "1943" .
```

RDF는 그래프의 의미 구조이고, Turtle은 그 구조를 파일로 기록하는 표기법이다. 같은 RDF 그래프를 JSON-LD나 RDF/XML로도 표현할 수 있다.

## 2. RDF만으로는 개념의 의미가 충분하지 않다

다음 트리플은 하나의 사실을 표현한다.

```turtle
ex:SaintExupery ex:wrote ex:TheLittlePrince .
```

그러나 이 트리플만으로는 다음 내용을 알 수 없다.

- `SaintExupery`는 사람인가?
- `TheLittlePrince`는 책인가?
- `wrote`의 주어와 목적어에는 어떤 종류의 대상이 와야 하는가?
- `writtenBy`는 `wrote`의 반대 방향 관계인가?

이처럼 **어떤 개념이 존재하며 관계가 무엇을 뜻하는지** 정의하는 것이 온톨로지의 역할이다.

## 3. RDFS는 기본적인 클래스와 계층을 정의한다

RDFS는 클래스, 속성, 상하위 계층, 속성의 domain과 range를 정의하는 기본 어휘를 제공한다.

```turtle
ex:Book rdfs:subClassOf ex:CreativeWork .
ex:Author rdfs:subClassOf ex:Person .

ex:wrote rdfs:domain ex:Person ;
         rdfs:range ex:Book .
```

- `subClassOf`: 한 클래스가 다른 클래스의 하위 개념임을 나타낸다.
- `domain`: 해당 속성의 주어가 속할 클래스를 나타낸다.
- `range`: 해당 속성의 목적어가 속할 클래스를 나타낸다.

여기서 domain과 range는 입력값을 차단하는 데이터베이스 검증 규칙이라기보다 **추론을 위한 의미 선언**이다. `A ex:wrote B`가 있으면 RDFS 추론기는 A를 `Person`, B를 `Book`으로 추론할 수 있다. 잘못된 데이터를 검사하려면 SHACL 같은 별도의 검증 언어가 더 적합하다.

## 4. OWL은 더 풍부한 공리를 표현한다

공리(axiom)는 온톨로지 안에서 참인 것으로 두는 개념과 관계의 규칙이다. OWL은 RDFS보다 풍부한 공리를 표현한다.

```turtle
ex:writtenBy owl:inverseOf ex:wrote .
ex:hasSibling a owl:SymmetricProperty .
ex:locatedIn a owl:TransitiveProperty .
```

각 선언의 의미는 다음과 같다.

- `inverseOf`: 두 속성이 서로 반대 방향의 관계다.
- `SymmetricProperty`: A와 B의 관계가 성립하면 B와 A의 관계도 성립한다.
- `TransitiveProperty`: A→B이고 B→C이면 A→C도 성립한다.

예를 들어 다음 사실과 역관계 공리가 함께 있다면,

```turtle
ex:SaintExupery ex:wrote ex:TheLittlePrince .
ex:writtenBy owl:inverseOf ex:wrote .
```

추론기는 다음 사실을 도출할 수 있다.

```turtle
ex:TheLittlePrince ex:writtenBy ex:SaintExupery .
```

## 5. 스키마와 온톨로지는 무엇이 다른가

스키마는 주로 데이터가 가져야 할 구조를 정의한다.

    Book에는 title과 publishedYear가 있다.

온톨로지는 개념과 관계의 의미, 개념 사이의 논리적 규칙까지 표현한다.

    Book은 CreativeWork의 하위 개념이다.
    writtenBy는 wrote의 역관계다.
    wrote의 주어는 Person이고 목적어는 Book이다.

둘의 경계가 언제나 명확한 것은 아니다. 이 문서에서는 필드와 자료형만 정하면 스키마, 클래스 계층과 관계의 의미 및 추론 규칙까지 정하면 온톨로지라고 구분한다.

## 6. TBox와 ABox

온톨로지 기반 지식그래프는 설명을 위해 TBox와 ABox로 나눠 볼 수 있다.

### TBox: 개념과 규칙

TBox(Terminological Box)는 어떤 종류가 존재하고 그 관계가 무엇을 뜻하는지 정의한다.

```turtle
ex:Author rdfs:subClassOf ex:Person .
ex:wrote rdfs:domain ex:Person ;
         rdfs:range ex:Book .
```

### ABox: 개별 사실

ABox(Assertional Box)는 실제 개체에 관한 사실을 기록한다.

```turtle
ex:SaintExupery a ex:Author ;
    ex:wrote ex:TheLittlePrince .
ex:TheLittlePrince a ex:Book .
```

TBox와 ABox는 개념적으로 구분할 뿐, 반드시 서로 다른 데이터베이스에 저장할 필요는 없다. 같은 RDF 그래프나 트리플 스토어 안에 함께 둘 수 있다.

## 7. 추론은 그래프 탐색과 다르다

그래프 탐색은 이미 저장된 관계를 따라가며 연결된 대상을 찾는다.

    생텍쥐페리 ──wrote──▶ 어린 왕자
         저장된 관계를 조회

추론은 사실과 공리를 결합해 저장하지 않은 사실을 도출한다.

    Author subClassOf Person
    SaintExupery rdf:type Author
    ─────────────────────────────
    SaintExupery rdf:type Person

| 작업 | 핵심 질문 |
|---|---|
| 탐색 | 어떤 노드가 어떤 경로로 연결되어 있는가? |
| 추론 | 기존 사실과 규칙으로 무엇을 새로 알 수 있는가? |

실제 온톨로지 기반 KG에서는 두 작업을 함께 사용한다.

## 8. 1차 논리는 추론의 사고 틀이다

1차 논리(First-Order Logic)는 개체, 속성, 관계와 규칙을 형식적으로 표현하는 논리 체계다.

| 기호 | 의미 |
|---|---|
| `∀` | 모든 |
| `∃` | 적어도 하나 존재 |
| `→` | 앞이 참이면 뒤도 참 |
| `∧` | 그리고 |
| `¬` | 아니다 |

“모든 작가는 사람이다”는 다음과 같이 생각할 수 있다.

    ∀x (Author(x) → Person(x))

그리고 `Author(SaintExupery)`가 주어지면 `Person(SaintExupery)`를 도출할 수 있다. OWL은 이러한 논리적 의미를 웹 환경에서 계산 가능한 범위로 표현하도록 설계된 언어다.

## 9. OWL만으로 표현하기 어려운 규칙

같은 부모를 가진 두 사람이 형제자매라는 규칙을 생각해보자.

    A의 부모가 P이고 B의 부모도 P이며 A와 B가 다르면
    → A와 B는 형제자매다.

`hasSibling`을 대칭 속성으로 선언하는 것만으로 이 관계가 새로 생성되지는 않는다. 대칭성은 이미 `A hasSibling B`가 있을 때 반대 방향을 도출할 뿐이다.

이처럼 조건과 결론으로 구성된 규칙은 SWRL이나 별도의 규칙 엔진을 사용할 수 있다. 다만 최단 경로, 복잡한 집계와 산술 계산까지 모두 OWL 추론으로 해결하려고 해서는 안 된다.

## 10. 개방 세계 가정

RDF·OWL의 일반적인 의미론은 개방 세계 가정(Open World Assumption)을 따른다.

> 그래프에 어떤 사실이 없다는 이유만으로 그 사실이 거짓이라고 결론 내리지 않는다.

예를 들어 어떤 책에 `writtenBy` 관계가 기록되지 않았다고 해서 그 책에 저자가 없다고 단정할 수 없다. 아직 조사하거나 입력하지 않았을 수도 있다.

따라서 질의 결과에 저자가 나오지 않았다는 것은 다음 뜻으로 해석해야 한다.

> 현재 그래프에서 해당 책의 저자 정보를 찾지 못했다.

이는 “그 책에는 저자가 없다”는 단정과 다르다. 화면과 질의 결과에서도 `저자 없음`보다 `저자 정보 미등록` 또는 `확인 필요`라는 표현이 더 정확하다.

## 핵심 정리

1. RDF는 데이터 모델이고 Turtle은 RDF를 기록하는 문법이다.
2. RDFS와 OWL은 클래스·속성·공리를 정의하는 데 사용한다.
3. TBox는 개념과 규칙, ABox는 실제 개체의 사실이다.
4. 탐색은 저장된 관계를 따라가고, 추론은 규칙으로 새 사실을 만든다.
5. 사실이 없다는 것은 거짓이 아니라 아직 모른다는 뜻일 수 있다.

## 참고자료

- [RDF 1.1 Primer — W3C](https://www.w3.org/TR/rdf11-primer/)
- [RDF Schema 1.1 — W3C](https://www.w3.org/TR/rdf-schema/)
- [OWL 2 Web Ontology Language Primer — W3C](https://www.w3.org/TR/owl2-primer/)
- [OWL 2 Profiles — W3C](https://www.w3.org/TR/owl2-profiles/)
- [SHACL — W3C](https://www.w3.org/TR/shacl/)
- [SWRL Submission — W3C](https://www.w3.org/Submission/SWRL/)
