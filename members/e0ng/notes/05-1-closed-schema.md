---
title: 닫힌 스키마 설계
date: 2026-09-30
tags: [ontology, closed-schema, rdfs, knowledge-graph]
status: in-progress
---

## 닫힌 스키마 설계

### 닫힌 스키마 closed schema

이 시스템에서 쓸 수 있는 클래스와 술어를 미리 정해진 목록으로 제한하는 것

- 클래스나 술어가 들어왔을 때 정의되어있는 목록에서 찾기
- 정의한 것 외의 새로운 종류는 사용 불가능
- 새로운 개념을 추가하기 위해 스키마 수정 필요

#### ↔️ 열린 스키마 open schema

기존 구조를 유지하면서 새로운 클래스나 속성을 필요에 따라 추가할 수 있는 설계 방식

- 컬럼 변경 방식보다 새로운 트리플 추가 용이
- 같은 의미가 여러 표현으로 나뉘어 일관성이 떨어질 수 있음

#### RDF

새로운 데이터와 관계를 쉽게 추가할 수 있다 → 열린 스키마

허용 목록 / 검증 규칙을 별도로 정해두고 사용한다 → 닫힌 스키마

### 온톨로지 방법론

>
>
> - Noy, N. F. & McGuinness, D. L., Ontology Development 101: A Guide to Creating Your First Ontology
> - Grüninger, M. & Fox, M. S., Methodology for the Design and Evaluation of Ontologies
> - Uschold, M. & King, M., *Towards a Methodology for Building Ontologies*

#### **Top-down**

“ 이 도메인을 구성하는 핵심 개념은 무엇인가? “

사람, 조직과 같은 일반적인 상위 개념 먼저 정의 후 하위 개념 구체화

```
개체
└─ 생명체
   └─ 사람
      └─ 직원
         ├─ 개발자
         └─ 기획자
```

- 일관성 있는 개념 체계 설계 가능
- 초기 도메인 분석 및 추상화 어려움

#### **Bottom-up**

“ 어떤 대상과 관계가 반복되는가? ”

데이터에서 반복해서 등장하는 대상과 관계를 찾아 개념으로 묶기

```
실제 데이터
민지 ──소속──▶ A회사
수현 ──소속──▶ B회사
지훈 ──소속──▶ A회사

        ↓ 공통 구조 추출

사람 ──소속──▶ 조직
```

- 실제 데이터와 잘 맞음
- 데이터에 없는 개념을 놓치거나 구조 파편화 가능성 존재

#### **Middle-out**

“ 가장 자주 사용하는 개념은 무엇인가? “

가장 중요하고 명확한 핵심 개념부터 정의 후 상/하위 개념으로 확장

```
              사람
               ↑ 상위 개념 추가
              직원
            ↙    ↘ 하위 개념 추가
         개발자    기획자
```

- 이해하기 쉽고 빠른 시작 가능
- 상위 핵심 개념 선택에 따라 전체 구조가 편향될 가능성 존재

#### Competency Question 기반

“ 이 온톨로지로 어떤 질문에 답해야 하는가? “

답해야하는 질문을 먼저 정하고, 답변에 필요한 클래스와 술어 도출

```
질문
“어떤 직원이 어떤 프로젝트에 참여하는가?”

        ↓ 필요한 개념·관계 도출

클래스: 직원, 프로젝트
술어: 참여함
```

- 불필요한 개념 증가 방지
- 질문 목록 밖의 활용에는 대응하지 못할 가능성 존재

#### 기존 온톨로지 재사용

“ 기존 어휘로 표현할 수 있는 개념은 무엇인가? “

`schema.org`, `FOAF`, `Dublin Core` 등 기존 어휘를 먼저 검토하고, 부족한 부분만 새로 정의

- 다른 데이터 및 시스템과의 연결 용이
- 기존 어휘가 도메인 의미와 정확히 일치하지 않을 수 있음

### 내 데이터에 맞는 클래스 / 술어

> 2026년 전반적인 활동이 포함된 Notion 데이터
>

