---
title: 1세대 검색 - 역색인과 BM25 키워드 검색
date: 2026-09-09
tags: [search, inverted-index, tf-idf, bm25, elasticsearch, korean-nlp]
status: done
---

# 1세대 검색 - 역색인과 BM25 키워드 검색

## 한 줄 요약

키워드 검색은 문서를 토큰으로 나누고 `토큰 -> 그 토큰을 가진 문서들`이라는 역색인을 만든다. BM25는 검색어 토큰의 빈도·희소성·문서 길이를 이용해 문서 청크를 관련도 순으로 정렬한다.

## 저장 구조: 역색인

검색 엔진은 문서를 적절한 단위로 나눈 뒤, 각 단위를 문서(document)로 저장한다. Elasticsearch 같은 검색 엔진은 분석기(analyzer)로 텍스트를 토큰화하고 역색인을 만든다.

```text
문서 17: "학기재수강 신청 기간 안내"
문서 42: "수강 신청 정정 공지"

역색인 예시
"신청"    -> [문서 17, 문서 42, ...]
"재수강"  -> [문서 17, ...]
"기간"    -> [문서 17, ...]
```

역색인에는 보통 문서 ID뿐 아니라 토큰 빈도와 위치도 함께 기록된다. 그래서 전체 원문을 매번 훑지 않고, 질의 토큰을 가진 후보 문서만 빠르게 모을 수 있다. 관계를 뒤집어 저장한다는 점에서 역색인은 문서-토큰 행렬의 전치 형태로도 이해할 수 있다.

## 질의 처리 흐름

문서를 인덱싱할 때만 토큰화하는 것이 아니다. 질의도 **같은 분석기**로 토큰화해야 문서의 토큰과 비교할 수 있다.

```text
문서 분석: "재수강 신청" -> [재수강, 신청] -> 역색인 생성
질의 분석: "재수강 기간" -> [재수강, 기간] -> posting list 조회
후보 결합: 재수강과 기간을 가진 문서 후보 생성
순위화: 후보마다 BM25 점수를 계산해 정렬
```

여기서 `AND`/`OR` 같은 불리언 조건은 후보를 좁히는 역할을 하고, BM25는 남은 후보의 우선순위를 정하는 역할을 한다. 필터링과 순위화는 서로 다른 문제다.

## TF-IDF에서 BM25로

TF-IDF의 직관은 간단하다.

- **TF(term frequency)**: 어떤 단어가 한 문서에서 많이 나올수록 그 문서와 더 관계있을 수 있다.
- **IDF(inverse document frequency)**: 너무 많은 문서에 나오는 단어보다 드문 단어가 더 구별력이 있다.

하지만 단순 TF-IDF는 단어가 반복될수록 점수가 계속 커지고, 긴 문서가 불리하거나 유리해지는 문제를 충분히 조절하기 어렵다. BM25는 TF 증가를 포화시키고 문서 길이를 보정한 대표적인 확률적 순위 함수다. 핵심 항은 다음처럼 쓸 수 있다.

```text
score(D, Q) = Σ IDF(q) × f(q, D) × (k1 + 1)
                       ─────────────────────────────
                       f(q, D) + k1 × (1 - b + b × |D| / avgdl)
```

- `f(q, D)`: 토큰 `q`가 문서 `D`에 등장한 횟수
- `|D|`, `avgdl`: 문서 길이와 평균 문서 길이
- `k1`: TF가 얼마나 빨리 포화될지 조절하는 값
- `b`: 문서 길이 보정의 강도

Elasticsearch의 `text` 필드는 기본 유사도 함수로 BM25를 사용한다. 즉, 적절히 분석한 필드에 `match` 질의를 보내면 키워드 겹침에 따른 점수와 순위를 얻는다. BM25 점수는 절대적인 확률이나 문서 간 보편 점수가 아니라, 같은 인덱스와 같은 질의 안에서 결과를 정렬하기 위한 상대적 신호로 이해하는 것이 안전하다.

## 한국어 토크나이징: 형태소 분석 vs n-gram

검색 품질은 BM25 공식만으로 결정되지 않는다. **무엇을 하나의 토큰으로 볼 것인가**가 특히 중요하다.

### 형태소 분석기: 의미 단위에 가깝게 나누기

Elasticsearch의 `nori_tokenizer`는 한국어 형태소 분석용 토크나이저다. 예를 들어 활용형·복합 명사를 분석해 검색 가능한 토큰 스트림으로 만든다. 한국어 문장에서 조사나 어미 변화 때문에 단어 표면형이 달라지는 문제를 줄이는 데 유리하다.

### nori는 무엇을 하는가

nori는 Lucene의 한국어 분석 모듈을 Elasticsearch에서 쓰게 하는 `analysis-nori` 플러그인이다. 기본 사전으로 `mecab-ko-dic`을 사용한다. nori를 사용하려면 모든 Elasticsearch 노드에 플러그인을 설치하고 재시작해야 한다.

