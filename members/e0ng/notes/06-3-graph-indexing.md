---
title: 그래프 인덱싱과 빌드 시점 선지불
date: 2026-10-07
tags: [graphrag, graph-indexing, community-detection, global-search]
status: in-progress
---

## 그래프 인덱싱 - "빌드 시점 선지불"

Global Search에서는 그래프 전체를 활용하기 위해
**Community 탐지와 Community 요약** 같은 작업이 필요하다

그래프가 커질수록 수많은 Node와 Relationship을 대상으로 **연결 구조를 분석**해야 한다

이 과정을 질문이 들어올 때마다 반복한다면,
같은 그래프에 대해 동일한 계산을 반복해 비효율적이고 계산 비용이 커진다

➡️ 그래서 Build-time에 미리 계산하는 방식 사용

### 1) Build-time에 미리 계산

특정 질문에 대한 것이 아닌, 그래프 자체만으로 계산할 수 있는 정보를 미리 만든다

- 질문에 대한 답을 미리 만든다 (X)
- 나중에 검색할 재료를 미리 만들어 저장한다 (O)
```
Community 탐지 -> Community별 Entity / Relationship 수집 -> Community 요약 생성

```
```
[Community 1]
맹구는 ABC 회사에서 근무하며,
ABC 회사는 서울에 위치한다.
인물의 회사·지역 관계를 중심으로 한 Community이다.

[Community 2]
철수는 OO대학교에서 공부하며,
인공지능에 관심이 있다.
AI·학업을 중심으로 한 Community이다.

[Community 3]
유리는 디자인회사에서 근무하며,
UX 프로젝트에 참여하고 있다.
디자인·프로젝트를 중심으로 한 Community이다.

```

### 2) Query-time에 재사용

미리 만들어둔 Community 요약에서 관련 정보를 찾아 사용한다
```
“학업이나 프로젝트와 관련해서 어떤 활동들이 있어?”

```

⬇️ Community 요약에서 관련 정보 찾기
```
Community 1
회사·지역 관계
→ 관련도 낮음 ❌

Community 2
AI·학업
→ 관련도 높음 ⭕

Community 3
디자인·프로젝트
→ 관련도 높음 ⭕

```

⬇️ 관련 Community 요약 선택 및 종합
```
[Community 2]
철수는 OO대학교에서 공부하며,
인공지능에 관심이 있다.

[Community 3]
유리는 디자인회사에서 근무하며,
UX 프로젝트에 참여하고 있다.

```

⬇️
```
Context
- 철수는 OO대학교에서 공부하며 인공지능에 관심이 있다.
- 유리는 UX 프로젝트에 참여하고 있다.

```
```
Answer
“학업과 관련해서는 철수의 인공지능 관련 활동이 있고,
프로젝트와 관련해서는 유리의 UX 프로젝트 참여가 있다.”
```
