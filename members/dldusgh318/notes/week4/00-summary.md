# **Week 4. 지식 그래프의 배경 — 온톨로지 변천사와 방법론**

지난주에는 BM25와 Vector Search를 RRF로 결합하고, 검색된 청크를 LLM에게 전달하는 개인 RAG를 만들었다. 대부분의 질문은 잘 동작했지만, **필요한 정보가 문서에 존재해도 여러 청크에 흩어져 있으면 검색 단계에서 일부를 놓치는 경우**가 있었다.

특히 운영 배포의 RDS 인증 실패 원인과 수정·검증 과정을 묻는 질문에서는 필요한 세 청크 중 하나만 검색됐다. 같은 LLM과 Prompt에 정답 청크를 직접 넣어주자 답변할 수 있었기 때문에, 이 사례에서는 생성보다 **Retrieval이 병목**이었다.

그래서 이번 주에는 질문을 조금 바꿨다.

**문서를 잘 찾는 것에서 더 나아가, 문서 안의 사실과 관계를 구조화해두면 어떨까?**

---

## **1. RDF : 문서가 아니라 사실과 관계를 저장하기**

RDF(Resource Description Framework)는 정보를 다음과 같은 **Triple**로 표현한다.

| Subject | Predicate | Object |
| --- | --- | --- |
| SeCause | USERS_TECHNOLOGY | Redis |
| 연호 | ATTENDS | 홍익대학교 |

그래프로 보면 결국 `Node → Edge → Node`다.

RDF에서는 개체를 IRI로 식별하고, 문자열이나 숫자 같은 값은 Literal로 표현한다. 이름 없는 구조적 노드가 필요하면 Blank Node도 사용할 수 있다.

여기서 중요한 건 용어 자체보다 **모든 사실을 동일한 세 칸 구조로 표현한다는 것**이다.

### **그런데 세 칸으로 부족하면?**

내가 진행한 AI 코드 보안 분석 프로젝트인 SeCause에서 Redis를 사용했다고 해보자.

```
SeCause → USES_TECHNOLOGY → Redis
```

그런데 실제로는 이것만 알고 싶은 게 아니다.

- 어떤 기술을 사용했는가?
- 왜 사용했는가?
- 실제 구현했는가, 제안만 했는가?

기본 Triple에서는 관계 자체에 이런 정보를 바로 붙이기 어렵다.

그래서 **“특정 프로젝트에서 특정 기술을 사용한 경험” 자체를 하나의 중간 노드**로 만들 수 있다. 이 노드를 편의상 `TechnologyUse`라고 이름 붙였다.

```
TechnologyUse
 ├─ PART_OF → SeCause
 ├─ USES_TECHNOLOGY → Redis
 ├─ HAS_PURPOSE → AI 분석 작업 큐
 └─ HAS_STATUS → implemented
```

처음에는 내 데이터를 표현하기 위해 만든 구조였는데, RDF에서도 오래전부터 이런 **n항 관계(n-ary relation)** 문제를 다뤄왔다. 관계를 별도의 대상으로 만들어 정보를 붙이는 reification과도 문제의식이 닿아 있다.

즉 이번에 가져갈 핵심은 하나다.

**현실의 관계는 단순한 A → B보다 많은 정보를 가지고 있고, 필요하면 관계 자체를 하나의 대상으로 만들어야 한다.**

---

## **2. SPARQL : 저장한 관계를 어떻게 찾을까?**

RDF 형태로 데이터를 저장했다면 이를 조회하는 대표적인 언어가 **SPARQL**이다.

SQL이 테이블을 조회한다면 SPARQL은 **Triple Pattern**을 찾는다.

```
SELECT ?education WHERE {
  wd:Q42 wdt:P69 ?education .
}
```

의미는 간단하다.

```
Q42 → 교육기관 → ?
```

빈칸에 해당하는 값을 찾아달라는 것이다.

### **조인은 같은 변수로 한다**

SPARQL에서 인상적이었던 건 다중 관계를 연결하는 방식이었다.

```
?person wdt:P69 ?school .
?person wdt:P108 ?company .
```

두 Triple Pattern에서 같은 `?person`을 사용하면 **같은 사람을 기준으로 두 관계가 연결된다.**

