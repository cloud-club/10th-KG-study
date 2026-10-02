---
title: W5 문서에서 RDF로 - 닫힌 스키마, LLM 추출, 표준 직렬화
date: 2026-09-30
tags: [rdf, rdfs, llm, information-extraction, turtle, json-ld, ontology]
status: complete
---

# W5 문서에서 RDF로: 닫힌 스키마, LLM 추출, 표준 직렬화

## 이 노트의 흐름

문장을 그래프 데이터로 바꾸려면 세 가지 질문에 답해야 한다.

| 순서 | 질문 | 이번 노트에서 다루는 개념 |
| --- | --- | --- |
| 1 | 어떤 종류의 대상과 관계를 기록할 것인가? | 닫힌 스키마, 클래스, 술어 |
| 2 | 문장에서 그 정보를 어떻게 찾아낼 것인가? | LLM 추출, JSON, few-shot, 근거 |
| 3 | 결과를 다른 프로그램도 이해하게 어떻게 전달할 것인가? | RDF, Turtle, JSON-LD |

예시를 위해 가상의 공지 문장을 사용한다.

> W5에서는 RDF 직렬화를 공부한다.

이 문장을 처리해 그래프로 옮기는 과정을 따라가면, 각 개념이 왜 필요한지 알 수 있다. 이 노트는 이론과 데이터 표현을 설명하며 특정 데이터를 처리하는 방법은 다루지 않는다.

## 1. 먼저 구분하기: 문장, 사실 후보, 그래프

문장에는 여러 정보가 자연스러운 말로 들어 있다. 사람은 문장을 읽고 대상과 관계를 알아내지만, 컴퓨터가 항상 같은 뜻으로 해석하는 것은 아니다.

| 단계 | 예시 | 무엇을 말하는가 |
| --- | --- | --- |
| 원문 문장 | W5에서는 RDF 직렬화를 공부한다 | 사람이 쓴 자연어 |
| 사실 후보 | W5의 주제는 RDF 직렬화다 | 문장에서 해석한 내용 |
| 그래프 관계 | StudyWeek-05 — hasTopic → Topic-RDF | 대상과 관계를 정해진 형식으로 표현 |

LLM이 사실 후보를 출력했다고 해서 그 내용이 자동으로 참이 되는 것은 아니다. 그 후보가 원문에서 실제로 나왔는지 확인할 수 있도록 근거를 함께 보관해야 한다.

~~~text
원문
  ↓ 어떤 정보를 기록할지 미리 정함
스키마
  ↓ 허용된 형식에 맞춰 문장에서 후보 추출
구조화된 결과와 근거
  ↓ 내용과 구조를 검증
RDF 그래프
  ↓ 표준 문법으로 파일에 표현
Turtle 또는 JSON-LD
~~~

## 2. 스키마란 무엇인가

스키마(schema)는 데이터를 어떤 구조로 기록할지 정한 설계다. 쉽게 말해, 기록할 수 있는 대상의 종류와 관계의 종류를 미리 정하는 규칙이다.

예를 들어 학습 공지를 정리한다고 하자. 모든 대상을 한 종류로 취급할 수는 없다. 공지, 주차, 학습 주제는 서로 다른 종류다. 또한 공지와 주차의 관계, 주차와 주제의 관계도 구별해야 한다.

| 구분 | 뜻 | 예 |
| --- | --- | --- |
| 클래스 | 대상의 종류 | 공지, 학습 주차, 주제 |
| 개체 | 클래스에 속하는 특정 대상 | W5 주차, 특정 공지 |
| 술어 | 대상 사이의 관계 또는 대상의 값 | 공지가 주차를 알린다 |
| 리터럴 | 날짜·숫자·문자열 같은 값 | 2026-10-08 |

클래스가 설계도상의 종류라면, 개체는 그 종류에 속하는 하나의 대상이다.

