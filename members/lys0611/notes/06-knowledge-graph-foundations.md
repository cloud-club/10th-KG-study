---
title: 지식 그래프의 배경 — 온톨로지 변천사와 방법론
date: 2026-09-30
tags: [knowledge-graph, semantic-web, rdf, rdfs, owl, sparql, linked-data, wikidata, property-graph, ontology]
status: done
---

# W4. 지식 그래프의 배경 — 온톨로지 변천사와 방법론

> **핵심 정리**: 검색은 문서를 찾는다. 사실과 관계를 찾으려면 ① 사실을 **식별자로 연결된 그래프**로 저장하고, ② **패턴 매칭 질의**로 관계를 찾고, ③ **온톨로지**로 개념의 의미와 추론 규칙을 정의해야 한다.

## 0. RAG에서 Knowledge Graph로 넘어가는 이유

> **RAG** : 관련 **텍스트를 찾는다**.  
> **KG** : 엔티티와 엔티티 사이의 **관계**를 명시적으로 저장하고 따라간다.

| 구분 | RAG/검색 | Knowledge Graph |
| --- | --- | --- |
| 찾는 것 | 관련 **문서, 청크** | **엔티티, 사실, 관계** |
| 기본 질문 | “관련 내용이 어느 문서에 있지?” | “A와 B는 어떤 관계이며 어떤 경로로 연결되지?” |
| 잘하는 것 | 의미적으로 관련된 텍스트 검색 | 관계 탐색, 다중 홉 질의 |
| 대표 문제 | 필요한 사실이 여러 문서에 흩어지면 검색·추론 실패 가능 | 그래프 구축·엔티티 식별이 필요 |

예를 들어 `“부산 같이 간 사람들 중 같은 회사 다니는 사람?”`은 하나의 문서를 찾는 문제가 아니라  
`나 → 부산 여행 → 사람 → 재직회사`처럼 **여러 관계를 연속해서 따라가는 multi-hop 문제**다.

## 1. 지식 그래프의 개념 및 활용 발전 흐름

| 흐름 | 의미 |
| --- | --- |
| **Semantic Web**<br>(비전) | 출발점인 **비전**: 웹의 정보를 기계도 의미적으로 이해, 연결할 수 있게 하자 |
| ↓ | 그 비전을 실제 데이터로 표현할 **기술이 필요** |
| **RDF / RDFS / OWL / SPARQL**<br>(표현 기술) | 사실 표현(RDF), 의미 구조(RDFS/OWL), 질의(SPARQL)를 위한 **표준 기술** |
| ↓ | 한 데이터셋 내부가 아니라 **웹의 서로 다른 데이터도 연결해보자** |
| **Linked Data**<br>(데이터 연결 방법) | 공통 식별자를 이용해 여러 데이터셋을 서로 연결하는 **원칙·방법론** |
| ↓ | 이 아이디어를 실제 대규모 데이터에 적용 |
| **DBpedia / Wikidata**<br>(실제 지식 데이터) | 사람·장소·사건 등의 지식을 실제로 구조화한 **공개 지식베이스 사례** |
| ↓ | 이런 구조를 검색·추천·서비스에 적극 활용 |
| **Knowledge Graph**<br>(서비스 활용) | 실세계 entity와 관계를 그래프로 관리·활용하는 **실용적 패러다임** |
| ↓ | 공개 웹뿐 아니라 회사 내부 데이터에도 적용 |
| **기업 KG**<br>(기업 활용) | 고객·직원·제품·설비·문서 등의 관계를 조직 내부에서 관리 |
| ↓ | LLM 등장 후 텍스트 이해 능력과 그래프의 관계 구조를 결합 |
| **LLM + GraphRAG**<br>(LLM과 결합) | 그래프의 entity·relationship을 **LLM 검색과 컨텍스트 구성에 활용** |

1. **Semantic Web:** 웹에 있는 데이터를 기계가 의미적으로 해석·연결할 수 있게 만들자는 비전
   - **한계**: 비전은 있었지만 **기계가 읽을 데이터를 표현할 표준이 필요**
   
     → RDF(데이터 표현), RDFS/OWL(의미·온톨로지), SPARQL(질의) 같은 표준이 발전

2. **RDF:** 사실을 **triple**로 표현하는 기본 데이터 모델
   - **한계**: 사실은 표현함 → **클래스·계층·관계의 의미가 부족**