<img width="2048" height="943" alt="image" src="https://github.com/user-attachments/assets/3bfe759c-ef47-4e4b-bcaa-48e34f41378e" />

즉 관계가 이미 구조화돼 있다면,

```
학교 → 사람 → 회사
```

같은 다중 홉 질문이 문서 검색 문제가 아니라 **그래프의 관계를 따라가는 문제**로 바뀐다.

### **Wikidata는 관계에 추가 정보를 어떻게 붙일까?**

앞에서 봤던 “세 칸으로 부족한 문제”를 Wikidata에서도 확인할 수 있었다.

→  https://query.wikidata.org/

단순 조회는 `wdt:`를 사용한다.

```
사람 → 교육기관 → 학교
```

하지만 재학 기간처럼 관계에 붙은 정보까지 필요하면 **statement 노드**를 거친다.

```
사람 → [교육 진술] → 학교
             ├→ 시작일
             └→ 종료일
```

SPARQL에서는 `p:`, `ps:`, `pq:`를 사용해 이 구조를 조회할 수 있다.

<img width="2048" height="926" alt="image" src="https://github.com/user-attachments/assets/0fd98303-2fdf-4608-9583-b7321c2c74d5" />

```sql
사람 ──p:P69──> [진술] ──ps:P69──> 학교
                   ├──pq:P580──> 시작일
                   └──pq:P582──> 종료일
```

이걸 보면서 `TechnologyUse`를 만든 이유와 같은 문제라는 걸 확인할 수 있었다. 둘이 완전히 동일한 데이터 모델은 아니지만, **단순 관계 하나로 부족해서 관계에 대한 정보를 별도로 표현한다**는 문제의식은 같다.

---

## **3. RDFS/OWL : 저장하지 않은 사실도 알 수 있을까?**

RDF는 사실을 표현할 수 있지만, 그 사실 사이의 의미까지 모두 정의해주지는 않는다.

예를 들어 다음과 같은 관계가 있다고 하자.

```
BackendEngineer → subClassOf → Engineer
Engineer → subClassOf → Person
연호 → type → BackendEngineer
```

그렇다면 `연호 → type → Person`을 직접 저장하지 않았더라도 알 수 있다.

이렇게 **기존 사실과 규칙으로부터 새로운 사실을 유도하는 것**이 추론(Inference)이다.

### **RDFS와 OWL**

RDFS는 비교적 단순한 의미 관계를 정의한다.

- `subClassOf` : 클래스 계층
- `subPropertyOf` : 속성 계층
- `domain` : 이 관계의 주어가 어떤 타입인지
- `range` : 목적어가 어떤 타입인지

OWL은 여기서 더 나아가 동일성, 역관계, 관계의 성질, 클래스 제약 등 더 풍부한 의미를 표현할 수 있다.

```
RDF       → 사실을 표현
RDFS/OWL  → 사실의 의미와 규칙을 표현
Inference → 규칙으로부터 적지 않은 사실을 유도
```

### **💥 domain/range는 검증 규칙이 아니다**

이 부분은 헷갈리기 쉬웠다.

```
attends의 range = School
연호 attends Redis
```

라고 했다고 해서 “Redis는 학교가 아니니까 오류!!”가 되는 게 아니다.

RDFS에서는 오히려 다음과 같이 추론한다.

```
Redis → type → School
```

즉 `domain/range`는 데이터가 올바른지 검사하는 Validation 규칙이 아니다. RDF 그래프를 검증하려면 **SHACL** 같은 별도의 접근이 필요하다.

### **열린 세계 가정**

RDF/OWL을 이해하면서 또 중요했던 게 **Open World Assumption(OWA)**이었다.

**적혀 있지 않은 것은 거짓이 아니라 모르는 것이다.**

`연호 → attends → 홍익대학교`가 있다고 해서 다른 학교에는 다니지 않는다고 결론낼 수 없다.

이건 웹처럼 데이터가 불완전한 환경에서는 자연스럽다. 다른 데이터셋에 새로운 사실이 존재할 수도 있기 때문이다.

반면 이번 실습은 정해진 관계만 추출하고 저장하는 작은 시스템이다. 추론 엔진도 없다.

