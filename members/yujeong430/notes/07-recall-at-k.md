---
title: Recall@k - 필요한 문서를 상위 결과에서 놓치지 않았는가
date: 2026-09-16
tags: [search, evaluation, recall-at-k]
status: done
---

# Recall@k - 필요한 문서를 상위 결과에서 놓치지 않았는가

## 한 줄 요약

Recall@k는 “정답으로 정한 관련 문서 전체 중, 검색 결과 상위 `k`개 안에 들어온 문서의 비율”이다.

## 먼저 필요한 것: 관련성 판정

Recall@k는 검색 결과만 보고 자동으로 계산할 수 없다. 각 질문마다 어떤 문서가 관련 있는지 사람이 먼저 정해야 한다. 이 목록을 관련성 판단(relevance judgment) 또는 평가셋이라고 한다.

```text
질문: “학기재수강 신청 기간은?”
관련 문서(정답): [공지 A, 공지 B]  -> 총 2개
검색 상위 5개:      [공지 C, 공지 A, 공지 D, 공지 B, 공지 E]
```

위 예에서는 관련 문서 2개를 모두 상위 5개에서 찾았으므로 Recall@5는 `2 / 2 = 1.0`이다.

## 수식

```text
Recall@k = (상위 k개 안에서 찾은 관련 문서 수) / (전체 관련 문서 수)
```

- 1.0: 관련 문서를 하나도 놓치지 않았다.
- 0.5: 관련 문서의 절반만 상위 k개에 들어왔다.
- 0.0: 상위 k개 안에 관련 문서가 없다.

## 왜 RAG에서 중요할까

RAG의 LLM은 검색 결과로 전달받은 문서만 읽는다. 필요한 문서가 상위 `k`개 안에 없다면, 답변 단계는 그 근거를 사용할 수 없다. 그래서 키워드·벡터·하이브리드 검색을 비교할 때 먼저 Recall@k를 보면 “어떤 검색기가 필요한 근거를 더 빠뜨리지 않는가”를 알 수 있다.

## Recall@k가 말해 주지 않는 것

Recall@k는 상위 `k`개 안에 관련 문서가 **있기만 하면** 같은 점수를 준다. 1위에 있든 k위에 있든 차이를 보지 않는다. 또한 관련 없는 문서가 많이 섞여도 Recall@k만으로는 알 수 없다.

따라서 함께 알아둘 지표는 Precision@k다.

```text
Precision@k = (상위 k개 안의 관련 문서 수) / k
```

검색 결과를 LLM에 적은 수만 전달하는 RAG에서는, 필요한 문서를 놓치지 않는 Recall과 잡음을 줄이는 Precision을 함께 보는 편이 좋다.

## 비교를 공정하게 하는 조건

세 검색 방식을 비교할 때는 다음을 고정한다.

- 같은 질문 목록
- 같은 관련 문서 판정 목록
- 같은 `k`값 (예: 모두 Recall@5)
- 같은 문서 청크 집합

검색 결과가 달라진 이유를 비교하려면 평가 조건도 같아야 한다.

## 참고 자료

- [Elasticsearch ranking evaluation: Recall at K](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/search-rank-eval.html) - Recall@k의 공식 정의와 계산 예시
- [Elasticsearch: relevance judgments](https://www.elastic.co/search-labs/blog/judgment-lists-search-query-relevance-elasticsearch) - 질문별 관련성 판단 목록을 이용한 평가 예시
