---
title: 하이브리드 리트리버
date: 2026-10-07
tags: [graphrag, hybrid-retrieval, vector-search, graph-search]
status: in-progress
---

## 하이브리드 리트리버

> Local Search + 벡터 검색

벡터 검색으로 질문과 의미적으로 가까운 진입 노드 Seed Node를 찾고,
해당 노드에서 그래프 관계를 따라 주변 정보를 확장하는 검색 방식

- Vector Search = 어디서 탐색을 시작할지 찾기
  - 의미가 비슷한 정보를 찾는 데 강점
  - 정확한 Entity 이름을 몰라도 찾을 수 있음
- Graph Search = 찾은 지점에서 연결된 정보까지 확장하기
  - 명시적인 연결 관계를 따라가는 데 강점
  - Multi-hop 관계를 탐색할 수 있음

### 1) 벡터 검색 — Seed Node 찾기

의미적 유사성을 이용해 Seed Node를 찾는다
```
       (서울:City)                    (ABC 회사)
           ↑                             ↑
       LOCATED_IN                    WORKS_FOR
           │                             │
      (OO대학교)                       (맹구)
           ↑
       STUDIES_AT
           │
         (철수)
           │
     INTERESTED_IN
           ↓
       (인공지능)

```

정확한 Entity 이름인 `철수`를 모르고 질문을 했다고 가정
```
“AI에 관심 있던 사람이 다니는 학교는 어느 도시에 있어?”

```

⬇️ 질문 임베딩 → 그래프의 Entity나 연결된 문서/청크 임베딩과 비교해서 **의미적으로 가까운 진입점을 찾음**
```
“AI에 관심 있던 사람”
        ↓
   Vector Search
        ↓
     (철수:Person)
      Seed Node

```

### 2) 그래프 확장 — 주변 관계 탐색

진입 노드에서 그래프의 Relationship을 따라 확장한다
```
        (OO대학교)
            ↑
        STUDIES_AT
            │
          (철수)
            │
      INTERESTED_IN
            ↓
        (인공지능)

```

⬇️ `철수`를 Seed Node로 그래프의 Relationship을 따라 탐색 - `STUDIES_AT` 관계를 따라감

- **1-hop**
```
철수
 │ STUDIES_AT
 ↓
OO대학교

```

- 2-hop
```
철수
 │ STUDIES_AT
 ↓
OO대학교
 │ LOCATED_IN
 ↓
서울

```

### 3) Context 구성

벡터 검색 + 그래프 확장으로 얻은 정보를 LLM이 사용할 Context로 만든다.
```
Context
- 철수는 인공지능에 관심이 있다.
- 철수는 OO대학교에서 공부한다.
- OO대학교는 서울에 위치한다.

```

⬇️ LLM
```
“AI에 관심 있는 철수가 다니는 OO대학교는 서울에 위치해 있어.”

```
