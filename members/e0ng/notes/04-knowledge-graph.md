---
title: 지식 그래프의 변천사와 RDF 기본
date: 2026-09-25
tags: [knowledge-graph, semantic-web, rdf, owl, linked-data, graphrag, ontology]
status: in-progress
---

## 지식 그래프의 변천사

시맨틱 웹 → RDF/OWL → 링크드 데이터 → Google Knowledge Graph → 기업 KG → GraphRAG → Palantir Ontology

### 시맨틱 웹 Semantic Web

“의미론적 웹”

기존의 웹 : 데이터 제공 → 사람이 해석해 의미 파악

시맨틱 웹 : 기계가 데이터 의미 이해, 관계 인식 후 연결된 정보 제공

#### HTML에서의 시맨틱

```html
<p>민지는 A회사에 다닌다.</p>
```

```html
<p vocab="https://schema.org/" typeof="Person">
  <span property="name">민지</span>는
  <span property="affiliation" typeof="Organization">
    <span property="name">A회사</span>
  </span>에 다닌다.
</p>
```

- `vocab`: 사용할 어휘 체계
- `typeof`: 대상의 종류 지정
- `property`: 대상이 가진 속성 또는 다른 대상과의 관계 지정

<aside>
👀

웹사이트마다 `사람`, `회사`, `소속`을 서로 다른 형식으로 표현한다면 컴퓨터가 공통된 의미로 처리하기 어렵다.

그렇다면 데이터의 의미와 관계를 모두가 공통된 형식으로 표현할 수는 없을까?

</aside>

### RDF와 OWL 표준

**RDF**

Resource 자원 + Description 서술 + Framework 형식

```
주어(Subject) ── 술어(Predicate) ──▶ 목적어(Object)
```

> 사실을 “트리플(SPO)”로 표현한다.
> 
- Subject 주어 : 설명하려는 대상
- Predicate 술어 : 속성 또는 관계
- Object 목적어 : 관계가 가리키는 대상

** 하나의 대상에 여러 트리플 연결 가능

```
민지 ── 종류 ──▶ 사람
민지 ── 소속 ──▶ A회사
민지 ── 나이 ──▶ 25
A회사 ── 종류 ──▶ 회사
```

이름이 같은 대상을 혼동하지 않도록 URI로 식별

```
주어 URI
<https://example.com/person/minji>

술어 URI
<https://schema.org/affiliation>

목적어 URI
<https://example.com/company/a>
```

**+ RDFS**

RDF Schema

> **기본적인 클래스 구조를 정의한다.**
> 

```
RDF 사실
민지 ──종류──▶ 사람

RDFS 정의
사람 ──하위 클래스──▶ 생명체

            ↓ 추론

민지 ──종류──▶ 생명체
```

** OWL은 더 정교한 의미와 제약을 표현하는 언어

**OWL**

Web 웹 + Ontology 개념-관계를 체계적으로 정의한 지식 체계 + Language 언어

> 개념과 규칙을 정의한다.
> 

```
근무함 ──역관계──▶ 고용함
         +
민지 ──근무함──▶ A회사
         ↓
A회사 ──고용함──▶ 민지
```

**RDF와 OWL의 관계** 

1) RDF는 **개별 사실을 트리플로 표현**

```
├─ 민지는 A회사에 근무한다
└─ 민지는 프로젝트를 이끈다
```

2) OWL은 RDF로 표현된 대상의 **개념·관계·규칙을 정의**

```
├─ 근무함과 고용함은 역관계다
└─ 프로젝트를 이끄는 사람은 프로젝트 리더다
```

3) 추론 : **RDF로 표현한 사실에 OWL로 정의한 규칙을 적용하여, 직접 저장하지 않은 사실을 도출하는 과정**

```
├─ A회사는 민지를 고용한다
└─ 민지는 프로젝트 리더다
```

<aside>
👀

각 기관이 RDF 데이터를 자기 서버에 따로 저장하기만 한다면 데이터의 형식은 같아도 서로 연결되지는 않는다. 데이터가 같은 대상을 설명하더라도 이를 연결하지 않으면 웹 전체의 지식으로 활용하기 어렵다.

서로 다른 데이터셋의 같은 대상을 연결할 수는 없을까?

</aside>

### 링크드 데이터와 DBpedia·Wikidata

**링크드 데이터 Linked Data**

RDF로 표현한 데이터를 웹에 공개하고,
URI를 이용해 서로 다른 데이터셋의 대상을 연결하는 방식

```
시맨틱 웹
└─ 기계가 웹 데이터의 의미와 관계를 처리한다
        ↓

RDF·OWL
└─ 의미와 관계를 표현한다
        ↓

링크드 데이터
└─ 표현한 데이터를 웹에 공개하고 다른 데이터와 연결한다
```

