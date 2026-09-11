---
title: 역색인과 BM25 — 카톡 검색에 대입해 보기
date: 2026-09-09
tags: [inverted-index, tf-idf, bm25, elasticsearch, lucene, nori, tokenization, ngram, korean]
status: done
---

# 01. 역색인과 BM25 — 카톡 검색에 대입해 보기

이번 실습에서 먼저 확인하고 싶었던 것은 단순했다. 카톡에서 `마감 일정`을 찾을 때 문자열 검색, BM25, 벡터 검색은 실제로 무엇을 다르게 가져오는가? 세 방법에 같은 질문을 던져 보니 차이는 검색 알고리즘보다도 “문서를 어떤 단위로 자르고, 질문을 어떤 토큰으로 해석했는가”에서 먼저 나타났다.

## 문자열 검색에서 막힌 지점

`ILIKE '%마감 일정%'`은 두 단어가 그 순서로 붙어 있는 문자열만 찾는다. 내 데이터에는 그런 메시지가 없어서 결과가 0건이었다. `마감`, `데드라인`, `제출일`, `언제까지`가 사람에게는 비슷한 말이어도 문자열 검색에는 전부 다른 값이다.

속도와 검색 품질도 구분해야 한다. `pg_trgm` 같은 인덱스는 부분 문자열 검색을 빠르게 만들 수 있지만, 동의어를 이해하거나 결과에 관련도 순위를 붙여 주지는 않는다. “grep이 느리다”보다 “표현이 조금만 달라도 못 찾고, 찾은 뒤 무엇이 더 중요한지도 모른다”가 이번 데이터에서 더 큰 한계였다.

## 역색인은 문서를 뒤집어 저장한다

문서를 매번 처음부터 읽는 대신, 역색인은 토큰별로 그 토큰이 나온 문서 목록(postings)을 저장한다.

```text
d1: 부산 숙소 예약했어요
d2: 숙소는 내가 알아볼게
d3: 부산 언제 갈까

부산 → d1(pos 0), d3(pos 0)
숙소 → d1(pos 1), d2(pos 0)
예약 → d1(pos 2)
```

질의가 들어오면 해당 토큰의 postings만 읽어 합치거나 교차한다. 실제 비용은 토큰 수 하나로 정해지는 것이 아니라 postings 길이, 교집합 방식, 상위 몇 건을 뽑는지 등에 따라 달라지지만, 적어도 모든 문서 본문을 훑는 방식은 아니다. 위치 정보가 있으면 단어의 순서와 인접 여부를 보는 구문 검색이나 하이라이트도 가능하다.

Lucene은 이 색인을 불변 세그먼트로 기록하고 작은 세그먼트를 나중에 병합한다. Elasticsearch의 `refresh`는 새 세그먼트를 검색 가능한 상태로 열어 주는 작업이다. 기본 설정에서는 대체로 1초 주기로 갱신되지만, 최근 30초 동안 검색 요청이 있었던 인덱스라는 조건도 있다. 이번 실습 코드는 대량 색인이 끝난 뒤 `indices.refresh()`를 직접 호출하므로, 이어지는 확인 쿼리가 주기적 refresh를 기다리지 않는다.

## BM25 점수를 읽는 법

BM25는 역색인에서 찾은 후보에 관련도 점수를 준다. 흔히 쓰는 한 토큰의 식은 다음과 같다.

```text
score(t, D) = IDF(t) × tf × (k1 + 1)
                         ───────────────────────────────────
                         tf + k1 × (1 - b + b × |D| / avgdl)

IDF(t) = ln(1 + (N - n(t) + 0.5) / (n(t) + 0.5))
```

여기서 `tf`는 문서 안의 토큰 빈도, `|D|`는 문서 길이, `avgdl`은 평균 문서 길이다. `k1`은 단어가 반복될 때 점수가 얼마나 빨리 포화되는지, `b`는 문서 길이를 얼마나 보정할지를 조절한다. Elasticsearch의 BM25 기본값은 `k1=1.2`, `b=0.75`다.

BM25를 “TF-IDF와 달리 빈도를 포화시킨다”라고만 외우면 조금 거칠다. TF-IDF도 구현에 따라 로그 TF처럼 반복 효과를 줄일 수 있다. 다만 BM25의 식에는 포화와 길이 정규화가 명시적으로 들어 있고, 그래서 긴 청크나 같은 단어를 여러 번 쓴 청크를 다루는 방식이 더 분명하다.

위 식은 설명할 때 많이 쓰는 형태다. 현재 Lucene의 `BM25Similarity`는 분자의 `(k1 + 1)`을 생략한다. 같은 필드 안에서는 모든 문서에 공통으로 곱해지는 값이라 순위는 바뀌지 않는다. 여러 필드에 서로 다른 BM25 설정을 섞는 경우에는 점수 크기까지 완전히 같다고 볼 수는 없다.

