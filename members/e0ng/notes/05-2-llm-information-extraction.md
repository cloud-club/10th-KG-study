---
title: LLM 정보 추출
date: 2026-09-30
tags: [llm, triple-extraction, information-extraction, knowledge-graph]
status: in-progress
---

## LLM 정보 추출

정해둔 온톨로지 스키마에 맞춰 LLM이 자동으로 관계를 추출한다

```
Notion 문서
   ↓ LLM 정보 추출
정해진 JSON 형식의 개체·관계·근거
   ↓ 변환
RDF 트리플 또는 지식 그래프
```

```
2026년 여름방학에 Naver가 주관한 NIPA-NAVER Cloud PBL에 참여했다.
프로젝트에서 Naver Cloud를 사용해 AI 서비스를 개발했다.
```

⬇️ 정보 추출

```
NIPA-NAVER Cloud PBL ──rdf:type──────────────▶ Activity
NIPA-NAVER Cloud PBL ──occursInPeriod────────▶ 2026년 여름방학
NIPA-NAVER Cloud PBL ──relatedToOrganization─▶ Naver
문서 ──schema:about──────────────────────────▶ Naver Cloud
```

### 스키마 강제 - JSON 출력

자유로운 문장이 아닌,
프로그램이 처리할 수 있는 정해진 JSON 구조로 출력하도록 제한

- 스키마 → LLM 출력의 JSON 형식
- JSON의 필드를 온톨로지의 클래스 / 술어와 맞춤
- 필드 누락과 이름 변형 방지
- RDF 변환 용이

```json
{
  "activity": {
    "name": "NIPA-NAVER Cloud PBL",
    "period": "2026년 여름방학",
    "organization": "Naver",
    "status": null,
    "activity_kind": "프로젝트",
    "activity_scope": null
  },
  "document": {
    "title": "NIPA-NAVER Cloud PBL",
    "topics": [
      {
        "id": "topic:naver-cloud",
        "type": "Topic",
        "name": "Naver Cloud"
      },
      {
        "id": "topic:ai-service",
        "type": "Topic",
        "name": "AI 서비스"
      }
    ]
  }
}
```

### few-shot

프롬프트 안에 입력과 올바른 출력 예시 몇 개를 제공하는 방법

- LLM이 예시와 같은 판단 기준과 출력 형식을 따르게 함

입력 :

```
2026년 여름방학에 Naver가 주관한 NIPA-NAVER Cloud PBL에 참여했다.
프로젝트에서 Naver Cloud를 사용해 AI 서비스를 개발했다.
```

출력 :

```json
{
  "activity": {
    "name": "NIPA-NAVER Cloud PBL",
    "period": "2026년 여름방학",
    "organization": "Naver",
    "status": null,
    "activity_kind": "프로젝트",
    "activity_scope": null
  },
  "document": {
    "title": "NIPA-NAVER Cloud PBL",
    "topics": [
      {
        "id": "topic:naver-cloud",
        "type": "Topic",
        "name": "Naver Cloud"
      },
      {
        "id": "topic:ai-service",
        "type": "Topic",
        "name": "AI 서비스"
      }
    ]
  }
}
```

위의 예시로 알려줄 수 있는 것은 다음과 같다

- `NIPA-NAVER Cloud PBL`을 활동으로 추출
- `2026년 여름방학`을 활동 기간으로 추출
- `Naver`는 관련 조직, `NIPA-NAVER Cloud PBL`은 활동으로 구분
- 활동 종류를 `프로젝트`로 분류
- 문서에 활동 범위가 없으면 `activity_scope`를 `null`로 처리
- 문서에 없는 진행 상태는 추측하지 않고 `null` 처리
- 하나의 문서에서 여러 주제가 나오면 `Naver Cloud`, `AI 서비스`처럼 각각 분리해 출력

### 근거 스팬 Evidence span

추출한 값마다 원문에서 그 판단 근거가 된 정확한 문구를 함께 저장

- 문구 뿐만 아니라 원문의 위치도 함께 저장 가능
- LLM이 문서에 없는 정보를 추측했는지 확인
- 잘못 추출한 관계를 사람이 검토
- 지식 그래프의 사실이 어디에서 나왔는지 추적

```json
{
  "period": {
    "value": "2026년 여름방학",
    "evidence": "2026년 여름방학에"
  },
  "organization": {
    "value": "Naver",
    "evidence": "Naver가 주관한"
  },
  "topics": [
    {
      "id": "topic:naver-cloud",
      "type": "Topic",
      "name": "Naver Cloud",
      "evidence": "Naver Cloud를 사용해"
    }
  ]
}
```