링크드 데이터의 기본 원칙

- 각 대상을 URI로 식별한다.
- HTTP URI를 사용해 웹에서 접근할 수 있게 한다.
- URI에 접근하면 RDF 형식의 정보를 제공한다.
- 다른 데이터의 URI를 연결해 추가 정보를 탐색할 수 있게 한다.

ex) 두 데이터셋이 같은 사람을 서로 다른 이름으로 저장한 경우

```
데이터셋 A
<https://example.kr/person/tim>
    이름 → "팀 버너스리"

데이터셋 B
<https://example.org/people/tbl>
    이름 → "Tim Berners-Lee"
```

두 URI가 동일한 대상을 가리킨다고 연결

```
<https://example.kr/person/tim>
    owl:sameAs
<https://example.org/people/tbl>
```

```
"팀 버너스리"
       ↑ 이름
데이터셋 A의 URI
       │
       │ owl:sameAs
       ▼
데이터셋 B의 URI
       ↓ 이름
"Tim Berners-Lee"
```

➡️ 데이터셋 A의 정보와 데이터셋 B의 정보를 같은 인물에 관한 지식으로 함께 활용 가능

**DBpedia**

위키백과 문서의 구조화된 정보를 추출해 RDF 형태로 공개한 지식 베이스

!스크린샷 2026-09-23 오후 9.06.12.png

 ⬇️ 구조화

```
홍길동 ──종류──▶ 사람
홍길동 ──출생 연도──▶ 1443년
홍길동 ──사망 연도──▶ 1510년
홍길동 ──성별──▶ 남성
홍길동 ──국적──▶ 조선
홍길동 ──직업──▶ 도적
```

```
<홍길동_URI> <출생연도_URI> "1443"
<홍길동_URI> <사망연도_URI> "1510"
<홍길동_URI> <국적_URI> <조선_URI>
<홍길동_URI> <직업_URI> <도적_URI>
```

**Wikidata**

사람들이 직접 구조화된 항목과 속성을 공동으로 편집하는 지식 베이스

- 대상을 고유한 항목 ID로 식별
- 속성으로 다른 대상이나 값을 연결

```
Q18964248: 홍길동
├─ 종류 ──▶ 사람
├─ 성별 ──▶ 남성
├─ 국적 ──▶ Q28179: 조선
└─ 직업 ──▶ 의적
```

> DBpedia는 위키백과 문서에서 구조화된 데이터를 추출
Wikidata는 항목·속성·값을 구조화된 데이터로 직접 작성하고 공동 관리
> 

### Google Knowledge Graph

**Things, not strings**

문자열이 아니라 현실의 개체 간 관계를 이해하여 검색에 활용하는 지식 그래프

**Knowledge Graph 지식 그래프**

개체 간 관계와 속성을 이해하여 그래프 형태로 표현한 지식 구조

- Entity 개체 : 독립적으로 식별할 수 있는 대상
- Property 속성 : 개체가 가진 값
- Relationship 관계 : 개체와 다른 개체의 연결

```
        ┌─ 이름 ─ "홍길동"
[홍길동]  ├─ 출생 연도 ─ 1440          
Entity 	└─ 성별 ─ "남성"
    │
    ├─ 국적 Relationship ──▶ [조선] 
    │                       Entity
    │
    └─ 등장 작품 Relationship ──▶ [홍길동전]
                                 Entity
```

기존 검색의 문제점

```
검색어: 홍길동

문자열 중심 검색
└─ “홍길동”이라는 문자열이 포함된 문서 검색
```

조선시대 인물, 홍길동전의 등장인물 등 홍길동이 가리킬 수 있는 대상은 여러 개

⬇️

Google Knowledge Graph는 고유하게 식별되는 개체로 해석

1) 올바른 개체 식별 

2) 식별된 개체의 핵심 정보 요약

3) 관련 개체 탐색

### 기업 Knowledge Graph

기업의 여러 시스템에 흩어진 데이터를 업무상의 개체·속성·관계를 중심으로 연결한 지식 그래프

- Google Knowledge Graph : 웹의 사람, 장소 등을 연결
- 기업 Knowledge Graph : 조직 내부의 고객, 제품, 주문 등을 연결

```
[민지]
  ├─주문함──▶ [주문 1001]
  │              ├─상태 ─ "배송 지연"
  │              ├─포함함 ─ [노트북]
  │              └─배송 ─ [배송 3001]
  │
  └─문의함──▶ [문의 5001]
                  ├─내용 ─ "배송이 언제 도착하나요?"
                  └─관련 제품 ─ [노트북]
```

