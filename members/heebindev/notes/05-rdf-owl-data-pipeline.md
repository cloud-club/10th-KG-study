---
title: RDF와 지식 그래프 데이터 파이프라인
date: 2026-09-30
tags: [rdf, owl, triple-extraction, turtle, neo4j, cypher]
status: in-progress
---

# 5. RDF와 지식 그래프 데이터 파이프라인

지난주에는 RDF 트리플과 온톨로지의 개념을 공부했다.
이번 주에는 내 운영체제 노트에서 실제로 엔티티와 관계를 추출하고, 이를 여러 저장소에 넣어 지식 그래프로 만든다.

```text
운영체제 노트의 청크
→ LLM으로 엔티티와 관계 추출
→ Postgres 테이블에 저장
→ Turtle 파일로 내보내기
→ Neo4j에 같은 내용을 적재
→ Cypher로 관계 검색
```

## 1. 문서에서 트리플 추출하기

지난 검색 실습에서는 문서를 청크로 나누고 질문과 관련된 청크를 찾았다.
이번에는 청크 안에 들어 있는 사실을 다음과 같은 트리플로 바꾼다.

```text
프로세스 -- 사용한다 --> CPU
Running -- 전이한다 --> Blocked
SJF -- 종류이다 --> 스케줄링 알고리즘
운영체제 -- 관리한다 --> 메모리
```

문장은 표현 방식이 다양하기 때문에 규칙만으로 모든 트리플을 추출하기 어렵다.
따라서 LLM에게 원문과 사용할 스키마를 함께 주고, 정해진 형식으로 엔티티와 관계를 뽑게 한다.

LLM이 추출했다고 해서 모두 사실인 것은 아니다.
원문에 없는 관계를 만들거나, 같은 대상을 서로 다른 엔티티로 인식할 수 있으므로 결과를 확인해야 한다.

## 2. 닫힌 스키마
참고: https://wikidocs.net/319219

스키마는 데이터에 어떤 종류의 엔티티와 관계를 사용할지 정한 규칙이다.

LLM이 관계 이름을 자유롭게 만들도록 하면 다음처럼 같은 뜻의 관계가 여러 개 생길 수 있다.

```text
USES
USE
USES_RESOURCE
사용한다
활용한다
```

닫힌 스키마는 미리 정의한 클래스와 관계만 사용하도록 제한한다.
이번 실습에서는 운영체제 노트에 맞는 작은 스키마를 먼저 만들고, LLM이 그 안에서만 결과를 출력하도록 한다.

### 클래스 초안

| 클래스 | 의미 | 예시 |
| --- | --- | --- |
| `Concept` | 운영체제의 일반적인 개념 | 문맥 교환, 교착상태 |
| `Process` | 실행되는 프로세스의 종류 | CPU-bound process |
| `Resource` | 운영체제가 관리하거나 프로세스가 사용하는 자원 | CPU, 메모리, 프린터 |
| `Algorithm` | 운영체제에서 사용하는 알고리즘 | SJF, Round Robin |
| `State` | 프로세스의 상태 | Ready, Running, Blocked |

### 관계 초안

| 관계 | 의미 | 예시 |
| --- | --- | --- |
| `IS_A` | 어떤 개념의 종류이다 | SJF → 스케줄링 알고리즘 |
| `USES` | 자원을 사용한다 | 프로세스 → CPU |
| `MANAGES` | 자원을 관리한다 | 운영체제 → 메모리 |
| `HAS_STATE` | 어떤 상태를 가진다 | 프로세스 → Running |
| `TRANSITIONS_TO` | 다른 상태로 전이한다 | Running → Blocked |
| `SCHEDULED_BY` | 알고리즘에 의해 스케줄된다 | 프로세스 → Round Robin |
| `REQUIRES` | 성립하기 위해 조건이 필요하다 | 교착상태 → 상호 배제 |
| `PREVENTS` | 어떤 현상을 방지한다 | 선점 허용 → 교착상태 |

이것은 완성된 온톨로지가 아니라 내 데이터로 먼저 실험하기 위한 **미니 온톨로지 v0**이다.
실제 추출 결과를 보면서 부족한 클래스나 관계를 수정할 수 있다.