~~~text
클래스: StudyWeek
개체:   week-05
뜻:     week-05는 학습 주차 한 개다
~~~

술어(predicate)는 RDF 트리플에서 관계의 이름이다. “W5가 RDF 직렬화를 주제로 다룬다”에서 hasTopic이 술어다.

~~~text
week-05 ──hasTopic──> topic-rdf
~~~

## 3. 닫힌 스키마: 사용할 관계 목록을 미리 정한다

문장마다 관계 이름을 자유롭게 만들면 같은 사실이 다른 이름으로 저장된다. 예를 들어 “게시자”, “작성자”, “공지한 사람”을 서로 다른 관계로 만들 수 있다. 프로그램은 이 이름들이 같은 의미인지 알기 어렵다.

**닫힌 스키마(closed schema)**는 사용할 클래스와 술어의 목록을 미리 정하는 방식이다. 추출기는 이 목록 안에서 적절한 항목을 고른다. 맞는 항목이 없으면 새 관계를 지어내지 않고 “해당 없음”이나 “검토 필요”를 반환하게 설계할 수 있다.

| 닫힌 스키마가 막으려는 문제 | 설명 |
| --- | --- |
| 관계 이름이 계속 늘어남 | 같은 뜻인데 이름만 다른 관계를 줄인다 |
| 데이터마다 구조가 다름 | 모든 결과를 같은 형식으로 비교할 수 있다 |
| 허용하지 않은 정보가 섞임 | 필요한 범위만 그래프로 만든다 |

> **닫힌 스키마와 닫힌 세계 가정은 다른 말이다**
>
> 닫힌 스키마는 “사용할 수 있는 클래스와 관계의 목록을 제한한다”는 뜻이다. 닫힌 세계 가정은 “자료에 기록되지 않은 사실은 거짓으로 취급한다”는 별도의 가정이다.
>
> 예를 들어 공지에서 게시자를 찾지 못했다고 해서 게시자가 존재하지 않는다는 뜻은 아니다. 현재 자료에서 확인하지 못했다는 뜻일 수 있다.

### 작은 스키마 예시: 클래스 5종, 술어 7종

아래 예시는 학습 공지를 표현하는 작은 온톨로지 초안이다. 실제 도메인에 맞춰 이름과 범위를 정해야 한다.

| 종류 | 이름 | 뜻 |
| --- | --- | --- |
| 클래스 | Notice | 공지 하나 |
| 클래스 | StudyWeek | 학습 주차 하나 |
| 클래스 | Topic | 학습 주제 하나 |
| 클래스 | Material | 교재나 학습 자료 하나 |
| 클래스 | Person | 사람 한 명 |

| 술어 | 주어 → 목적어 | 뜻 |
| --- | --- | --- |
| announces | Notice → StudyWeek | 공지가 특정 주차를 알린다 |
| postedBy | Notice → Person | 사람이 공지를 게시했다 |
| hasTopic | StudyWeek → Topic | 주차에서 주제를 다룬다 |
| hasMaterial | StudyWeek → Material | 주차에서 자료를 사용한다 |
| supersedes | Notice → Notice | 새 공지가 이전 공지를 대체한다 |
| deadlineDate | StudyWeek → 날짜 값 | 주차의 마감 날짜다 |
| publishedAt | Notice → 날짜·시간 값 | 공지가 게시된 시각이다 |

앞의 다섯 술어는 다른 개체를 가리킨다. 마지막 두 술어는 날짜나 시각 같은 값, 즉 리터럴을 가리킨다. 이 구별을 해 두면 주어와 목적어가 어떤 종류여야 하는지 검사하기 쉬워진다.

### 관계 이름은 뜻과 사용 범위를 함께 정한다

hasTopic은 “어떤 대상을 주제로 다룬다”는 뜻이다. 이 관계가 무엇을 연결하는지도 정한다.

~~~text
주어: StudyWeek
술어: hasTopic
목적어: Topic
~~~

