---
title: RDF 직렬화 포맷
date: 2026-09-30
tags: [rdf, turtle, json-ld, serialization]
status: in-progress
---

## RDF 직렬화 포맷

RDF의 핵심은
데이터를 트리플로 표현하는 것

트리플을 실제 파일에 적는 여러 방식이 **직렬화 포맷**

### “표준으로 내보내기”

LLM이 아래와 같이 JSON을 출력했다고 가정했을 때,

```json
{
  "activity": "Naver 지원 준비",
  "organization": "Naver"
}
```

해당 JSON은 우리 프로그램만 의미를 알고 있다.

`activity`와 `organization`이 단순 문자열인지, 개체인지, 어떤 관계인지 다른 프로그램은 알 수 없다.
별도의 규칙을 공유하지 않은 프로그램은 이를 동일한 의미로 해석하기 어렵다.

따라서 개체와 관계의 의미를 URI로 명시하고,
다른 시스템도 동일하게 해석할 수 있는 공통 데이터 모델로 변환할 필요가 있다.

이를 위해 데이터를 RDF 표준 모델로 변환한다.
RDF 표준으로 내보낼 때 선택할 수 있는 대표적인 직렬화 포맷이
**Turtle**과 **JSON-LD**이다.

### Turtle

RDF 트리플을 사람이 읽기 쉽게 표현하는 포맷으로,
사람이 직접 작성하거나 온톨로지 구조를 확인할 때 편리하다

- `a` - rdf:type
- `;` - 같은 주어에 술어·목적어 추가
- `.` - 하나의 문장 종료

```
@prefix ex: <https://example.com/ontology/> .
@prefix activity: <https://example.com/activity/> .
@prefix period: <https://example.com/period/> .
@prefix organization: <https://example.com/organization/> .
@prefix schema: <https://schema.org/> .

activity:naver-job-application-preparation
    a ex:Activity ;
    schema:name "Naver 지원 준비"@ko ;
    ex:occursInPeriod period:2026-summer ;
    ex:relatedToOrganization organization:naver .

organization:naver
    a ex:Organization ;
    schema:name "Naver"@ko .
```

### **JSON-LD**

같은 RDF 데이터를 JSON과 비슷한 형태로 표현하는 포맷으로,
웹 API나 JSON 기반 애플리케이션과 연결하기 편리하다

- `@context` - 짧은 이름과 URI의 연결 규칙
- `@id` - 대상을 식별하는 URI
- `@type` - 대상이 속한 클래스
- `@value` - 리터럴 값
- `@language` - 문자열의 언어

```json
{
  "@context": {
    "ex": "https://example.com/ontology/",
    "activity": "https://example.com/activity/",
    "period": "https://example.com/period/",
    "organization": "https://example.com/organization/",
    "schema": "https://schema.org/",
    "name": "schema:name",
    "occursInPeriod": {
      "@id": "ex:occursInPeriod",
      "@type": "@id"
    },
    "relatedToOrganization": {
      "@id": "ex:relatedToOrganization",
      "@type": "@id"
    }
  },
  "@id": "activity:naver-job-application-preparation",
  "@type": "ex:Activity",
  "name": {
    "@value": "Naver 지원 준비",
    "@language": "ko"
  },
  "occursInPeriod": {
    "@id": "period:2026-summer"
  },
  "relatedToOrganization": {
    "@id": "organization:naver"
  }
}
```

### Turtle vs JSON-LD

```
Naver 지원 준비 ──관련 조직──▶ Naver
```

#### Turtle

```
activity:naver-job-application-preparation            # 주어: Naver 입사 지원 준비 활동
    ex:relatedToOrganization                           # 술어: 관련된 조직
    organization:naver .                               # 목적어: Naver 조직
```

#### JSON-LD

```json
{
  "@id": "activity:naver-job-application-preparation", // 현재 개체: Naver 입사 지원 준비 활동
  "relatedToOrganization": {                           // 관계: 관련된 조직
    "@id": "organization:naver"                        // 관계가 가리키는 개체: Naver 조직
  }
}
```