## 3. RDFS와 OWL은 어디에 사용되는가

RDF는 개별 사실을 트리플로 표현한다.
RDFS는 클래스, 속성, 상하위 관계와 같은 기본 스키마를 정의한다.
OWL은 여기에 더 복잡한 제약과 논리 규칙을 표현할 수 있게 한다.

```text
RDF: SJF는 스케줄링 알고리즘이다.
RDFS: SJF는 Algorithm 클래스에 속한다.
OWL: 특정 클래스가 가질 수 있는 관계와 제약을 더 자세히 정의한다.
```

이번 실습에서는 처음부터 복잡한 OWL 추론을 만드는 것이 아니라, RDFS 스타일로 클래스와 관계를 제한하는 것부터 시작한다.

## 4. LLM 정보 추출

LLM에게 단순히 `트리플을 뽑아줘`라고 하면 실행할 때마다 형식과 관계 이름이 달라질 수 있다.
안정적인 결과를 얻기 위해 출력 형식, 예시와 근거를 함께 지정한다.

아래는 하나의 정보 추출과정에서 함께 적용할 수 있는 3가지 보조장치이다

### 스키마를 강제한 JSON 출력

출력할 JSON 구조를 미리 정하고 다른 설명은 출력하지 않도록 한다.

```json
{
  "entities": [
    {
      "name": "프로세스",
      "type": "Process"
    },
    {
      "name": "CPU",
      "type": "Resource"
    }
  ],
  "relations": [
    {
      "subject": "프로세스",
      "predicate": "USES",
      "object": "CPU",
      "evidence": "프로세스는 CPU에서 실행된다."
    }
  ]
}
```

JSON Schema 같은 구조를 사용하면 필수 필드와 허용할 값을 제한할 수 있다.
예를 들어 `type`에는 위에서 정의한 다섯 클래스만, `predicate`에는 여덟 관계만 허용한다.

### Few-shot

Few-shot은 LLM에게 입력과 출력 예시를 몇 개 함께 보여주는 방법이다.

```text
입력: 운영체제는 메모리를 관리한다.
출력: 운영체제 -- MANAGES --> 메모리
```

예시를 보여주면 LLM이 원하는 엔티티 이름과 관계 형식을 이해하는 데 도움이 된다.

### 근거 스팬

근거 스팬은 트리플을 추출할 때 사용한 원문의 일부다.

```text
트리플: 프로세스 -- USES --> CPU
근거: "프로세스는 CPU에서 실행된다."
```

근거를 함께 저장하면 다음 내용을 확인할 수 있다.

- LLM이 원문에 있는 사실을 추출했는가?
- 원문의 어느 청크에서 나온 사실인가?
- 잘못된 트리플을 나중에 찾아서 수정할 수 있는가?

따라서 트리플만 저장하지 않고 `chunk_id`, 원문 근거와 추출 모델도 함께 기록하는 것이 좋다.

## 5. 엔티티 중복과 신원해소

같은 대상을 다르게 표현하면 서로 다른 엔티티가 만들어질 수 있다.

```text
운영체제
OS
Operating System
```

이 세 표현이 같은 대상을 의미한다면 하나의 대표 엔티티로 합쳐야 한다.
이 과정을 *신원해소(Entity Resolution)*라고 한다.

이번 실습에서는 이름을 정규화하고, 같은 `type`과 정규화된 이름을 가진 엔티티를 같은 대상으로 처리하는 간단한 규칙부터 사용할 수 있다.

```text
OS → 운영체제
CPU 스케줄러 → 스케줄러
```

이 규칙이 완벽하지 않기 때문에 원래 이름도 함께 보관하는 것이 좋다.

## 6. Postgres에 그래프 저장하기

그래프 데이터도 관계형 데이터베이스의 테이블에 저장할 수 있다.
이번 실습에서는 엔티티, 관계와 근거를 분리한다.

### 엔티티 테이블

| id | name | type |
| --- | --- | --- |
| 1 | 프로세스 | Process |
| 2 | CPU | Resource |

### 관계 테이블

| id | subject_id | predicate | object_id |
| --- | --- | --- | --- |
| 1 | 1 | USES | 2 |