“공지의 작성자”와 “공지에 언급된 사람”은 서로 다른 관계다. 둘 다 Person을 가리키더라도 같은 술어로 합치면 “누가 작성했는가?”와 “누가 언급되었는가?”를 나눠 물을 수 없다.

## 4. RDFS로 용어의 기본 뜻을 적는다

RDFS(RDF Schema)는 RDF 용어의 기본 의미를 설명하는 표준이다. 클래스, 속성, 클래스 계층, 속성의 domain과 range를 표현할 수 있다.

아래는 앞의 미니 스키마 일부를 Turtle 문법으로 적은 예시다.

~~~turtle
@prefix ex:   <https://example.org/study/> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Notice a rdfs:Class ;
    rdfs:label "공지"@ko .

ex:StudyWeek a rdfs:Class ;
    rdfs:label "학습 주차"@ko .

ex:Topic a rdfs:Class ;
    rdfs:label "주제"@ko .

ex:hasTopic a rdf:Property ;
    rdfs:label "다루는 주제"@ko ;
    rdfs:domain ex:StudyWeek ;
    rdfs:range ex:Topic .
~~~

| 표기 | 쉽게 말하면 |
| --- | --- |
| rdfs:Class | 뒤에 적은 이름은 클래스다 |
| rdf:Property | 뒤에 적은 이름은 관계·속성이다 |
| rdfs:domain | 관계의 주어 쪽 종류를 알려준다 |
| rdfs:range | 관계의 목적어 쪽 종류를 알려준다 |
| rdfs:label | 사람이 읽을 이름을 붙인다 |

### Domain과 range는 검증 오류 규칙이 아니다

위 선언에서 hasTopic의 주어는 StudyWeek, 목적어는 Topic이라고 설명했다. RDFS의 의미에 따르면 다음 트리플에서 이 유형을 추론할 수 있다.

~~~text
week-05 — hasTopic → topic-rdf

추론할 수 있는 분류:
week-05는 StudyWeek다.
topic-rdf는 Topic이다.
~~~

여기서 중요한 점은 RDFS가 잘못된 값을 자동으로 거부하는 검사기가 아니라는 것이다. domain과 range는 유형을 추론하는 데 쓰인다. “값이 다르면 오류로 처리하라”는 검증은 SHACL 같은 별도의 규칙으로 작성한다.

| 기술 | 주된 역할 |
| --- | --- |
| RDFS | 용어의 뜻과 클래스·속성 사이의 기본 관계를 설명 |
| SHACL | 그래프가 정해진 구조와 조건을 만족하는지 검사 |
| JSON Schema | JSON 문서의 필드와 값의 형식을 검사 |

## 5. LLM 정보 추출은 사실 후보를 구조화한다

LLM 정보 추출은 문장 안에서 미리 정한 종류의 대상과 관계를 찾는 작업이다. 이때 LLM은 문장을 읽고 결과를 정해진 구조로 반환한다.

가상의 문장:

> W5에서는 RDF 직렬화를 공부한다.

사람이 읽은 결과:

~~~text
대상: week-05
관계: hasTopic
대상: topic-rdf-serialization
~~~

이를 트리플로 표현하면 다음과 같다.

~~~text
week-05 — hasTopic → topic-rdf-serialization
~~~

LLM은 문장을 자연어로 요약하는 대신, 어떤 대상이 어떤 관계로 연결되는지 항목별로 반환한다.

### JSON을 사용하는 이유

JSON은 데이터를 키와 값의 구조로 표현하는 형식이다. 결과를 일반 문장으로 받으면 프로그램이 문장을 다시 읽고 해석해야 한다. JSON으로 받으면 어떤 값이 대상 ID이고, 어떤 값이 관계인지 각 필드로 구분할 수 있다.

