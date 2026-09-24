---
title: RAGAS로 RAG 시스템 평가하기
tags: [rag, ragas, evaluation, faithfulness, context-recall, factual-correctness]
status: done
---

# RAGAS로 RAG 시스템 평가하기

## 한 줄 요약

RAG 시스템은 검색 결과만 맞는다고 끝나지 않는다. **필요한 근거를 빠짐없이 검색했는지**, **답변이 검색 근거에서 벗어나지 않았는지**, **기준 정답과 비교해 사실이 맞는지**를 각각 평가해야 한다. RAGAS는 이 평가 관점을 지표로 나누어 제공하는 프레임워크다.

이 프로젝트에서는 다음 세 지표를 중심으로 정리한다.

| 지표 | 비교 대상 | 확인하려는 것 |
|---|---|---|
| Context Recall | 기준 정답 ↔ 검색 문맥 | 답에 필요한 정보를 검색기가 빠뜨리지 않았는가? |
| Faithfulness | 생성 답변 ↔ 검색 문맥 | 답변의 주장들이 가져온 근거로 뒷받침되는가? |
| Factual Correctness | 생성 답변 ↔ 기준 정답 | 답변이 기준 정답과 사실적으로 일치하는가? |

## 왜 검색 평가와 답변 평가를 나눠야 하나

기존 평가 화면의 `Hit@3`과 `MRR`은 **검색기**를 평가한다.

- `Hit@3`: 정답 문서가 상위 3개 결과 안에 하나라도 들어왔는가?
- `MRR`: 첫 번째 정답 문서가 얼마나 높은 순위에 나왔는가?

하지만 정답 문서를 잘 가져와도 LLM이 근거에 없는 내용을 덧붙일 수 있다. 반대로 답변 모델이 좋아도 검색기가 핵심 문서를 놓치면 완전한 답을 만들 수 없다. 따라서 전체 RAG 파이프라인은 다음처럼 나눠서 본다.

```text
질문
  │
  ▼
검색기 ── 검색 문맥(retrieved_contexts) ──▶ 답변 생성기 ──▶ 생성 답변(response)
  │                                            │
  ├─ Hit@3 / MRR                               ├─ Faithfulness
  └─ Context Recall                            └─ Factual Correctness
```

## 평가 데이터 한 건의 구조

RAGAS 평가 한 건을 만들려면 역할이 다른 네 값이 필요하다.

| 필드 | 이 프로젝트에서 가져오는 곳 | 예시 |
|---|---|---|
| `user_input` | `queries.jsonl`의 `query` | 인증서 갱신 후 무엇을 검증해야 하나? |
| `retrieved_contexts` | BM25·Vector·Hybrid·Graph가 반환한 청크 본문 | 갱신 절차, 장애 기록 청크 |
| `response` | Worklog Copilot이 생성한 답변 | static Pod 재시작 후 노드별 `/readyz`를 확인한다. |
| `reference` | `answer_points`를 문장으로 조립한 기준 정답 | 갱신만으로 파일을 다시 읽지 않음. 노드별 확인 필요. |

`expected_primary`와 `expected_supporting`은 검색 평가용 문서 ID이고, `answer_points`는 답변 평가용 기준 사실이다. 같은 질문셋을 검색 평가와 RAGAS 평가에 함께 사용할 수 있도록 설계했다.

## 1. Context Recall

Context Recall은 기준 정답을 만드는 데 필요한 주장 중 검색 문맥이 얼마나 많이 포함했는지 측정한다.

```text
Context Recall
= 검색 문맥으로 뒷받침할 수 있는 기준 정답의 주장 수
  / 기준 정답의 전체 주장 수
```

예를 들어 기준 정답에 다음 세 항목이 있다고 가정한다.

1. 인증서 갱신만으로는 static Pod가 새 파일을 읽지 않는다.
2. manifest를 잠시 옮겨 static Pod를 재시작한다.
3. 각 노드의 `/readyz`를 확인한다.

검색 문맥에 1번과 2번만 있다면 Context Recall은 낮아진다. 답변을 아직 생성하기 전에도 검색 단계의 누락을 발견할 수 있는 지표다.

