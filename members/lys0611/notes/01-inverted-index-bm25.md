---
title: 역색인과 BM25 — 카톡 검색에 대입해 보기
date: 2026-09-09
tags: [inverted-index, tf-idf, bm25, elasticsearch, lucene, nori, tokenization, ngram, korean]
status: done
---

# 01. 역색인과 BM25 — 카톡 검색에 대입해 보기

카톡에서 `마감 일정`을 검색해 문자열 검색, BM25, 벡터가 가져오는 결과를 비교했다. 같은 데이터여도 질문을 어떻게 해석하고 어떤 단위로 검색하느냐에 따라 결과가 달랐다.

## 문자열 검색의 한계

`ILIKE '%마감 일정%'`은 두 단어가 붙어 있는 메시지만 찾는다. 내 데이터에는 없어서 0건이었다. `마감`, `데드라인`, `제출일`, `언제까지`는 비슷한 뜻이어도 서로 다른 문자열이다.

`pg_trgm` 인덱스로 부분 검색을 빠르게 할 수는 있다. 다만 인덱스를 붙인다고 이 쿼리가 동의어를 찾거나 관련도순으로 정렬되지는 않는다. 별도의 trigram 유사도 검색도 철자 유사성을 보는 것이지 의미를 이해하는 것은 아니다.

## 역색인과 BM25

역색인은 토큰마다 그 토큰이 나온 문서 목록(postings)을 저장한다.

```text
d1: 부산 숙소 예약했어요
d2: 숙소는 내가 알아볼게
d3: 부산 언제 갈까

부산 → d1, d3
숙소 → d1, d2
예약 → d1
```

검색할 때는 본문 전체 대신 해당 토큰의 목록을 읽어 합치거나 교차한다. 위치 정보도 저장하면 단어 순서와 간격을 따지는 구문 검색이 가능하다.

BM25는 여기에 순위를 매긴다. 문서에 자주 나오는 검색어는 점수를 올리되, 반복 효과를 점점 줄이고 문서 길이도 보정한다. 여러 문서에 흔한 단어보다 드문 단어에 높은 가중치를 준다. 한 토큰의 점수는 보통 다음 식으로 설명한다.

```text
score(t, D) = IDF(t) × tf × (k1 + 1)
             / (tf + k1 × (1 - b + b × |D| / avgdl))

IDF(t) = ln(1 + (N - n(t) + 0.5) / (n(t) + 0.5))
```

`tf`는 문서 내 빈도, `|D|`는 문서 길이, `avgdl`은 평균 길이다. `N`은 문서 수, `n(t)`는 토큰 t를 포함한 문서 수다. Elasticsearch 기본값은 빈도 포화를 조절하는 `k1=1.2`, 길이 보정을 조절하는 `b=0.75`다. TF-IDF도 로그 TF 등으로 반복 효과를 줄일 수 있으므로, 포화 여부만으로 둘을 구분하지는 않는다. ([Similarity 설정](https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity))

실제 점수를 식과 대조할 때는 구현 차이도 봐야 한다. Lucene은 위 분자의 `(k1 + 1)`을 생략한다. 같은 설정의 단일 필드에서는 공통 상수라 순위가 같지만, 점수 숫자까지 같지는 않다. ([변경 기록](https://github.com/apache/lucene/blob/main/lucene/MIGRATE.md))

## 한국어 토큰화

기본 `text` 필드는 Nori를 쓴다. `decompound_mode=mixed`로 복합명사의 원형과 분해형을 함께 남기고, 품사 필터로 조사·어미 등을 제거했다. 프로젝트명처럼 잘못 잘리는 고유어는 사용자 사전으로 보완할 수 있다. ([Nori tokenizer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer))

보조 필드 `text.ngram`은 2~3글자 조각을 저장한다. 실습 분석기에 같은 문장을 넣은 결과다.

```text
입력: 부산숙소 예약했어요

Nori
['부산', '숙소', '예약']

n-gram
['부산', '부산숙', '산숙', '산숙소', '숙소',
 '예약', '예약했', '약했', '약했어', '했어', '했어요', '어요']
```

n-gram은 이름 일부나 사전에 없는 말을 찾는 데 쓸 수 있지만 `산숙`, `약했` 같은 조각도 만든다. 기본 검색은 Nori로 두고, 부분 문자열 검색이 필요한 경우에 보조 필드를 비교해 볼 생각이다. n-gram만 붙인다고 오타나 초성 검색까지 해결되는 것은 아니다.

## `마감 일정` 검색 결과

팀리더 방의 W2 실행 기록이다.

| 방식 | 결과 | 내용 |
|---|---|---|
| 문자열 `ILIKE` | 0건 | 두 단어가 붙은 메시지 없음 |
| BM25 | 1위 `#1908` (7.12) | 일반 일정 조율 |
| BM25 | 2위 `#1463` (7.00) | 마감 논의 |
| 벡터 | 1위 `#1653` (0.592) | 제출일 논의 |
| 벡터 | 2위 `#1695` (0.573) | 언제까지 완성할지 질문 |

BM25에서 마감 논의보다 일반 일정이 먼저 나온 데는 쿼리 설정도 영향을 줬다. `match`의 기본 연산자가 OR라 두 토큰 중 하나만 있어도 후보가 된다. 이 질문에서는 `operator: and`나 `minimum_should_match: 2`로 둘 다 요구할 수 있다. `match_phrase`는 토큰의 순서와 간격까지 보므로 다른 조건이다. ([match query](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-match-query))

조건을 엄격하게 해도 `제출일`처럼 다른 표현을 놓치는 문제는 남는다. BM25와 벡터의 상위 5개 중 공통 청크는 `#1463` 하나였다. 전체 비교는 [W2 결과](../labs/01-ingest/README.md)에 남겼다.

## 더 해볼 것

- OR, AND, 구문 검색에서 어떤 정답이 빠지고 오탐이 줄어드는지 비교하기.
- 프로젝트명을 Nori 사용자 사전에 넣기 전후 토큰 확인하기.
- 두 검색기의 점수는 척도가 다르므로, [RRF](04-hybrid-search-rrf-recall.md)로 순위를 합쳐 비교하기.

## 참고

- Lucene, [BM25Similarity](https://lucene.apache.org/core/10_2_2/core/org/apache/lucene/search/similarities/BM25Similarity.html)
- PostgreSQL, [pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html)