~~~json
{
  "source_id": "message-001",
  "entities": [
    {
      "id": "week-05",
      "type": "StudyWeek",
      "label": "W5"
    },
    {
      "id": "topic-rdf-serialization",
      "type": "Topic",
      "label": "RDF 직렬화"
    }
  ],
  "relations": [
    {
      "subject": "week-05",
      "predicate": "hasTopic",
      "object": "topic-rdf-serialization",
      "evidence": {
        "quote": "W5에서는 RDF 직렬화를 공부한다."
      }
    }
  ]
}
~~~

이 예시에서 subject는 관계의 시작 대상이고 object는 연결되는 대상이다. predicate는 둘 사이의 관계다. evidence는 이 관계를 뒷받침한다고 판단한 원문 구간이다.

### “형식이 맞다”와 “내용이 맞다”는 다르다

구조화 출력이 JSON 형식을 잘 지켰더라도 관계를 잘못 뽑았을 수 있다.

| 검사 | 확인하는 것 | 확인하지 못하는 것 |
| --- | --- | --- |
| JSON 문법 검사 | 괄호·쉼표 등 JSON 문법이 맞는가 | 관계가 실제 문장 뜻과 맞는가 |
| JSON Schema 검사 | 필드·자료형·허용 값이 맞는가 | 인용문이 원문에 실제로 있는가 |
| 원문 대조 | 주장과 근거가 문맥상 일치하는가 | 외부 세계의 사실까지 참인가 |

따라서 “JSON 출력에 성공했다”는 말은 결과 형식이 맞다는 뜻이지, 사실 검증까지 끝났다는 뜻이 아니다.

### 스키마 강제는 여러 층으로 나뉜다

“스키마를 강제한다”는 말은 한 가지 기술만을 가리키지 않는다.

| 층 | 무엇을 제한하는가 | 예 |
| --- | --- | --- |
| 추출 스키마 | 허용된 클래스와 관계 이름 | predicate는 hasTopic 등 목록 중 하나 |
| JSON Schema | JSON 객체의 구조와 값 | relations는 배열, predicate는 문자열 |
| RDFS | RDF 용어의 의미 | hasTopic은 StudyWeek와 Topic을 연결 |
| SHACL | 만들어진 그래프의 구조 | hasTopic 목적어는 Topic이어야 함 |
| 근거 확인 | 출력이 원문에 뿌리를 두는가 | quote가 출처 안에 존재하는가 |

각 층의 역할을 구분해야 한다. JSON Schema는 “문장 의미가 맞는가”를 판단하지 않는다. RDFS도 필수 JSON 필드나 개수 제한을 검사하지 않는다.

## 6. Few-shot: 예시를 보여 주고 같은 방식으로 답하게 한다

Few-shot은 모델에게 몇 개의 입력과 정답 예시를 함께 보여 주는 방법이다. 모델 자체를 새로 학습시키는 것과 다르다. 예시는 “어떤 표현을 어떤 구조로 바꾸어야 하는가”를 보여 준다.

| 예시 유형 | 입력 | 기대하는 처리 |
| --- | --- | --- |
| 명시적 관계 | W5에서 RDF를 공부한다 | W5 hasTopic RDF |
| 단순 언급 | RDF는 중요한 기술이다 | 특정 주차와 연결하지 않는다 |
| 부정 | W5에서 SPARQL을 공부하지 않는다 | 긍정 관계로 추출하지 않는다 |
| 수정 | W5 마감은 금요일에서 토요일로 바뀐다 | 과거와 새 값을 구별한다 |
| 불분명한 지시 | 그 자료는 다음 주에 다룬다 | 다음 주가 특정되지 않으면 추측하지 않는다 |

긍정 사례만 보여 주면 모델이 단순 언급이나 부정문까지 관계로 잘못 뽑을 수 있다. “무엇을 추출할지”와 함께 “무엇을 추출하지 않을지”도 예시로 설명하는 편이 좋다.