⬇️ 여러 시스템의 정보를 함께 봐야 하는 질문에 답변이 가능해진다.

```
배송이 지연된 주문을 한 고객은 누구인가?

배송 지연
    ◀──상태── 주문
                 ◀──주문함── 고객
```

### LLM 시대의 GraphRAG

개체와 관계로 구성된 그래프를 함께 탐색해 LLM의 Context를 만드는 RAG 방식

**RAG의 한계**

RAG는 특정 문서 하나에서 근거를 찾는 질문에 적합

- 벡터 검색 : 질문과 각 청크의 의미적 유사도를 개별적으로 비교
→ 필요한 청크를 모두 가져오지 못할 가능성 존재

여러 문서에 흩어진 관계 연결에는 한계 존재

**GraphRAG**
문서에서 Entity와 Relationship을 추출 또는 기존 Knowledge Graph를 사용

```
                       ┌──── 근무함 ─────▶ [A회사]
                       │  Relationship    Entity
[부산 여행] ◀─── 함께 감 ─── [민지]
 Entity  Relationship   Entity
     ▲
     │
     ├──── 함께 감 ────── [수현] ──근무함──▶ [B회사]
     │  Relationship    Entity           Entity
     └──── 함께 감 ────── [지훈] ──근무함──▶ [A회사]
        Relationship    Entity           Entity

```

1) 그래프 구성

```
원본 문서
 ↓ 청킹
Text Chunks
 ↓ 개체·관계 추출
Entity + Relationship
 ↓
Knowledge Graph 저장
```

2) 그래프 검색

```
사용자 질문
 ↓
질문에 등장한 Entity 식별
 ↓
관련 Entity와 Relationship 탐색
 ↓
연결된 원본 청크 검색
```

3) Context 조립과 답변

```
그래프에서 찾은 관계
        +
관계의 근거가 된 원본 청크
        ↓
LLM Context 조립
        ↓
근거 기반 답변 생성
```

예시) “부산에 같이 간 사람들 중 같은 회사에 다니는 사람은?”

- RAG

```
청크 1: 부산은 민지, 수현, 지훈이랑 같이 갔다.
청크 2: 민지는 A회사에 다닌다.
청크 3: 수현은 B회사에 다닌다.
청크 4: 지훈은 A회사에 다닌다.
```

- GraphRAG

```
[부산 여행]
     ▲
     ├──함께 감── [민지] ──근무함──▶ [A회사]
     ├──함께 감── [수현] ──근무함──▶ [B회사]
     └──함께 감── [지훈] ──근무함──▶ [A회사]
                        ↓
                 회사 Entity 비교
                        ↓
              [민지]와 [지훈] → [A회사]
```

### Palantir Ontology

Knowledge Graph [Object + Property + Relationship] + Action

기업의 데이터를 실제 업무 대상과 관계로 연결하고,
조회뿐 아니라 실제 업무 행동까지 수행할 수 있게 만든 운영 계층

- Object : 현실의 업무 대상
** 지식 그래프의 Entity와 대응
- Property : Object가 가진 상태나 값
- Relationship[Link} : 서로 다른 Object 간의 연결
- Action : 사용자가 Object의 상태를 변경하거나 실제 업무를 수행 가능하게 함

```
실행 전
배송 3001 ──담당자──▶ 지훈

Action
배송 담당자를 수현으로 변경

실행 후
배송 3001 ──담당자──▶ 수현
```

**실제 업무 대상과 관계로 연결**

흩어져 있는 기존 데이터들을 고객, 주문, 배송과 같은 실제 업무 대상과 연결한다.

```
고객 데이터 ───── CRM
주문 데이터 ───── 주문 DB
배송 데이터 ───── 물류 시스템
직원 데이터 ───── 인사 시스템
```

⬇️ Ontology 맵핑

```
CRM 데이터 ────────▶ [고객 Object]
주문 DB ───────────▶ [주문 Object]
물류 시스템 ───────▶ [배송 Object]
인사 시스템 ───────▶ [직원 Object]
```

⬇️ Link : Object 간 연결

```
고객 ──주문함──▶ 주문 ──배송됨──▶ 배송 ──담당자──▶ 직원
```

ex) 

```
customers 테이블의 101번 행
        ↓ 매핑
[고객: 민지]

orders 테이블의 3001번 행
        ↓ 매핑
[주문: 3001]

        ↓ Link로 연결

[고객: 민지] ──주문함──▶ [주문: 3001]
```

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
- `https://example.com/` : 네임스페이스 URI

트리플도 짧게 작성 가능하다

```
ex:person/minji schema:affiliation ex:company/a .
```

