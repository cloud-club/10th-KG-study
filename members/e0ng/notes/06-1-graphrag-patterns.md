---
title: GraphRAG 패턴
date: 2026-10-07
tags: [graphrag, local-search, global-search, text2cypher]
status: in-progress
---

## GraphRAG 패턴

- GraphRAG

  Graph + RAG

  데이터에서 **Entity와 Relationship을 추출해 그래프 구성**

  **그래프의 연결 관계를 검색에 활용**하는 방식

> “구축된 그래프를 어떻게 검색해서 RAG의 Context를 만들 것인가”

### 로컬 서치

: 질문과 관련된 **Entity를 찾아 주변 Subgraph를 탐색**하여 답변에 필요한 정보를 가져오는 방식

**Subgraph 부분 그래프:** 일부 노드와 관계만 떼어낸 그래프

#### 1) 링킹 로컬 서치 Entity Linking

사용자 질문에서 그래프에 존재하는 Entity를 찾아 연결한다
```
“맹구가 다니는 회사는 어느 도시에 위치해 있어?”
              ↓
         "맹구" 식별
              ↓
       (맹구:Person)

```

⬇️ 그래프에 다음과 같은 정보가 있다고 가정
```
(맹구:Person)
     │
     │ WORKS_FOR
     ↓
(ABC 회사:Company)
     │
     │ LOCATED_IN
     ↓
(서울:City)

```

⬇️

`맹구`를 그래프의 `(맹구:Person)` 노드와 연결하여 **탐색을 시작할 Entity**를 찾는다

#### 2) 주변 Subgraph 탐색

링킹된 Entity를 시작점으로 **주변 Relationship을 따라가며 질문에 필요한 부분 그래프를 탐색**한다

ex) 전체 그래프 예시
```
                         (서울:City)
                             ↑
                         LOCATED_IN
                             │
                      (ABC 회사:Company)
                             ↑
                         WORKS_FOR
                             │
                             │
(짱구:Person) ← FRIEND_OF ─ (맹구:Person) ─ LIVES_IN → (떡잎마을:City)
                             │
                         STUDIED_AT
                             ↓
                       (OO대학교)

```

⬇️ 주변 Subgraph를 탐색한 뒤 질문과 관련된 경로 선택
```
(서울:City)
     ↑
 LOCATED_IN
     │
(ABC 회사:Company)
     ↑
 WORKS_FOR
     │
(맹구:Person)

```

#### 3) 컨텍스트 Context

탐색한 Subgraph를 **LLM이 답변 생성에 사용할 수 있는 형태로 정리**한다
```
Question
“맹구가 다니는 회사는 어느 도시에 위치해 있어?”

Context
- 맹구는 ABC 회사에 다닌다.
- ABC 회사는 서울에 위치한다.

          ↓ LLM

Answer
“맹구가 다니는 회사는 서울에 위치해 있다.”

```

### 글로벌 서치 Global Search

**그래프 전체의 큰 주제와 구조를 파악하고 여러 영역의 정보를 종합**하여 답변하는 방식

예를들어
```
“이 데이터에서 사람들이 주로 어떤 분야에서 활동하고 있어?”

```

와 같은 질문이라면
`맹구` 하나의 주변만 탐색해서는 답하기 어렵다

#### 1) 커뮤니티 탐지

**Community =** 전체 그래프에서 **서로 상대적으로 밀접하게 연결된 Node들의 그룹**

그래프에 구분선을 그어주는 단계

- 기존 그래프 - `"누가 누구와 연결되어 있는가?"`
```
       (서울)                    (OO대학교)                 (디자인회사)
         ↑                          ↑                          ↑
     LOCATED_IN                 STUDIES_AT                 WORKS_FOR
         │                          │                          │
     (ABC 회사)                    (철수)                       (유리)
         ↑                          │                          │
     WORKS_FOR                 INTERESTED_IN                 WORKS_ON
         │                          ↓                          ↓
       (맹구)                    (인공지능)                  (UX 프로젝트)
         │
     FRIEND_OF
         ↓
       (짱구)

```

- **Community -** `"연결 구조를 봤을 때 어떤 노드들이 한 집단인가?"`
```
[Community 1]          [Community 2]          [Community 3]

     서울                  OO대학교                디자인회사
      ↑                      ↑                      ↑
  LOCATED_IN              STUDIES_AT             WORKS_FOR
      │                      │                      │
   ABC 회사                  철수                    유리
      ↑                      │                      │
  WORKS_FOR              INTERESTED_IN            WORKS_ON
      │                      ↓                      ↓
     맹구                  인공지능                UX 프로젝트
      │
  FRIEND_OF
      ↓
     짱구

```

#### 2) 커뮤니티 요약

각 Community에 어떤 Entity와 Relationship이 있는지 바탕으로 **해당 Community의 내용 요약**

→ 그래프 자체를 매번 읽는 대신 **Community별 요약 정보**를 활용 가능
```
Community 1
→ 맹구와 ABC 회사를 중심으로 한 회사·지역 관련 정보

Community 2
→ 철수와 OO대학교를 중심으로 한 AI·학업 관련 정보

Community 3
→ 유리와 디자인회사를 중심으로 한 디자인·프로젝트 관련 정보

```

#### 3) 종합

예를들어
```
“이 그래프에는 전반적으로 어떤 내용이 있어?”

```

라는 질문이라면,
```
Community 1 요약 ──┐
                  │
Community 2 요약 ──┼──→ 종합 : 회사·지역, AI·학업,디자인·프로젝트 관련 정보가 주요 주제로 나타남
                  │
Community 3 요약 ──┘

```

> 👀
>
> **Local Search**
> 핵심 Entity → 주변 관계 탐색 → 관련 Subgraph → Context
>
> **Global Search**
> 전체 그래프 → Community 탐지 → Community 요약 → 종합

### Text2Cypher

사용자의 **자연어 질문을 LLM이 Cypher 쿼리로 변환**하고,
생성된 쿼리를 그래프 DB에 실행하여 필요한 정보를 직접 조회하는 방식

#### **1) Cypher 생성**

LLM에게 **질문 + 그래프 스키마 → Cypher를 생성**
```
[Schema]
Person -[:WORKS_FOR]-> Company
Company -[:LOCATED_IN]-> City

[Question]
맹구가 다니는 회사는 어느 도시에 위치해 있어?

```

⬇️ LLM
```
MATCH (p:Person {name: "맹구"})
      -[:WORKS_FOR]->(c:Company)
      -[:LOCATED_IN]->(city:City)
RETURN city.name;

```

#### 2) 그래프 조회

생성된 Cypher를 Neo4j에 실행
```
Cypher
  ↓
Neo4j
  ↓
"서울"

```

#### 3) 답변 생성

조회 결과를 다시 LLM에 전달해 자연어 답변 생성
```
Query Result
"서울"

```

⬇️ LLM
```
“맹구가 다니는 회사는 서울에 위치해 있어.”

```