few-shot 예시는 실제로 사용할 스키마와 같은 클래스·술어 이름을 사용해야 한다. 같은 뜻에 여러 이름을 섞으면 출력이 다시 흔들린다. few-shot은 정확도를 보장하는 방법이 아니라, 원하는 작업 방식을 구체적으로 보여 주는 방법이다.

## 7. 근거 span은 “어느 부분을 보고 그렇게 판단했는가”를 가리킨다

**근거(evidence)**는 추출한 관계를 뒷받침하는 원문이다. **span**은 그중에서 선택한 연속된 글자 구간이다.

~~~text
원문: W5에서는 RDF 직렬화를 공부한다.
추출: week-05 — hasTopic → topic-rdf-serialization
근거 span: “W5에서는 RDF 직렬화를 공부한다.”
~~~

근거를 함께 저장하면 사람이 추출 결과를 원문과 비교할 수 있다. 문장이 부정인지, 조건이 붙었는지, 일정이 나중에 바뀌었는지도 확인하기 쉬워진다.

하지만 근거가 있다고 해서 주장이 무조건 참인 것은 아니다.

| 원문에서 확인되는 것 | 원문만으로 보장되지 않는 것 |
| --- | --- |
| 공지에 “마감은 토요일”이라고 적혀 있다 | 실제 마감일도 반드시 토요일이라는 사실 |
| 특정 사람이 공지를 게시했다 | 그 사람이 공지의 모든 내용을 작성했다는 사실 |

근거는 “이 자료가 이렇게 말한다”는 것을 보여 준다. 현실의 사실인지, 최신 정보인지는 출처의 권한과 시점도 확인해야 한다.

### 근거 위치를 안정적으로 보존하기

근거에는 보통 원문 ID, 인용 구간, 그리고 필요하다면 글자 위치를 함께 기록한다.

~~~json
{
  "source_id": "message-001",
  "quote": "W5에서는 RDF 직렬화를 공부한다.",
  "start": 0,
  "end": 20
}
~~~

위 숫자는 예시다. 실제 위치를 쓸 때는 시작과 끝의 기준을 정해야 한다. 보통 start는 구간이 시작되는 위치이고, end는 끝 바로 다음 위치로 정할 수 있다. 또한 원본 텍스트 기준인지, 줄바꿈과 공백을 정리한 텍스트 기준인지 기록해야 한다.

원문이 수정되면 위치 숫자는 더 이상 맞지 않을 수 있다. 그래서 원문 버전과 인용문도 함께 보존하는 것이 좋다. W3C Web Annotation은 인용문과 텍스트 위치를 가리키는 선택자 방식을 정의한다.

출처가 사적인 대화라면 근거 문장을 어디까지 복사해 보관할지, 누가 볼 수 있는지, 언제 삭제할지 정해야 한다. 근거를 남긴다는 이유로 원문 전체를 필요 이상 복제해서는 안 된다.

## 8. RDF를 파일로 표현하기: 직렬화

RDF 그래프는 데이터의 의미를 나타내는 모델이다. 다른 시스템으로 그래프를 보내려면 파일에 적을 문법이 필요하다. 이처럼 데이터를 파일이나 메시지로 표현하는 과정을 **직렬화**라고 한다.

| 구분 | 예 | 역할 |
| --- | --- | --- |
| RDF | 주어-술어-목적어 그래프 | 어떤 사실을 표현하는가 |
| Turtle | 사람이 읽기 쉬운 RDF 문법 | 그래프를 텍스트로 적는 방법 |
| JSON-LD | JSON 기반 RDF 문법 | JSON 구조와 RDF 의미를 함께 표현 |

“표준으로 내보낸다”는 것은 파일 확장자만 바꾸는 일이 아니다. 다른 프로그램이 같은 식별자, 관계, 값의 자료형을 읽어 같은 그래프로 이해할 수 있어야 한다.

## 9. Turtle로 그래프 읽기

~~~turtle
@prefix ex:   <https://example.org/study/> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

