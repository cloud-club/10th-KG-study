---
title: RDF 기본
date: 2026-09-27
tags: [rdf, triple, uri, literal, namespace]
status: in-progress
---

## RDF 기본

RDF, Resource Description Framework는
웹의 대상을 식별하고
대상에 대한 사실을 컴퓨터가 처리할 수 있는 관계로 표현하는 표준

ex) 민지는 A회사에 다닌다

⬇️

```
민지 - 소속 ─▶ A회사
```

### 트리플 [주어-술어-목적어]

```
하나의 사실 = 주어 Subject - 술어 Predicate ─▶ 목적어 Object
```

- 주어 Subject : 설명하려는 대상
- 술어 Predicate : 대상의 속성 또는 관계
- 목적어 Object : 관계가 가리키는 대상 또는 값

하나의 대상에 대한 여러 트리플

⬇️

**그래프**

### 리터럴 Literal

목적어가 개체가 아닌 “값”인 경우, 그 값

- 문자열
- 숫자
- 날짜

```
민지 - 이름 ─▶ "김민지" # 문자열 리터럴
민지 - 나이 ─▶ 25 # 숫자 리터럴
민지 - 생일 ─▶ 2002-02-02 # 날짜 리터럴
```

리터럴에는 데이터 타입이나 언어 표시가 가능하다

- ^^ :  리터럴의 데이터 타입 지정
- xsd : XML Schema Definition에서 정의한 타입 접두어
    
    ```
    http://www.w3.org/2001/XMLSchema#integer
    👉🏻 xsd:integer 
    ```
    

```
"25"^^xsd:integer 
"2025-03-01"^^xsd:date
"민지"@ko 
"Minji"@en
```

### URI 식별

이름만 사용하면 동명이인, 이름이 같은 회사 등 구분이 어려운 경우가 발생한다.

이를 방지하기 위해 RDF는 URI로 대상을 식별한다.

```
https://도메인/대상종류/고유식별자

https://example.com/person/minji → 민지라는 대상
https://example.com/company/a    → A회사라는 대상
```

**schema.org**

대상과 속성을 공통된 의미로 표현하기 위해 만든 구조화 데이터 어휘 체계

- 타입 Type : 대상의 종류
    
    ```
    https://schema.org/Person        → 사람
    https://schema.org/Organization  → 조직
    https://schema.org/Article       → 글
    https://schema.org/Event         → 행사
    ```
    
- 속성 Property : 대상이 가진 값 또는 다른 대상과의 관계
    
    ```
    https://schema.org/name          → 이름
    https://schema.org/birthDate     → 생년월일
    https://schema.org/author        → 작성자
    https://schema.org/affiliation   → 소속 조직
    ```
    

하나의 RDF 트리플

```
<https://example.com/person/minji> 주어
    <https://schema.org/affiliation> 술어
    <https://example.com/company/a> . 목적어
```

<aside>
👀

URI를 매번 쓰면 RDF가 너무 길어지는 문제가 있다. 그리고 길어지는 원인 중 하나가 중복되는 부분들이 많다는 것이다.

자주 사용되는 부분을 치환할 수 있는 표현이 있다면 편리하지 않을까?

</aside>

### 네임 스페이스

여러 URI가 공유하는 공통 앞부분

```
@prefix ex: <https://example.com/> . # https://example.com/를 ex:로 치환
@prefix schema: <https://schema.org/> . # https://schema.org/를 schema:로 치환
```

```
<https://example.com/person/minji> -> ex:person/minji
<https://schema.org/affiliation> -> schema:affiliation
```

- @prefix : Turtle의 선언 키워드
- ex: , schema: : 접두어
- https://example.com/ : 네임스페이스 URI

트리플도 짧게 작성 가능하다

```
ex:person/minji schema:affiliation ex:company/a .
```