3. **RDFS/OWL:** RDF에 클래스, 계층, 관계의 의미와 논리를 추가
   - **한계**: 의미와 규칙까지 표현함 → **그래프를 실제로 질의할 방법이 필요**

4. **SPARQL:** RDF 그래프를 질의하는 언어
   - SQL이 테이블을 질의한다면 SPARQL은 RDF graph를 질의
   - 그래프를 질의할 수 있음 → **서로 다른 데이터셋끼리도 연결하고 싶음**

5. **Linked Data:** 서로 다른 데이터셋의 entity를 **웹상의 식별자와 링크로 연결**해 하나의 “Web of Data”처럼 탐색
   - **Linked Data 4원칙**: 사물에 URI를 붙이고 / HTTP URI로 조회 가능하게 하고 / 조회하면 표준(RDF·SPARQL)으로 정보를 주고 / 다른 URI로 연결한다
   
     → "**전역 온톨로지를 먼저 완성**"에서 "**데이터를 먼저 링크**"로 노선 수정
   - **한계**: 웹의 데이터들을 연결 → **실제 대규모 구조화 지식 데이터가 필요**

6. **DBpedia/Wikidata**
   - **DBpedia:** Wikipedia의 구조화된 정보를 추출해 RDF/Linked Data 형태의 공개 Knowledge Graph로 만든 프로젝트
   - **Wikidata:** 사람·장소·개념 등을 Item으로 만들고 Property를 통해 관계를 표현하는 Wikimedia의 공동 지식베이스
   - **한계**: 실제 지식 그래프 데이터 등장 → **검색·추천·기업 문제에 직접 활용하고 싶음**

7. **Knowledge Graph:** 현실 세계의 entity와 relationship을 그래프 구조로 관리
   - **한계**: entity·relation 기반 서비스 가능 → **기업 내부 데이터와 비정형 문서까지 활용하고 싶음**

8. **Enterprise KG + LLM**: 공개 웹 전체가 아니라 **특정 도메인**을 그래프로 모델링
   - **한계**: 구조화 관계와 LLM을 함께 활용 → **기존 RAG가 어려워하는 다중 관계·전체 데이터 질문을 개선**

9. **GraphRAG:** 문서에서 entity·relationship을 추출해 graph를 만들고, **그래프 구조까지 검색 컨텍스트에 활용**
   - **텍스트 검색 + 그래프 관계 탐색을 결합**

## **2. RDF 기본: Triple, IRI, Literal, Namespace**

### Triple

- RDF의 기본 단위: **Subject – Predicate – Object**
- 사실 하나 = 트리플 하나, 그래프 = 트리플의 집합
- 예: `김@@ ─ 근무 → AWS`

### URI/IRI

- entity와 관계를 이름이 아닌 **고유한 식별자**로 구분
- RDF 1.1부터 IRI를 사용하며 URI보다 더 넓은 문자 집합을 지원
- 같은 entity에 같은 IRI를 사용하면 `"서울 / Seoul / 서울시"` 같은 표현 차이와 관계없이 연결할 수 있음
- 이름 없는 임시 자원은 **Blank Node** 사용

### Literal

- 문자열·숫자·날짜 같은 **값**이며 목적어에 사용
- 예: `"42"^^xsd:integer`, `"부산"@ko`, `"2025-06-14"^^xsd:date`
- Property 그래프의 속성값에 가까움

### Namespace

- 긴 IRI를 `접두어:로컬이름` 형태로 축약
- 예: `http://www.wikidata.org/entity/Q8684` → `wd:Q8684`

### 직렬화

- 같은 RDF 그래프를 파일로 표현하는 방식: **Turtle, N-Triples, JSON-LD, RDF/XML**
- Turtle은 사람이 읽기 편하고, JSON-LD는 웹 환경에서 사용하기 편함

## 3. RDFS/OWL — 클래스·속성·계층·제약

### 핵심 개념