ex:week-05 a ex:StudyWeek ;
    ex:hasTopic ex:topic-rdf ;
    ex:deadlineDate "2026-10-08"^^xsd:date .

ex:topic-rdf a ex:Topic ;
    rdfs:label "RDF 직렬화"@ko .
~~~

한 줄씩 의미를 읽어 보자.

| 표기 | 의미 |
| --- | --- |
| @prefix ex: ... | 긴 IRI 앞부분을 ex라는 짧은 이름으로 쓴다 |
| a ex:StudyWeek | week-05는 StudyWeek라는 종류다 |
| ex:hasTopic ex:topic-rdf | week-05의 주제는 topic-rdf다 |
| ^^xsd:date | 뒤의 문자열을 날짜 값으로 해석한다 |
| @ko | 문자열이 한국어라는 언어 표시다 |

세미콜론은 같은 주어에 관계를 더 적는 기호다. 마침표는 그 주어에 대한 기록을 끝낸다. 접두어를 사용하면 긴 주소를 반복해서 쓰지 않아도 된다.

## 10. JSON-LD로 같은 정보를 표현하기

JSON-LD는 JSON 문법을 사용하면서, 각 키와 값이 RDF에서 어떤 의미인지 context로 알려 준다.

~~~json
{
  "@context": {
    "@base": "https://example.org/study/",
    "@vocab": "https://example.org/study/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "label": "rdfs:label",
    "hasTopic": { "@type": "@id" },
    "deadlineDate": { "@type": "xsd:date" }
  },
  "@graph": [
    {
      "@id": "week-05",
      "@type": "StudyWeek",
      "hasTopic": "topic-rdf",
      "deadlineDate": "2026-10-08"
    },
    {
      "@id": "topic-rdf",
      "@type": "Topic",
      "label": {
        "@value": "RDF 직렬화",
        "@language": "ko"
      }
    }
  ]
}
~~~

| JSON-LD 표기 | 역할 |
| --- | --- |
| @context | 용어와 값의 뜻을 연결한다 |
| @id | 대상의 식별자를 적는다 |
| @type | 대상의 클래스를 적는다 |
| @graph | 그래프에 포함할 대상을 나열한다 |
| @type: @id | 값이 문자열이 아니라 다른 대상의 ID임을 나타낸다 |
| @type: xsd:date | 값이 날짜 자료형임을 나타낸다 |

이 예시에서 @base와 @vocab은 짧은 이름이 어떤 기준 주소에 속하는지 정한다. JSON-LD를 RDF로 읽으면 앞 절의 Turtle과 같은 주어·관계·목적어를 얻는다.

### 일반 JSON과 JSON-LD는 무엇이 다른가

일반 JSON에는 키와 값만 있다. 다음 JSON만으로는 hasTopic이 어떤 관계인지 알 수 없다.

~~~json
{
  "hasTopic": "topic-rdf"
}
~~~

topic-rdf가 실제 대상의 ID인지, 그냥 화면에 표시할 글자인지도 정해져 있지 않다. JSON-LD는 context를 통해 hasTopic이 어떤 IRI인지, 값이 대상 ID인지 문자열인지 알려 준다.

| 일반 JSON | JSON-LD |
| --- | --- |
| 구조화된 키와 값 | 키와 값에 RDF 식별자·자료형 의미를 연결 |
| 애플리케이션이 각 필드 의미를 따로 알아야 함 | context로 용어 해석 규칙을 제공 |
| 그 자체만으로 RDF 그래프가 되지는 않음 | RDF 데이터 교환 형식으로 변환 가능 |

## 11. 내보낸 그래프의 의미가 보존되는가

표준 파일을 만들 때는 파일이 생성되는 것뿐 아니라, 다른 프로그램이 같은 그래프를 복원할 수 있는지 확인해야 한다.