### 근거 테이블

| relation_id | chunk_id | evidence |
| --- | --- | --- |
| 1 | `abc123` | 프로세스는 CPU에서 실행된다. |

Postgres에서는 외래 키와 조인으로 엔티티와 관계를 연결한다.
트리플을 저장하는 것은 가능하지만, 여러 관계를 반복해서 따라가는 질의는 조인이 계속 늘어나 복잡해질 수 있다.

## 7. RDF 직렬화

*직렬화*는 메모리나 데이터베이스에 있는 데이터를 파일이나 네트워크로 전달할 수 있는 형식으로 바꾸는 것이다.

RDF 그래프도 여러 문법으로 저장할 수 있다.
표현 형식은 달라도 같은 트리플을 나타낼 수 있다.

### Turtle

Turtle은 RDF 그래프를 사람이 비교적 읽기 쉬운 텍스트로 표현한다.
파일 확장자는 보통 `.ttl`을 사용한다.

```turtle
@prefix os: <https://example.org/os/> .

os:process os:uses os:cpu .
os:sjf os:isA os:schedulingAlgorithm .
```

- 한 줄은 기본적으로 `주어 술어 목적어 .` 형태다.
- 각 트리플의 끝에는 마침표를 붙인다.
- `@prefix`로 긴 URI를 짧게 표현한다.

### JSON-LD

JSON-LD는 RDF의 의미를 JSON 형태로 표현한다.
웹 애플리케이션에서 사용하는 JSON 구조에 `@context`, `@id`, `@type` 같은 정보를 추가한다.

```json
{
  "@context": {
    "os": "https://example.org/os/",
    "uses": "os:uses"
  },
  "@id": "os:process",
  "@type": "os:Process",
  "uses": {
    "@id": "os:cpu"
  }
}
```

Turtle과 JSON-LD는 서로 완전히 다른 데이터 모델이 아니라, *같은 RDF 그래프를 표현하는 서로 다른 직렬화 형식*이다.

### 표준으로 내보내는 이유

내부 데이터베이스의 테이블 구조만 사용하면 다른 도구가 그 의미를 바로 알기 어렵다.
RDF 표준 형식으로 내보내면 RDF를 지원하는 트리플 스토어와 도구에서 같은 데이터를 다시 사용할 수 있다.

## 8. Neo4j에 그래프 저장하기

Neo4j는 프로퍼티 그래프 데이터베이스다.
엔티티는 노드, 관계는 엣지로 저장한다.

```text
(프로세스:Process)-[:USES]->(CPU:Resource)
(Running:State)-[:TRANSITIONS_TO]->(Blocked:State)
```

노드는 이름과 타입 같은 속성을 갖고, 관계도 `chunk_id`와 `evidence` 같은 속성을 가질 수 있다.

### MERGE

`CREATE`는 실행할 때마다 새로운 노드나 관계를 만든다.
같은 데이터를 다시 적재하면 중복이 생길 수 있다.

`MERGE`는 지정한 패턴이 이미 있으면 기존 데이터를 찾고, 없으면 새로 만든다.

```cypher
MERGE (p:Process {name: "프로세스"})
MERGE (cpu:Resource {name: "CPU"})
MERGE (p)-[:USES]->(cpu)
```

`MERGE`만 사용한다고 모든 중복 문제가 자동으로 해결되는 것은 아니다.
이름 표준화와 고유성 제약을 함께 사용해야 한다.

## 9. Cypher 질의

Cypher는 Neo4j에서 그래프를 조회하고 수정하는 질의 언어다.
괄호는 노드, 대괄호와 화살표는 관계를 나타낸다.

### Cypher와 SPARQL의 차이

Cypher와 SPARQL은 모두 그래프에서 관계를 찾는 질의 언어지만, 사용하는 데이터 모델이 다르다.

| 질의 언어 | 사용하는 데이터 모델 | 대표 저장소 | 데이터를 표현하는 방식 |
| --- | --- | --- | --- |
| `Cypher` | 프로퍼티 그래프 | Neo4j | 노드와 관계에 속성을 붙임 |
| `SPARQL` | RDF 그래프 | RDF 트리플 스토어 | 주어-술어-목적어 트리플로 표현함 |