- **Class:** 같은 종류의 entity를 묶는 개념 (예: `김철수 rdf:type 사람)`
- **Property:** entity 사이의 속성, 관계
- **계층:** `subClassOf`, `subPropertyOf`로 상하 관계 표현
- **domain/range:** property의 주어와 목적어가 어떤 클래스인지 의미를 정의
- **OWL:** RDFS보다 복잡한 관계, 제약을 표현
  - 역관계, 이행 관계, 대칭 관계, `sameAs`, 서로소 클래스, 카디널리티 등을 정의할 수 있음

### Schema vs Ontology

| 구분 | Schema | Ontology |
| --- | --- | --- |
| 중심 | 데이터의 **구조** | 세계의 **의미·관계** |
| 예 | 컬럼·타입 정의 | Person과 Company의 관계 정의 |
| 범위 | 주로 특정 시스템 | 여러 시스템이 공유 가능한 의미 |
| 목적 | 저장·검증 | 의미 표현·추론 |

- 관계형 스키마는 보통 **닫힌 세계**를 가정하지만 RDFS/OWL은 **열린 세계**를 가정해, 없는 사실을 거짓이 아니라 `"모름"`으로 본다.
- RDFS의 `domain/range`는 DB 제약처럼 잘못된 값을 거부하는 기능보다 **새 타입을 추론하는 의미론**에 가깝다.

### Inference

**명시적으로 저장된 사실에서 규칙을 이용해 새로운 사실을 도출하는 것**

- 장점: 계층 탐색, 역관계 생성, 서로 다른 데이터셋 연결
- 주의: 잘못된 `sameAs` 같은 규칙은 오류를 그래프 전체에 전파할 수 있음
- `(worksAt domain Person) + (A worksAt 회사)` ⇒ `(A type Person)`

## 4. SPARQL

**RDF 그래프에서 원하는 트리플 패턴을 찾는 질의 언어**

- 구조: `PREFIX → SELECT/ASK/CONSTRUCT/DESCRIBE → WHERE { triple pattern }`
- 변수는 `?person`처럼 표현
- **여러 패턴이 같은 변수를 공유하면 조인**이 발생하고, 패턴을 연속해서 연결하면 multi-hop 질의가 된다
- 주요 문법: `OPTIONAL`, `FILTER`, `ORDER BY`, `COUNT/GROUP BY`, Property Path

### Wikidata에서 알아둘 것

- `Q`: Item/entity
- `P`: Property
- `wd:`: entity / `wdt:`: 직접 값 / `p:`: statement / `ps:`: statement의 값 / `pq:`: qualifier
- **Qualifier:** 단순 `속성-값`에 시간·순서 등의 추가 맥락을 붙임
  - Wikidata 공식 모델에서도 statement는 subject-predicate-object 구조를 기본으로 하며 qualifier로 이를 확장한다.

## 5. Property Graph vs RDF Triple Store

| 구분 | Property Graph | RDF |
| --- | --- | --- |
| **사용 목적** | **관계 속성, 경로 탐색이 중심** | **여러 데이터셋, 공개 데이터 연결** |
| 기본 단위 | Node + Relationship | Triple |
| 속성 | 노드·관계에 직접 부착 | 속성도 트리플로 표현 |
| 식별자 | 로컬 DB 중심 | 전역 IRI |
| 스키마 | 선택적·검증 중심 | RDFS/OWL 의미·추론 |
| 질의 | Cypher / GQL | SPARQL |
| 강점 | 경로 탐색, 개발 편의 | 데이터 통합, 표준, 추론 |

- **RDF:** 웹처럼 분산된 데이터를 공통 식별자·표준 어휘로 연결하는 것이 중심
- **Property Graph:** 한 애플리케이션에서 복잡한 연결을 직관적으로 모델링하고 탐색하는 것이 중심
- 둘 중 하나가 우월한 것이 아니라 **사용 목적이 다름**
- 여러 데이터셋과 공개 데이터를 연결하려면 RDF, 관계 속성과 경로 탐색이 중심이면 Property Graph가 자연스러움

## 6. W3의 못 답한 질문을 그래프로 표현

**Q: 부산 같이 간 사람들 중 같은 회사 다니는 사람?**

<img width="2048" height="1446" alt="image" src="https://github.com/user-attachments/assets/65e016cb-6d93-42ce-b75b-57c882f44ef4" />


**방법**: 질문 선택 → 필요한 사실 분해 → 명사=Node, 동사=Relationship → 경로 연결 → Hop 수 확인

- 필요 사실: A가 부산여행 참가, B가 부산여행 참가, A가 회사 X 근무, B가 회사 X 근무
- 클래스: 사람, 여행, 회사
- 관계: 참가, 근무
- 텍스트 검색에서는 여러 문서에 흩어진 사실을 모두 가져와야 하지만, 그래프에서는 관계를 연결해 **조인/경로 탐색** 문제로 표현할 수 있음