## 2. Faithfulness

Faithfulness는 생성 답변을 작은 주장으로 나눈 뒤 각 주장이 검색 문맥에서 직접 뒷받침되는지 확인한다.

```text
Faithfulness
= 검색 문맥으로 뒷받침되는 생성 답변의 주장 수
  / 생성 답변의 전체 주장 수
```

예를 들어 검색 문맥에는 `/readyz` 확인만 있는데 답변이 “모든 인증서는 1년마다 자동 갱신된다”고 덧붙였다면, 그 주장은 근거가 없으므로 Faithfulness가 낮아진다. 즉 **환각이나 근거 밖 확장**을 찾는 데 유용하다.

중요한 점은 Faithfulness가 정답 여부 자체를 보장하지 않는다는 것이다. 잘못된 문서만 검색했는데 답변이 그 문서에 충실하면 Faithfulness는 높을 수 있다.

## 3. Factual Correctness

Factual Correctness는 생성 답변과 기준 정답을 각각 주장으로 나누고 사실의 겹침을 비교한다.

- TP: 답변과 기준 정답에 모두 있는 주장
- FP: 답변에는 있지만 기준 정답에는 없는 주장
- FN: 기준 정답에는 있지만 답변이 빠뜨린 주장

기본적인 F1 관점에서는 정확성(precision)과 완전성(recall)을 함께 본다.

```text
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 × Precision × Recall / (Precision + Recall)
```

따라서 그럴듯하지만 틀린 내용을 추가해도 점수가 내려가고, 중요한 정답 항목을 빠뜨려도 점수가 내려간다.

## 세 지표를 함께 해석하기

| 상황 | Context Recall | Faithfulness | Factual Correctness | 해석 |
|---|---:|---:|---:|---|
| 필요한 문서를 놓침 | 낮음 | 높을 수도 있음 | 낮음 | 검색기 개선 필요 |
| 근거는 충분하지만 답변이 지어냄 | 높음 | 낮음 | 낮음 | 프롬프트·답변 모델 개선 필요 |
| 잘못된 문서를 충실히 요약함 | 낮음 | 높음 | 낮음 | Faithfulness만 보면 놓치는 실패 |
| 필요한 근거로 정확히 답함 | 높음 | 높음 | 높음 | 바람직한 상태 |

## 이 프로젝트에 적용하는 방법

1. `queries.jsonl`에서 질문과 `answer_points`를 읽는다.
2. 각 검색 모드로 상위 청크를 가져와 `retrieved_contexts`를 만든다.
3. 동일한 프롬프트와 답변 모델로 `response`를 생성한다.
4. `answer_points`를 기준 정답 `reference`로 사용한다.
5. Context Recall, Faithfulness, Factual Correctness를 계산한다.
6. 질문별 점수와 검색 모드별 평균을 함께 비교한다.

비교 시에는 한 번에 검색기와 답변 모델을 모두 바꾸지 않는다. 예를 들어 BM25와 Hybrid를 비교할 때는 답변 모델·프롬프트·근거 수를 동일하게 고정해야 검색 방식의 영향을 해석할 수 있다.

## 현재 구현 범위와 다음 단계

현재 Worklog Copilot의 평가 화면에는 다음이 구현되어 있다.

- 19개 질문의 `Hit@3`, `MRR` 검색 평가
- RAGAS 세 지표의 비교 대상과 의미 설명
- 각 질문의 `user_input`, `reference`, 정답 문서 미리보기

실제 RAGAS 점수 계산은 평가용 LLM 호출 비용과 실행 시간이 발생하므로 자동 실행하지 않는다. 다음 단계에서는 사용자가 명시적으로 실행할 때만 19문항의 답변을 생성하고 RAGAS 점수를 계산하도록 분리한다.

## 참고 자료

- [RAGAS 공식 지표 목록](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/)
- [RAGAS Context Recall](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/)
- [RAGAS Factual Correctness](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/factual_correctness/)
- [RAG 시스템 평가 예제](https://docs.ragas.io/en/latest/getstarted/rag_eval/)