## 한국어에서는 분석기가 먼저다

BM25는 문자열이 아니라 분석기가 만든 토큰을 센다. 한국어 카톡은 조사와 어미가 붙고 띄어쓰기도 자주 흔들리므로, 공백만 기준으로 잘라서는 부족하다.

이번 인덱스의 기본 `text` 필드는 Nori를 사용한다. `decompound_mode=mixed`로 복합명사의 원형과 분해형을 함께 남기고, `nori_part_of_speech`로 조사·어미 등 기본 stop tag를 제거했다. 팀명이나 서비스명처럼 사전에 없는 고유어가 계속 잘못 잘리면 `user_dictionary`를 추가하는 쪽이 무작정 n-gram 범위를 넓히는 것보다 관리하기 쉽다.

보조 필드인 `text.ngram`은 2~3글자 조각을 저장한다. 사전에 없는 신조어와 이름 일부를 찾는 데 도움이 되지만, 토큰 수와 오탐도 함께 늘어난다. 로컬 분석기로 같은 문장을 넣어 보니 차이가 선명했다.

```text
입력: 부산숙소 예약했어요

korean(nori)
['부산', '숙소', '예약']

korean_ngram(2~3글자)
['부산', '부산숙', '산숙', '산숙소', '숙소',
 '예약', '예약했', '약했', '약했어', '했어', '했어요', '어요']
```

Nori는 `예약했어요`를 의미 있는 어간인 `예약`으로 정리했다. n-gram은 `산숙`, `약했`처럼 의미 없는 조각도 함께 만든다. 그래서 일반 문장은 Nori, 철자 일부·별명·신조어 같은 예외는 n-gram 보조 필드로 실험해 보는 구성이 적당해 보인다.

## `마감 일정` 검색 결과

실제 팀리더 방에 같은 질문을 던진 결과는 다음과 같았다.

| 방식 | 상위 결과 | 메모 |
|---|---|---|
| 문자열 `ILIKE '%마감 일정%'` | 0건 | 두 단어가 붙어 있는 메시지가 없음 |
| BM25 + Nori | 1위 `#1908`, 7.12 | 일정 조율 내용. `match`의 기본 연산자가 OR라 `일정`만으로도 높은 점수를 받음 |
| BM25 + Nori | 2위 `#1463`, 7.00 | 실제 마감 관련 내용 |
| 벡터 | 1위 `#1653`, 0.592 | `제출일`을 논의한 청크 |
| 벡터 | 2위 `#1695`, 0.573 | `언제까지 완성`할지를 묻는 청크 |

BM25 결과가 이상하다기보다 쿼리가 생각보다 느슨했다. Elasticsearch `match` 쿼리의 기본 연산자는 OR라서 두 토큰 중 하나만 있어도 후보가 된다. `operator: and`나 `minimum_should_match: 2`를 쓰면 두 토큰을 모두 요구할 수 있다. `match_phrase`는 여기서 한 단계 더 나아가 분석된 토큰의 순서와 인접성까지 본다. 세 옵션을 같은 것으로 취급하면 안 된다.

반대로 조건을 엄격하게 해도 `제출일`이나 `언제까지` 같은 표현 불일치는 해결되지 않는다. 이 부분은 벡터가 잘 잡았다. BM25와 벡터의 상위 5개 중 공통 청크는 `#1463` 하나뿐이었다. 둘 중 하나가 무조건 낫다기보다, 서로 다른 실패를 한다는 쪽에 가깝다.

## 다음에 확인할 것

- `operator: and`, `minimum_should_match`, `match_phrase`를 나눠 실행하고 정밀도와 재현율 변화를 기록한다.
- 실제 별명과 프로젝트명을 Nori 사용자 사전에 넣기 전후의 토큰을 비교한다.
- `text`와 `text.ngram`을 각각 검색해 초성체·오타·이름 일부에서 어느 쪽이 도움이 되는지 본다.
- BM25 점수와 코사인 유사도는 단위와 분포가 다르므로 직접 더하지 않고, 3주차에는 순위 기반 RRF로 합친다.

## 확인한 자료

- Robertson et al., [Okapi at TREC-3](https://trec.nist.gov/pubs/trec3/t3_proceedings.html)
- Apache Lucene, [BM25Similarity](https://lucene.apache.org/core/10_2_2/core/org/apache/lucene/search/similarities/BM25Similarity.html) · [BM25의 `(k1+1)` 변경 기록](https://github.com/apache/lucene/blob/main/lucene/MIGRATE.md)
- Elastic, [Similarity settings](https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity) · [`match` query](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-match-query)
- Elastic, [Nori tokenizer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer) · [n-gram tokenizer](https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-ngram-tokenizer.html)
- Elastic, [Near real-time search와 refresh](https://www.elastic.co/docs/manage-data/data-store/near-real-time-search)
