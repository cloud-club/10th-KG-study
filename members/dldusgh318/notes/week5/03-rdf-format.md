# **RDF 직렬화 포맷 — Turtle과 JSON-LD**

## **1. RDF 직렬화란?**

RDF는 데이터를 **주어(Subject) - 술어(Predicate) - 목적어(Object)** 형태의 트리플로 표현하는 데이터 모델이다.

그런데 이 그래프를 실제 파일로 저장하거나 다른 시스템에 전달하려면 문자 형태로 표현해야 한다. 이를 **직렬화(Serialization)** 라고 한다.

즉,

**RDF라는 데이터 모델은 같고, Turtle·JSON-LD·N-Triples는 같은 그래프를 적는 서로 다른 방법이다.**

예를 들어 다음 사실이 있다고 하자.

```
SeCause ──usesTechnology──> Redis
```

이를 Turtle로 표현하면 다음과 같다.

```
kg:secause kg:usesTechnology kg:redis .
```

JSON-LD로 표현하면 형태는 달라진다.

```json
{
  "@context": {
    "kg": "http://example.org/kg/",
    "usesTechnology": "kg:usesTechnology"
  },
  "@id": "kg:secause",
  "usesTechnology": {
    "@id": "kg:redis"
  }
}
```

표현 방식은 다르지만 **둘 다 같은 관계를 나타낸다.**

---

## **2. Turtle과 JSON-LD**

이번 실습에서는 여러 RDF 직렬화 형식 중 **Turtle과 JSON-LD 정도만 이해하면 충분하다.**

| **포맷** | **특징** | **주 용도** |
| --- | --- | --- |
| **Turtle** | RDF를 간결하게 표현 | 사람이 읽고 작성하기 편함 |
| **JSON-LD** | JSON 형태로 RDF 표현 | 웹/API 환경과 결합하기 편함 |
| N-Triples | 한 줄에 트리플 하나 | 단순 처리·대용량 데이터 |
| RDF/XML | XML 기반 RDF 표현 | 기존 XML 생태계 |

### **Turtle**

Turtle은 앞선 W4에서도 사용했다.

```
@prefix kg: <http://example.org/kg/> .

kg:secause
    a kg:Project ;
    kg:usesTechnology kg:redis .
```

prefix와 `;` 같은 축약 표현을 사용할 수 있어 RDF를 사람이 비교적 쉽게 읽을 수 있다.

이번 실습에서 만드는 **`my-kg.ttl`이 바로 이 형식이다.**

### **JSON-LD**

JSON-LD는 JSON 문법을 이용해 Linked Data를 표현하는 방식이다.

핵심 키워드는 세 개 정도만 기억한다.

- `@context`: JSON에서 사용하는 용어를 IRI와 연결
- `@id`: 해당 개체의 식별자
- `@type`: 해당 개체의 타입

특히 `@context`를 이용하면 `"usesTechnology"` 같은 애플리케이션의 키가 RDF에서 어떤 의미의 IRI인지 정의할 수 있다.

따라서 JSON 기반 애플리케이션에서도 RDF의 전역적인 의미 체계를 연결할 수 있다는 장점이 있다.

---

## **3. 왜 표준 형식으로 내보낼까?**

우리의 실제 데이터 처리 흐름은 RDF 트리플 스토어를 중심으로 하지 않는다.

```
문서
 ↓
LLM 정보 추출
 ↓
중립적인 추출 JSON
 ↓
 ├─ Postgres
 ├─ Neo4j
 └─ Turtle / JSON-LD
```

Postgres와 Neo4j는 실제 저장·질의를 위해 사용하고, Turtle은 **같은 지식 그래프를 RDF 표준 형식으로 표현하기 위한 산출물**로 사용한다.

즉 **“표준으로 내보낸다”는 새로운 그래프를 만드는 것이 아니다.**

내부에서 사용하던 지식 그래프를 특정 DB 구조에만 묶어두지 않고, RDF 생태계에서도 해석할 수 있는 형태로 표현하는 것이다.

그래서 하나의 중립적인 추출 결과를 만든 뒤 각 저장소와 직렬화 포맷으로 변환한다. 각각 따로 추출하면 동일한 사실이 서로 다른 형태로 저장될 가능성이 있기 때문이다.

---

## **4. Evidence는 어떻게 할까?**

우리 그래프의 관계에는 단순한 트리플 외에도 `chunk_id`, `evidence`, `confidence` 같은 정보가 존재한다.

예를 들어:

```
SeCause ──usesTechnology──> Redis
             │
             ├─ evidence: "Redis를 작업 큐로 사용..."
             └─ chunk_id: chunk_103
```