그래서 우리가 만드는 것은 거대한 Ontology라기보다는? **실험 목적에 맞게 제한한 작은 관계 스키마**에 가깝다.

---

## **4. Semantic Web에서 Knowledge Graph까지**

여기까지 공부하면서 궁금했던 건 하나였다.

**이렇게 좋은 표준과 추론 방법이 오래전부터 있었는데, 왜 지금 웹 전체가 RDF와 OWL로 이루어져 있지는 않을까?**

2001년 Semantic Web의 목표는 웹 전체에 의미를 부여해 기계가 데이터를 이해하고 연결하도록 만드는 것이었다.

하지만 이를 위해서는 많은 전제가 필요했다.

```
웹사이트들이 구조화 데이터를 제공
→ 공통 표현과 어휘 사용
→ 서로 다른 데이터를 연결
→ 기계가 이를 조회하고 추론
```

문제는 **누가 먼저 이 비용을 부담하느냐**였다.

웹사이트 운영자가 열심히 메타데이터를 만들어도 그 이익을 검색엔진이나 다른 Agent가 가져갈 수 있다. 여러 주체가 동시에 참여해야 전체 가치가 커지는 **조정 문제**가 발생한다.

### **Google Knowledge Graph는 범위를 바꿨다**

2012년 Google Knowledge Graph는 비슷한 아이디어를 다른 방식으로 가져갔다.

웹 전체가 하나의 Ontology에 합의하기를 기다리는 대신 **필요한 데이터를 직접 수집하고 통합해 자신의 그래프를 만들었다.**

```
**Semantic Web**
모두가 공통 방식으로 데이터를 만들자
        ↓
**Knowledge Graph**
우리에게 필요한 데이터를 우리가 구조화하자!
```

이후 기업 Knowledge Graph도 비슷한 방향으로 발전했다.

세상 전체가 아니라 **상품, 사용자, 조직 등 특정 도메인으로 범위를 좁히고**, 그 조직이 필요한 스키마를 직접 정의했다.

즉 Semantic Web의 아이디어를 완전히 버렸다기보다 **보편성보다 실제 활용 가능성을 선택한 것**에 가깝다.

### **그리고 GraphRAG**

LLM이 등장하면서 또 하나가 바뀌었다.

과거에는 사람이 구조화 데이터를 만들고 관계를 정의하는 비용이 컸다면, 이제는 LLM을 이용해 문서에서 Entity와 Relationship을 자동으로 추출할 수 있게 됐다.

```
문서
 → LLM이 Entity / Relationship 추출
 → Graph 구축
 → Graph를 이용한 검색과 요약
```

Microsoft의 GraphRAG도 문서에서 Entity와 Relationship을 추출해 그래프를 만들고, 커뮤니티 구조와 요약을 활용해 기존 top-k RAG가 어려워하는 전체적인 질문을 다룬다.

다만 **LLM이 그래프를 만들어준다고 해서 스키마 합의나 Entity Resolution 문제가 사라지는 것은 아니다.** 자동화되는 것은 주로 구축 비용이다.

### **Palantir는 한 단계 더 나아간다**

Palantir의 Ontology에서는 Object와 Link를 이용해 조직의 데이터를 현실 세계의 개체와 관계로 표현한다.

여기에 흥미로운 점이 하나 더 있다. 바로 **Action**이다.

기존 Knowledge Graph가 주로 **“이 주문의 상태는?”** 처럼 그래프를 조회했다면,

Action이 있는 구조에서는 **“이 주문을 승인한다.”** 처럼 실제 업무 시스템의 변경까지 연결할 수 있다.

Semantic Web이 꿈꿨던 “기계가 의미를 이해하고 사람 대신 일을 수행한다”는 비전이 웹 전체가 아니라 **하나의 조직이라는 제한된 범위에서 다시 나타난 것**처럼 볼 수 있었다.

---

## **5. RDF와 Property Graph : 우리 실습은 어느 쪽일까?**

마지막으로 그래프를 실제로 저장하는 방식도 비교해봤다.

대표적으로 **RDF Triple Store**와 **Property Graph**가 있다.

둘 다 그래프지만 출발점이 조금 다르다.