```
Competency Question으로 범위 결정
                ↓
Bottom-up으로 실제 데이터 분석
                ↓
Middle-out으로 핵심 개념 선정
                ↓
기존 어휘와 비교
                ↓
클래스·술어 정의 및 검증
```

#### Competency Question으로 범위 결정

데이터에는 수업, 프로젝트, 취업 준비, 기술 공부 등 다양한 내용이 섞여있다

따라서 데이터를 먼저 모두 분석하면 필요하지 않은 개념까지 모델링할 가능성 높다

➡️ 온톨로지가 답할 질문을 정해 표현할 것과 제외할 것을 결정하는 것이 적절하다고 판단

```
Q1. 특정 기간에 어떤 활동을 했는가?
필요: Period, Activity, occursInPeriod

Q2. 특정 활동과 관련된 문서는 무엇인가?
필요: Activity, Document, hasDocument

Q3. 특정 문서는 어떤 주제를 다루는가?
필요: Document, Topic, schema:about

Q4. 특정 활동은 어떤 조직과 관련되어 있는가?
필요: Activity, Organization, relatedToOrganization

Q5. 특정 활동의 종류·범위·진행 상태는 무엇인가?
필요: activityKind, activityScope, status
```

#### Bottom-up으로 실제 데이터 분석

질문만 보고 설계하면 실제 데이터에는 없는 개념을 만들거나,
데이터에 존재하는 중요한 구조를 놓칠 수 있다

➡️ Notion의 폴더, 제목과 본문을 확인해 질문에 필요한 정보가 어떻게 표현되어 있는지 찾기

```
질문에서 예상한 개념: 기간

실제 데이터:
2026년 1학기
2026년 여름방학
2026년 2학기
```

```
질문에서 예상한 개념: 활동의 기록

실제 데이터:
노션 페이지 하나하나가 독립된 문서로 존재
(예: "졸전" 폴더 안에 "가구 GLB 파일 스트리밍.md", "공간 스캔 업로드 시작.md" 등 여러 파일)
```

** 이미 적재한 데이터는 페이지별로 청킹되어 있으며, 같은 페이지에서 생성된 청크는 동일한 `page_id`를 가진다

> 👀
>
> 질문 - 설계 범위 정하기
>
> 데이터 - 설계 근거 제공

#### **Middle-out으로 핵심 개념 선정**

Bottom-up 결과를 그대로 사용하면 졸업 전시, 취업 준비와 같은 구체적인 항목이 모두 별도 클래스가 될 수 있다

이를 여러 데이터에 공통으로 사용할 수 있는 중간 수준의 개념으로 묶어야 한다

➡️ 너무 추상적인 `Entity`부터 시작하지도 않고, 모든 페이지 제목을 클래스로 만들지도 않기 위해 Middle-out을 사용

```
졸업 전시          → Activity
코테 스터디        → Activity
Naver 지원 준비    → Activity

Naver              → Organization
```

"취업 준비"를 하나로 묶으면 "어느 회사를 준비했는가"를 답할 수 없다

Bottom-up에서 확인한 실제 폴더가 이미 회사별로 나뉘어 있어,
Activity도 그 단위 그대로 둔다.

#### 기존 어휘와 비교

자체적으로 모든 용어를 만들어 사용하면 다른 온톨로지와 같은 개념을 서로 다른 이름으로 표현하게 된다

➡️ 기존 어휘의 의미가 목적에 맞으면 재사용, 맞지 않는 개념만 직접 정의 → 호환성, 명확성 향상

```
Document ──aboutTopic──────▶ Topic
```

⬇️ `schema.org`의 기존 어휘로 대체

```
Document ──schema:about────▶ Topic
```

> 👀 **Q. 기존 어휘 적용보다 핵심 개념 정리를 먼저 한 이유는?**
>
> 기존 어휘를 먼저 적용하면 실제 데이터의 의미를 표준 어휘에 억지로 맞출 수 있다. 따라서 핵심 개념을 먼저 정리한 후 기존 어휘와 비교한다.