| 확인할 것 | 필요한 이유 |
| --- | --- |
| 각 대상의 식별자가 안정적인가 | 서로 다른 대상이 잘못 합쳐지는 일을 막는다 |
| 관계와 리터럴을 구분했는가 | 대상 ID와 텍스트 값을 혼동하지 않는다 |
| 날짜·숫자의 자료형이 남아 있는가 | 값의 의미를 보존한다 |
| JSON-LD context를 함께 이해할 수 있는가 | 축약된 용어를 같은 IRI로 해석한다 |
| 다시 읽었을 때 트리플이 같은가 | 내보내기 전후의 의미가 유지되는지 확인한다 |

Turtle과 JSON-LD는 같은 그래프를 표현하는 서로 다른 문법이다. 저장소는 별개의 선택이다. Turtle 파일을 만들었다고 해서 자동으로 데이터베이스가 생기는 것은 아니다.

## 12. 스키마는 바뀔 수 있다

처음에는 필요 없던 관계가 나중에 필요해질 수 있다. 예를 들어 공지에 사용된 언어를 추가하고 싶을 수 있다. 새 관계를 추가해도 기존 RDF 트리플이 자동으로 바뀌지는 않는다. 다만 그 데이터를 읽는 프로그램이 새 관계를 무시하는지, 오류로 처리하는지는 프로그램의 규칙에 달려 있다.

| 변경 | 주의할 점 |
| --- | --- |
| 새 술어 추가 | 오래된 프로그램이 새 술어를 처리할 수 있는가 |
| 기존 술어 이름 변경 | 기존 데이터를 새 이름으로 바꾸거나 연결해야 하는가 |
| 기존 URI의 의미 변경 | 과거 데이터까지 다른 뜻으로 해석될 위험이 있는가 |

기존 URI의 뜻을 완전히 바꾸는 일은 피하는 편이 좋다. 같은 식별자는 같은 의미로 유지해야 한다. 개념이 달라졌다면 새 식별자를 만들고, 이전 개념과의 관계를 설명해야 한다.

이 문제는 DDIA 4장의 주제인 부호화와 스키마 발전에도 연결된다. 데이터를 만드는 프로그램과 읽는 프로그램이 서로 다른 시점에 바뀔 수 있으므로, 데이터 형식은 버전이 달라져도 어떻게 읽힐지 고려해야 한다.

## 참고 자료

- W3C, [RDF 1.1 Concepts and Abstract Syntax](https://www.w3.org/TR/rdf11-concepts/) — RDF 그래프, 트리플, IRI, 리터럴.
- W3C, [RDF Schema 1.1](https://www.w3.org/TR/rdf-schema/) — 클래스, 속성, domain, range.
- W3C, [RDF 1.1 Turtle](https://www.w3.org/TR/turtle/) — Turtle 문법.
- W3C, [JSON-LD 1.1](https://www.w3.org/TR/json-ld11/) — JSON-LD context와 RDF 변환.
- W3C, [SHACL](https://www.w3.org/TR/shacl/) — RDF 그래프 모양 검증.
- W3C, [Web Annotation Data Model](https://www.w3.org/TR/annotation-model/) — 텍스트 인용 구간과 위치 선택자.
- W3C, [PROV-O](https://www.w3.org/TR/prov-o/) — 데이터와 생성 과정의 출처 표현.
- JSON Schema, [Validation Specification 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation) — JSON 구조와 값 검증.
- Josifoski et al., [GenIE: Generative Information Extraction (NAACL 2022)](https://aclanthology.org/2022.naacl-main.342/) — 정해진 지식베이스 스키마에 맞춰 관계를 추출하는 연구.
- Brown et al., [Language Models are Few-Shot Learners (2020)](https://arxiv.org/abs/2005.14165) — 예시를 문맥에 제공하는 few-shot 학습 연구.
- Martin Kleppmann, [Designing Data-Intensive Applications, Chapter 4](https://dataintensive.net/) — 직렬화와 스키마 발전.