|  | **RDF** | **Property Graph** |
| --- | --- | --- |
| 출발점 | 데이터 표현·연결·교환 | 애플리케이션 그래프 저장·탐색 |
| 기본 구조 | Subject-Predicate-Object | Node-Edge-Node |
| Edge에 속성 | 기본 Triple에는 직접 없음 | 직접 추가 가능 |
| 식별 | IRI 중심 | 내부/애플리케이션 ID 가능 |
| 대표 질의 | SPARQL | Cypher / GQL |
| 의미·추론 | RDFS/OWL 생태계 | 주로 패턴 탐색 |

특히 이번 실습과 연결되는 차이는 **Edge Property**다.

앞에서 SeCause와 Redis 관계에 목적과 상태를 붙이기 위해 `TechnologyUse`라는 중간 노드를 만들었다.

Property Graph에서는 이런 형태도 가능하다.

```
SeCause
 ── USES_TECHNOLOGY
      {purpose: "작업 큐", status: "implemented"}
 ──> Redis
```

관계 자체가 속성을 가질 수 있기 때문이다.

물론 관계 자체를 별도의 개체로 다뤄야 한다면 Property Graph에서도 중간 노드를 만드는 것이 적절할 수 있다. 핵심은 프로퍼티 그래프는 노드없이 관계 자체에도 속성을 붙일 수 있다는 것~

### **현재 실습은 어디에 가까울까?**

우리의 저장 구조는 대략 다음과 같다.

```
entities
- entity_id
- type
- label
- props

edges
- subject
- predicate
- object
- chunk_id
- evidence
- confidence
```

`props`로 Node Property를 저장하고, `evidence`, `confidence`처럼 **관계에 대한 정보도 Edge에 직접 저장한다.** 추론 엔진도 없고 외부와 공유할 IRI 체계를 만드는 것도 아니다.

따라서 지금 구조를 설명할 때는

**RDF의 Triple이라는 사고방식은 참고하지만, 실제 구현은 PostgreSQL 위에 작은 Property Graph를 구현하는 것에 가깝다.**

라고 보는 게 적절하다.

---

# **4주차를 정리하면**

이번 주 내용을 처음 봤을 때는 RDF, SPARQL, OWL, Semantic Web, Knowledge Graph가 전부 별개의 내용처럼 보였다.

그런데 실제로는 하나의 흐름으로 이어졌다.

```
W3
문서 검색에서 필요한 청크를 놓치는 사례 발견
↓
RDF
문서가 아니라 사실과 관계를 구조화하면 어떨까?
↓
SPARQL
구조화한 관계를 직접 따라가며 조회할 수 있다
↓
RDFS / OWL
관계에 의미와 규칙을 부여하면 새로운 사실도 추론할 수 있다
↓
Semantic Web → Knowledge Graph
하지만 웹 전체가 이 구조에 합의하기는 어려웠고,
실무에서는 도메인을 좁힌 Knowledge Graph가 발전했다
↓
Property Graph
우리 역시 범용 Ontology보다
현재 실험에 필요한 작은 관계 그래프를 만드는 쪽에 가깝다
```

이번 주에 가장 기억에 남은 건 **내가 실습을 위해 만든 구조가 기존 그래프 모델에서 오래전부터 고민해온 문제와 연결된다는 점**이었다.

처음에는 단순히 `SeCause → Redis`라고 연결하려 했다. 그런데 목적과 구현 상태가 필요해 `TechnologyUse`라는 중간 노드를 만들었다.

공부하고 나니 이 문제는 RDF에서는 `n항 관계와 reification`, Wikidata에서는 `statement와 qualifier`, Property Graph에서는 `Edge Property`와 연결되는 문제였다.

**2항 관계만으로 현실의 맥락을 표현하기 어렵다는 문제는 데이터 규모와 관계없이 반복된다.**

그리고 다음 주에는 이론을 더 확장하기보다 이걸 실제 데이터에 적용한다.

**기존 Hybrid RAG가 필요한 청크를 놓쳤던 질문에서, 문서 속 Entity와 Relationship을 미리 구조화해두면 Retrieval을 실제로 개선할 수 있을까?**

이제 이 가설을 직접 확인해본다.