#### 클래스·술어 정의 및 검증

앞에서 찾은 개념과 관계에 이름, 의미, 주어/목적어 범위를 부여해 정식으로 정의

```
Activity ──occursInPeriod──▶ Period
Activity ──hasDocument─────▶ Document
Document ──schema:about────▶ Topic
```

그 후 Competency Question에 실제로 답할 수 있는지 확인

```
질문: KB 국민은행 지원 준비는 언제 했는가?

검증:
1. KB 국민은행 지원 준비 Activity를 조회할 수 있는가?
2. occursInPeriod가 없으면 "기간 정보 없음"으로 처리하는가?
3. 기간 정보가 없는 Activity도 잘못된 데이터로 판단하지 않는가?
```

질문에 답할 수 없는 경우 원인을 구분한다.

- 필요한 개념이나 관계가 없음 → 클래스·술어 설계 수정
- 개념과 관계는 있지만 실제 값이 없음 → 데이터 부족으로 기록

#### 최종 클래스 / 술어

```
Period
   ▲
   │ occursInPeriod
Activity ──hasDocument──────────▶ Document
   │                                  │
   │ relatedToOrganization            │ schema:about
   ▼                                  ▼
Organization                        Topic

Activity
├─ schema:name ────▶ "Naver 지원 준비"
├─ status ─────────▶ "In progress"
├─ activityKind ───▶ "취업 준비"
└─ activityScope ──▶ "대외"
```

- 클래스

| 클래스 | 뜻 |
| --- | --- |
| `Period` | 학기·방학 등의 기간 |
| `Activity` | 프로젝트·공부·수업·지원 등의 활동 |
| `Document` | Notion 페이지 한 장 |
| `Topic` | 문서가 다루는 주제 |
| `Organization` | 학교·기업·동아리 등의 조직 |
- 술어
    - 필수·선택은 온톨로지의 사용 규칙이며, 실제 데이터 검증이 필요하면 이후 SHACL로 정의한다.

| 술어 | 뜻 | Domain → Range | 사용 규칙 |
| --- | --- | --- | --- |
| `occursInPeriod` | 활동이 수행된 기간 | Activity → Period | 선택 |
| `hasDocument` | 활동과 관련된 문서 | Activity → Document | 필수 |
| `schema:about` | 문서가 다루는 주제 | Document → Topic | 선택 |
| `relatedToOrganization` | 활동과 관련된 조직 | Activity → Organization | 선택 |
| `schema:name` | 인스턴스의 이름 | 모든 인스턴스 → Literal | 필수 |
| `status` | 활동의 진행 상태 | Activity → `xsd:string` | 선택 |
| `activityKind` | 활동의 종류 | Activity → `xsd:string` | 선택 |
| `activityScope` | 활동의 범위 | Activity → `xsd:string` | 선택 |

#### RDFS 정의

```
@prefix ex: <https://example.com/ontology/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix schema: <https://schema.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:Period a rdfs:Class .
ex:Activity a rdfs:Class .
ex:Document a rdfs:Class .
ex:Topic a rdfs:Class .
ex:Organization a rdfs:Class .

ex:occursInPeriod
    a rdf:Property ;
    rdfs:domain ex:Activity ;
    rdfs:range ex:Period .

ex:hasDocument
    a rdf:Property ;
    rdfs:domain ex:Activity ;
    rdfs:range ex:Document .

ex:relatedToOrganization
    a rdf:Property ;
    rdfs:domain ex:Activity ;
    rdfs:range ex:Organization .

ex:status
    a rdf:Property ;
    rdfs:domain ex:Activity ;
    rdfs:range xsd:string .

ex:activityKind
    a rdf:Property ;
    rdfs:domain ex:Activity ;
    rdfs:range xsd:string .

ex:activityScope
    a rdf:Property ;
    rdfs:domain ex:Activity ;
    rdfs:range xsd:string .

schema:about
    rdfs:domain ex:Document ;
    rdfs:range ex:Topic .

schema:name
    rdfs:range rdfs:Literal .
```
