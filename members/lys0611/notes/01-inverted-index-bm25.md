---
title: 역색인과 BM25 — 키워드 검색(1세대)이 잡는 것과 놓치는 것
date: 2026-09-09
tags: [inverted-index, tf-idf, bm25, elasticsearch, lucene, nori, tokenization, ngram, korean]
status: done
---

# 01. 역색인과 BM25 — 키워드 검색(1세대)이 잡는 것과 놓치는 것

> 참고 자료:
> - Robertson et al., *Okapi at TREC-3* (1994) — BM25의 원 출처
> - Elastic, [Similarity module (BM25 파라미터)](https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity) · [Practical BM25 Part 2](https://www.elastic.co/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables), [Part 3](https://www.elastic.co/blog/practical-bm25-part-3-considerations-for-picking-b-and-k1-in-elasticsearch)
> - Lucene, [BM25Similarity javadoc](https://lucene.apache.org/core/8_1_1/core/org/apache/lucene/search/similarities/BM25Similarity.html) — IDF 식 그대로
> - Elastic, [Korean (nori) analysis plugin](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori) · [nori_tokenizer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer)
> - 실습: [labs/01-ingest](../labs/01-ingest/README.md) 의 `kakao_chunks` 인덱스

## 한 줄 요약

grep은 "문자열이 그대로 있는가"만 보고 순위가 없다. 역색인은 문서를 **단어 → 문서 목록**으로 뒤집어 놓아 검색을 O(문서 수)에서 O(매칭 단어 수)로 바꾸고, BM25는 그 위에서 "이 단어가 이 문서에 얼마나 특징적인가"를 점수로 매긴다. 한국어에서는 **무엇을 단어로 볼 것인가(토크나이징)**가 이 모든 것의 전제다.

## 핵심 개념

- **0세대 grep의 한계**: 표현 불일치(`마감`≠`데드라인`), 순위 없음, 띄어쓰기·조사 하나에 깨짐, 매번 전체 스캔.
- **역색인(inverted index)**: term → postings(문서 id, 빈도, 위치). Lucene은 이것을 불변 세그먼트로 쓰고 주기적으로 병합한다(→ [03. DDIA 3장](03-ddia-ch3-storage-and-search.md)의 LSM 계열).
- **TF-IDF → BM25**: 단어 빈도(TF)는 **포화**시키고(k1), 문서 길이로 **정규화**하고(b), 흔한 단어는 IDF로 깎는다. Elasticsearch 기본 유사도가 BM25, 기본값 `k1=1.2`, `b=0.75`.
- **한국어 토크나이징**: 형태소 분석(nori, mecab-ko-dic 사전) vs n-gram(사전 없이 글자 조각). 각각 이기는 상황이 다르다.
- **`match` 쿼리는 기본 OR**: "마감 일정"은 `마감 OR 일정`으로 풀린다. 하나만 맞아도 걸린다.

## 상세 정리

### 1. grep으로는 왜 안 되는가

| 문제 | 예 (카톡 데이터) |
|---|---|
| 표현 불일치 | 질문 "마감 일정" ↔ 본문 "제출일", "언제까지", "데드라인" |
| 순위 없음 | `ILIKE '%일정%'` 결과 300건이 시간순으로만 나열됨 |
| 형태 변화 | "예약했어요", "예약할까", "예약은" 이 모두 다른 문자열 |
| 비용 | 문서 수에 비례해 매번 전체 스캔 (pg_trgm 인덱스로 속도만 보조 가능) |

실습에서 `messages.text ILIKE '%…%'` 가 정확히 이 0세대다. "마감 일정" 은 두 단어가 붙어 있는 메시지가 없어 **0건**이었다.

### 2. 역색인 구조

```
문서: d1 "부산 숙소 예약했어요"   d2 "숙소는 내가 알아볼게"   d3 "부산 언제 갈까"
사전(term)   postings
부산      →  d1(tf1, pos0), d3(tf1, pos0)
숙소      →  d1(tf1, pos1), d2(tf1, pos0)
예약      →  d1(tf1, pos2)
```

- 질문이 오면 사전에서 term을 찾고 postings를 교집합/합집합한다. 문서 전체를 읽지 않는다.
- postings에 **위치**가 있어 `match_phrase`(인접 매칭), 하이라이트(`«일정»`)가 가능하다.
- Lucene은 색인을 **불변 세그먼트** 파일로 쓰고 새 문서는 새 세그먼트로 추가, 백그라운드에서 병합한다. 그래서 색인 직후 바로 검색되지 않고 `refresh`(기본 1초) 후에 보인다. 실습의 `index_es.py` 가 마지막에 `indices.refresh` 를 호출하는 이유.

### 3. TF-IDF에서 BM25로

```
score(D, Q) = Σ_{t ∈ Q}  IDF(t) · ( f(t,D) · (k1 + 1) ) / ( f(t,D) + k1 · (1 − b + b · |D| / avgdl) )
IDF(t)      = ln( 1 + (N − n(t) + 0.5) / (n(t) + 0.5) )        ← Lucene 구현
```

| 기호 | 뜻 | 기본값 / 효과 |
|---|---|---|
| f(t,D) | 문서 D 안의 term 빈도 | 많을수록 점수↑, 단 **포화**됨 |
| k1 | TF 포화 강도 | ES 기본 1.2. 0이면 "있냐 없냐"만, 크면 빈도가 계속 반영 |
| b | 문서 길이 정규화 | ES 기본 0.75. 0이면 길이 무시, 1이면 평균 대비 길이로 완전 정규화 |
| N, n(t) | 전체 문서 수, t를 포함한 문서 수 | 흔한 단어(n(t) 큼)는 IDF↓ |

- Lucene 최신 `BM25Similarity`는 분자의 `(k1+1)`을 생략한다(순위는 같고 점수 크기만 다름). 옛 동작은 `LegacyBM25Similarity`.
- Elastic 블로그의 결론: 대부분 코퍼스에 기본값 `b=0.75, k1=1.2`가 잘 맞고, 튜닝 전에 분석기·쿼리 설계·필드 부스팅을 먼저 손보라.

**왜 TF-IDF가 아니고 BM25인가.** TF-IDF는 단어가 10번 나오면 1번보다 10배 중요하다고 본다. BM25는 "몇 번 이상 나오면 더 봐줄 것 없다"(포화)와 "긴 문서가 단어를 많이 포함하는 건 당연하다"(길이 정규화)를 넣은 것이다. 짧은 카톡 청크에서는 길이 정규화가 특히 크게 작동한다.

### 4. 한국어 토크나이징 — 형태소(nori) vs n-gram

BM25 점수는 "term"을 어떻게 자르느냐에 완전히 의존한다. 영어는 공백으로 자르면 대충 되지만 한국어는 `예약했어요` 안에 `예약`이 들어 있어도 문자열이 다르다.

**nori (형태소 분석)**
- 사전 기반: nori 플러그인은 mecab-ko-dic 사전으로 한국어 형태소 분석을 한다. 공식 이미지에 없어 `elasticsearch-plugin install analysis-nori` 로 노드마다 설치한다.
- `decompound_mode`: 복합명사 처리. `none`은 분해 안 함, `discard`(기본)는 `가곡역 → 가곡, 역` 으로 분해하고 원형을 버림, `mixed`는 `가곡역, 가곡, 역` 으로 원형도 유지. 실습은 `mixed`(원형 매칭과 부분 매칭 둘 다 살리기).
- `user_dictionary`: 팀 용어(프로젝트명, 서비스명)를 명사(NNG)로 등록해 분해를 막을 수 있다.
- 토큰 필터: `nori_part_of_speech`(조사·어미 등 기본 stoptags 제거), `nori_readingform`(한자→한글 읽기), `lowercase`.

**n-gram (글자 조각)**
- 사전 없이 `부산숙소 → 부산, 산숙, 숙소`(2-gram) 처럼 자른다. 신조어·오타·초성체(`ㄱㄱ`, `ㅇㅇ`)에 강하고 사전에 없는 말도 걸린다.
- 대신 인덱스가 커지고 노이즈 매칭이 늘어난다(`산숙` 같은 무의미 토큰). ES `ngram` 토크나이저는 `min_gram`/`max_gram`을 쓰고, 둘의 차가 `index.max_ngram_diff`(기본 1)를 넘으면 에러.

| | nori (형태소) | n-gram |
|---|---|---|
| 사전 | 필요 (mecab-ko-dic) | 불필요 |
| `예약했어요` | `예약` 으로 정규화 → `예약` 질의와 매칭 | `예약, 약했, 했어, 어요` — `예약` 질의는 2-gram `예약` 로 매칭 |
| 신조어·초성·오타 | 사전에 없으면 이상하게 잘림 | 강함 |
| 인덱스 크기 / 노이즈 | 작음 / 적음 | 큼 / 많음 |
| 카톡에서 | 일반 대화 문장 | 줄임말·은어·이름 변형 |

실습은 `text`(nori) + `text.ngram`(2~3gram) 두 필드를 함께 색인해 두었다. 분담 과제 "nori vs n-gram 비교"는 같은 질문을 두 필드에 던져 보면 된다.

### 5. 내 데이터에서 본 것 — "마감 일정"

| 방식 | 결과 | 해석 |
|---|---|---|
| grep `ILIKE '%마감 일정%'` | 0건 | 두 단어가 붙어서 나온 메시지가 없음 |
| BM25 (nori) | top-1 = 투표 공지 청크(score 7.1) | `match`가 OR로 풀려 `일정`만 3번 반복된 짧은 공지가 1위. `마감`을 포함한 진짜 정답 청크는 2위 |
| 벡터 | top-1 = "제출일" 논의 청크 | 단어가 없어도 뜻으로 잡음 (→ [02](02-embeddings-cosine-hnsw.md)) |

BM25가 틀린 게 아니라 **질문을 OR로 해석한 것**이 문제였다. `minimum_should_match: "2"` 나 `match_phrase` 를 쓰면 `마감`과 `일정`이 둘 다 있는 청크만 남는다. 반대로 그렇게 조이면 "제출일" 같은 표현 불일치는 영원히 못 잡는다 — 이것이 2세대(벡터)와 3주차 하이브리드의 동기다.

## 예시 / 코드

실습에서 쓴 분석기 설정(`src/index_es.py`):

```json
{
  "tokenizer": { "nori_mixed": { "type": "nori_tokenizer", "decompound_mode": "mixed" } },
  "analyzer": {
    "korean": { "type": "custom", "tokenizer": "nori_mixed",
                "filter": ["nori_part_of_speech", "nori_readingform", "lowercase"] },
    "korean_ngram": { "type": "custom", "tokenizer": "ngram_2_3", "filter": ["lowercase"] }
  }
}
```

```bash
python src/index_es.py --analyze "부산 여행 숙소 예약했어요"
# korean       : ['부산', '여행', '숙소', '예약']
# korean_ngram : ['부산', '산 ', ' 여', '여행', ...]
```

BM25 한 항을 손으로 계산해 보기:

```python
import math
def bm25_term(tf, dl, avgdl, N, n, k1=1.2, b=0.75):
    idf = math.log(1 + (N - n + 0.5) / (n + 0.5))
    return idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avgdl))
# '일정' 이 3번 나오는 30단어 공지 vs 1번 나오는 200단어 대화 (평균 길이 100, N=2000, n=150)
print(bm25_term(3, 30, 100, 2000, 150), bm25_term(1, 200, 100, 2000, 150))
```

## 궁금한 점 / 더 알아볼 것

- [ ] `minimum_should_match`·`match_phrase`를 넣으면 "마감 일정" 표가 어떻게 바뀌나 — 정밀도↑ 재현율↓를 수치로
- [ ] 팀 용어를 `user_dictionary`에 넣었을 때 nori 토큰이 어떻게 달라지나
- [ ] 초성체(`ㄱㄱ`, `ㅇㅇ`)와 줄임말은 nori에서 어떻게 잘리나 — n-gram 필드로 보완되는지
- [ ] BM25 점수는 인덱스마다 스케일이 달라 벡터 코사인과 직접 비교가 안 된다 → 3주차 RRF가 점수 대신 **순위**를 쓰는 이유

## 스터디에서 나눌 이야기

- `decompound_mode`를 `mixed`로 한 이유와 `discard`와의 차이를 실제 토큰으로 보여주기
- "BM25가 이기는 질문"의 공통점: 고유명사·숫자·짧은 키워드. "지는 질문": 동의어·풀어 쓴 질문
- 카톡은 문서가 짧다 → `b`(길이 정규화)를 낮추면 어떻게 되는지 누가 실험해 볼 만함