하지만 기본적인 RDF 트리플은 `주어-술어-목적어`의 **2항 관계**이므로 이 추가 정보를 관계에 바로 붙일 수 없다.

W4에서 RDF의 **reification과 Wikidata의 statement 구조**를 공부했던 이유가 바로 이런 문제 때문이다. 단순한 `(SeCause, usesTechnology, Redis)`만으로는 그 관계의 근거·상태·시점 같은 추가 정보를 담을 자리가 없기 때문에 관계 자체를 하나의 대상으로 만들어야 했다.

이번 실습에서는 여기까지 복잡하게 만들지 않는다.

**Turtle에는 핵심 그래프만 내보내고, evidence와 chunk 정보는 Postgres와 Neo4j에 유지한다.**

이번 Turtle 산출물의 목적은 provenance 모델링 자체가 아니라 **우리 그래프를 RDF 표준 형식으로 내보내보는 것**이기 때문이다.

---

## **5. 스키마가 바뀌면 어떻게 될까?**

이번 주차에서 한 가지 더 확인할 것은 **스키마 진화(schema evolution)** 다.

처음에는 다음 관계만 사용했다고 하자.

```
TechnologyUse
 ├─ partOf
 └─ usesTechnology
```

이후 `status`도 필요하다는 것을 발견해 새로운 술어를 추가했다.

```
TechnologyUse
 ├─ partOf
 ├─ usesTechnology
 └─ hasStatus       ← 추가
```

RDF에서는 기존 트리플을 변경하지 않고 새로운 트리플을 추가할 수 있다.

```
kg:use-secause-redis
    kg:hasStatus "implemented" .
```

기존의 `partOf`, `usesTechnology` 트리플은 그대로 유지된다.

이러한 구조는 관계형 테이블의 고정된 컬럼 구조보다 **새로운 종류의 관계를 추가하기 유연하다.**

하지만 여기서 중요한 문제가 하나 있다.

### **기존 데이터에는 새로운 정보가 자동으로 생기지 않는다**

예를 들어:

```
v0 스키마로 추출한 300개
→ hasStatus 정보 없음

v1 스키마로 추출한 100개
→ hasStatus 정보 있음
```

이라고 하자.

이후 `"implemented인 기술 사용례를 모두 찾아줘"`라고 질의하면 앞의 300개는 어떻게 해야 할까?

**`hasStatus`가 없다고 해서 implemented가 아니라는 뜻은 아니다.**

단지 이전 스키마에서는 그 정보를 추출하지 않았기 때문에 **현재 그래프가 모르는 것**일 수 있다.

이는 W4에서 공부한 부정·부재 정보의 한계와도 연결된다.

**그래프에 어떤 사실이 없다는 것만으로 그 사실이 거짓이라고 판단할 수 없다. 기록하지 않았거나 아직 알지 못하는 정보일 수도 있기 때문이다.**

따라서 스키마 변경 자체는 쉽지만, **서로 다른 스키마 버전으로 추출된 데이터가 섞이면 조용한 누락이 발생할 수 있다.**

---

## **6. 추출 버전을 함께 관리하기**

이 문제를 구분하기 위해 추출 시점의 스키마 버전을 함께 기록할 수 있다.

예를 들어:

```
extraction_run = "v0-4predicates"
extraction_run = "v1-5predicates"
```

처럼 저장한다.

그러면 `hasStatus`가 없는 데이터가

- 실제로 상태 정보가 없었던 것인지
- `hasStatus`를 도입하기 전에 추출해서 없는 것인지

구분할 수 있다.

앞으로 스키마가 변경됐을 때도 이를 기준으로 **전체 데이터를 다시 추출할지, 일부만 재추출할지** 판단할 수 있다.

---

## **정리**

이번 파트에서 기억할 것은 세 가지다.

1. **RDF 모델은 하나이고 Turtle·JSON-LD 등은 같은 그래프를 표현하는 서로 다른 직렬화 방식이다.**
2. **Turtle로 내보내는 이유는 내부 그래프를 RDF 표준 형태로 표현해 상호운용 가능한 산출물을 만들기 위해서다.**
3. **트리플 구조에서는 새로운 술어를 유연하게 추가할 수 있지만, 기존 데이터에 새로운 정보가 자동으로 채워지는 것은 아니다.**

이번 실습에서는 LLM이 추출한 동일한 데이터를 **Postgres와 Neo4j에 저장하고, Turtle로도 내보내면서 “같은 지식 그래프를 서로 다른 시스템과 표현 방식으로 다루는 과정”을 직접 확인한다.**