분석 과정은 크게 두 단계다.

```text
원문 / 질의
  -> nori_tokenizer: 형태소·복합어 단위 토큰 생성
  -> nori_part_of_speech: 검색에 불필요한 품사 토큰 제거
  -> 역색인 또는 질의 토큰
```

`nori_tokenizer`와 `nori_part_of_speech` 필터를 조합해 사용자 정의 분석기를 만들 수 있다. 문서를 색인할 때와 `match` 질의를 처리할 때 같은 분석기를 적용하면, 같은 기준의 토큰끼리 BM25 점수를 계산할 수 있다.

#### 복합 명사와 `decompound_mode`

복합어를 어떻게 다룰지도 검색 결과에 영향을 준다. nori의 `decompound_mode`는 다음 세 값을 제공한다.

| 값 | `가곡역` 예시 |
| --- | --- |
| `none` | `가곡역`을 유지 |
| `discard` (기본값) | `가곡`, `역`으로 분해하고 원형은 버림 |
| `mixed` | `가곡역`, `가곡`, `역`을 함께 보존 |

기본값은 `discard`다. 따라서 기본 nori는 사전에 있는 복합어를 분해할 수 있지만, 원형 토큰을 항상 보존하지는 않는다.

#### 분석 결과가 순위에 미치는 영향

예를 들어 어떤 분석기가 `재수강 신청`을 `[수강, 신청]`으로 만들면, BM25는 `재수강`이라는 표면형이 아니라 그 두 토큰의 빈도·희소성·문서 길이만으로 순위를 계산한다. 따라서 `수강신청`을 포함한 문서가 더 높은 점수를 받을 수 있다. 이는 BM25 순위 함수의 오류가 아니라 **분석기가 만든 토큰이 검색의 입력**이라는 뜻이다.

사용자 사전은 이런 문제를 다룰 수 있는 선택지다. 공식 문서상 사용자 사전은 기본 사전에 사용자 명사를 추가하는 확장 기능이며, 복합 명사는 원하는 분해 단위도 함께 정의할 수 있다. 다만 사전은 토큰화 자체를 바꾸므로, 추가한 뒤에는 대표 질의의 분석 결과와 검색 순위를 함께 검증해야 한다.

### n-gram: 글자 조각을 넓게 만들기

`ngram` 토크나이저는 텍스트를 일정 길이의 연속 토큰 조각으로 낸다. 사전 없이 부분 문자열 검색과 오타·변형에 어느 정도 견고해질 수 있지만, 토큰 수와 인덱스 크기가 늘고 의미 없는 조각도 많이 생긴다.

| 선택 | 장점 | 비용/주의점 |
| --- | --- | --- |
| 형태소 분석(nori) | 한국어 어근·복합어를 더 자연스럽게 처리 | 사전과 분석 설정의 영향을 받음 |
| n-gram | 부분 일치·표기 변형에 강함 | 인덱스가 커지고 잡음 토큰이 증가 |
| 공백/기본 분리 | 가장 단순 | 한국어 활용형·붙여쓰기 변형에 취약 |

## grep보다 나아지는 점과 여전히 남는 한계

BM25는 `재수강`, `신청`, `기간`처럼 일부 단어가 겹치는 여러 청크 중 더 관련 있는 결과를 위로 올린다. 그러나 `수업을 다시 듣는 절차`와 `재수강`처럼 **토큰이 하나도 겹치지 않는 동의 표현**은 여전히 찾기 어렵다. 이 표현 불일치를 줄이기 위해 2세대 벡터 검색을 추가한다.

## 키워드 검색이 강한 정보

정확한 명칭, 법령 번호, 제품 코드, URL, 오류 메시지처럼 토큰 자체가 의미의 핵심인 정보는 BM25가 매우 강하다. 반대로 표현 자체가 많이 달라질 수 있는 질문은 벡터 검색이나 동의어 사전·질의 확장과 결합하는 편이 좋다.

## 참고 자료

- [Elasticsearch text field](https://www.elastic.co/guide/en/elasticsearch/reference/current/text.html) - `text` 필드의 분석기와 기본 BM25 유사도
- [Elasticsearch similarity](https://www.elastic.co/guide/en/elasticsearch/reference/current/similarity.html) - 필드별 유사도 설정과 BM25
- [Elasticsearch nori_tokenizer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer) - 한국어 형태소 분석 토크나이저의 공식 설정
- [Elasticsearch Korean (nori) analysis plugin](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori) - nori 플러그인 설치와 기본 사전
- [Elasticsearch nori_part_of_speech token filter](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-speech) - 품사 기반 토큰 제거 필터
- [Elasticsearch n-gram tokenizer](https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-ngram-tokenizer.html) - n-gram 생성 방식과 설정
- [Weaviate Advanced RAG Techniques](https://weaviate.io/ebooks/advanced-rag-techniques) - 데이터 정제, 청킹, 메타데이터 필터링, 하이브리드 검색의 RAG 연결