예를 들어 `프로세스가 사용하는 자원`을 찾는 Cypher 질의는 다음과 같다.

```cypher
MATCH (p:Process)-[:USES]->(r:Resource)
RETURN p, r
```

같은 관계를 RDF에서 찾는 SPARQL 질의는 다음처럼 표현할 수 있다.

```sparql
PREFIX os: <https://example.org/os/>

SELECT ?process ?resource
WHERE {
  ?process os:uses ?resource .
}
```

둘 중 하나가 더 좋은 것이 아니라 데이터를 어떤 모델로 저장했는지에 따라 사용하는 질의 언어가 달라진다.
이번 실습에서는 같은 지식을 Turtle 형식의 RDF로 내보내고, Neo4j의 프로퍼티 그래프에도 저장해 두 표현 방식을 비교한다.

### 1-hop 질의

한 개의 관계를 따라가는 질문이다.

```cypher
MATCH (p:Process)-[:USES]->(r:Resource)
RETURN p, r
```

```text
프로세스가 사용하는 자원은 무엇인가?
프로세스 → USES → 자원
```

### 가변 길이 경로

관계를 몇 번 따라가야 할지 정해져 있지 않을 때 가변 길이 경로를 사용한다.

```cypher
MATCH path = (start)-[*1..3]->(end)
RETURN path
```

`*1..3`은 관계를 최소 1개, 최대 3개까지 따라가라는 의미다.
경로의 길이가 길어질수록 결과가 매우 많아질 수 있으므로 최대 길이를 정하는 것이 좋다.

### 다중 홉 질문

```text
프로세스가 I/O를 기다리면 어떤 상태가 되고,
그 상태에서 다음에는 어떤 상태로 이동할 수 있는가?
```

문서 검색은 이 질문에 필요한 내용을 여러 청크에서 모두 찾아야 한다.
그래프에서는 상태 사이에 저장된 관계를 따라가며 답을 찾을 수 있다.

```cypher
MATCH path = (start:State {name: "Running"})-[:TRANSITIONS_TO*1..3]->(end:State)
RETURN path
```

이번 실습에서 확인할 핵심은 검색 결과와 LLM의 추측에만 의존하지 않고, 저장된 관계를 실제로 따라가서 답을 찾을 수 있는지다.

## 10. 브라우저에서 그래프 보기

공용 Docker Compose의 Neo4j를 실행하면 `http://localhost:7474`에서 Neo4j Browser를 사용할 수 있다.

Cypher 결과를 표뿐만 아니라 노드와 화살표가 연결된 그래프로 볼 수 있다.
시각화는 데이터가 올바르게 연결됐는지 확인하는 데 유용하지만, 화면이 보기 좋다고 추출한 사실이 모두 정확하다는 뜻은 아니다.

## 11. 이번 주에 확인할 내용

- 클래스와 관계가 운영체제 노트에 적절한가?
- LLM이 닫힌 스키마에 있는 값만 출력하는가?
- 모든 트리플에 실제 원문 근거가 있는가?
- 같은 엔티티가 다른 이름으로 중복 생성되지 않았는가?
- Postgres와 Turtle, Neo4j에 같은 사실이 저장됐는가?
- Cypher가 문서 검색으로 답하기 어려웠던 질문을 관계 탐색으로 답할 수 있는가?

## 참고 자료

- [W3C RDF 1.1 Turtle](https://www.w3.org/TR/turtle/) — RDF 그래프를 Turtle 문법으로 표현하는 방법
- [W3C JSON-LD 1.1](https://www.w3.org/TR/json-ld11/) — JSON 기반 RDF 직렬화 형식
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) — JSON Schema에 맞춘 구조화 출력
- [Neo4j Cypher MERGE](https://neo4j.com/docs/cypher-manual/current/clauses/merge/) — 기존 패턴을 찾거나 새로 생성하는 방법
- [Neo4j Variable-length paths](https://neo4j.com/docs/cypher-manual/current/patterns/variable-length-paths/) — 여러 관계를 따라가는 경로 질의
