---
title: 한국어 토크나이징 — nori 형태소 분석과 n-gram
type: concept
tags: [concept, pitfall]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [yujeong430, dldusgh318, do-dop, kdyann, e0ng, ur2e, lys0611]
weeks: [2]
---

> 한국어는 조사·어미가 붙고 복합명사가 생겨 공백 분리가 통하지 않는다. Elasticsearch에서는 nori(형태소, `mecab-ko-dic` 사전)와 n-gram(글자 조각)을 쓰며, 둘은 택일이 아니라 병행 대상이다. **분석기가 만든 토큰이 검색의 입력**이므로 결과가 이상하면 점수가 아니라 토큰을 먼저 봐야 한다.

## nori

- `analysis-nori` 플러그인. Lucene 한국어 모듈을 ES에서 쓰게 하며 기본 사전은 `mecab-ko-dic`. 모든 노드에 설치하고 재시작해야 한다. 공용 인프라([[로컬-인프라]])의 ES 이미지에 포함되어 있다.
- 2단계: `nori_tokenizer`(형태소·복합어 토큰 생성) → `nori_part_of_speech`(불필요 품사 제거). 예: "학교에서 지식그래프를 배웠다" → `학교 / 지식 / 그래프 / 배웠 / 배우` (dldusgh318 실측), "부산 여행 숙소 예약했어요" → `[부산, 여행, 숙소, 예약]` (lys0611 실측), "클라우드기술을 공부했습니다" → `[클라우드, 기술, 공부, 하다]` (e0ng·do-dop).
- `decompound_mode` (yujeong430): `none`은 `가곡역` 유지, `discard`(**기본값**)는 `가곡`+`역`으로 분해하고 원형을 버림, `mixed`는 셋 다 보존. 기본 nori는 복합어의 원형 토큰을 항상 보존하지 않는다.
- lys0611의 분석기 체인: `nori_tokenizer(decompound_mode=mixed) → nori_part_of_speech(조사·어미 제거) → nori_readingform → lowercase`, 보조 필드 `text.ngram`(2~3글자). "부산숙소 예약했어요"가 nori로는 `['부산', '숙소', '예약']`, n-gram으로는 `['부산', '부산숙', '산숙', '산숙소', '숙소', '예약', '예약했', …]`처럼 `산숙`·`약했` 같은 의미 없는 조각을 만든다. 팀명·서비스명처럼 계속 잘못 잘리는 고유어는 n-gram 범위를 넓히기보다 `user_dictionary`가 관리하기 쉽다.
- 사전의 한계: 신조어·기술 용어·서비스명·사람 이름·줄임말은 예상 밖으로 분리된다. dldusgh318은 `지식그래프`가 원하는 형태로 처리되지 않았다고 기록했고, `user_dictionary`에 기술 용어를 추가하는 실험을 TODO로 남겼다. 사전은 토큰화 자체를 바꾸므로 추가한 뒤 대표 질의의 분석 결과와 순위를 함께 검증해야 한다 (yujeong430).
- 토큰화가 순위를 바꾼다: `재수강 신청`이 `[수강, 신청]`이 되면 `수강신청` 문서가 더 높은 점수를 받을 수 있다. BM25의 오류가 아니라 입력이 그렇게 만들어진 것이다 (yujeong430).

## n-gram

- 사전 없이 일정 글자 수로 자른다. 2-gram: `지식그래프` → `지식/식그/그래/래프`, `클라우드스터디` → `클라/라우/우드/드스/스터/터디`. 오타·신조어·띄어쓰기 변형에 상대적으로 강하지만 토큰 수와 인덱스가 커지고 잡음이 는다 (dldusgh318, kdyann, e0ng, do-dop).
- do-dop이 처음엔 "의미 없는 2~3글자 조각이 검색에 도움이 될지 의문"이었다가, 언어적으로 의미를 잘 나누는 것이 언제나 검색하기 좋은 단위는 아니라는 점이 흥미로웠다고 적었다.
- 병행 색인: `text ├─ nori └─ ngram`. nori로 정밀하게 찾고 n-gram으로 놓치는 표현을 보완한다 (dldusgh318, e0ng, do-dop). 가중치 배분은 미해결.

## 멤버들이 확인한 것

- **2-gram은 한 글자 검색어와 공백에서 깨진다** (do-dop, 카카오톡 1,203건): `곡` → nori 27건 / 2-gram 0건, `몇 시` → nori 75건 / 2-gram 0건. 반대로 `정하자`는 nori 25건 / 2-gram 13건, `합주`는 21 / 31.
- **오타가 검색된 이유는 n-gram이 아니었다** (dldusgh318): `쿠버네티즈`가 grep 0건인데 BM25 7건. 처음엔 "BM25가 오타에 강하다"고 생각했지만 analyzer를 보니 `쿠 / 버네 / 티즈`와 `쿠 / 버네 / 티스`의 일부 토큰이 우연히 겹친 것이었다. 결과만 보지 말고 analyzer가 어떤 토큰을 만들었는지 확인해야 한다.

> ⚠️ Contradiction: dldusgh318의 개념 절은 "n-gram이 오타에 강하다"고 쓰고 Case 2는 오타 검색 성공을 형태소 토큰의 우연한 겹침으로 진단한다. `쿠 / 버네 / 티즈` 분해는 같은 문서의 2-gram 예시 방식과도 형태가 달라 어느 analyzer 출력인지 불명. 출처: [dldusgh318 02](../../members/dldusgh318/notes/week2/02-inverted-index-bm25.md) §3, §4 Case 2.

- **stopword 필터 누락** (ur2e, 합성 vault): `nori_part_of_speech`·`nori_readingform`·`lowercase`는 조사·어미(J, E 태그)는 걸러도 "있다/않다" 어간이나 "노드" 같은 짧은 일반명사는 안 거른다. 경쟁 문서들이 `노드`, `않`, `있`, `두`, `멈추`의 형태소 우연 매치로 이겼다. "의미로 진 게 아니라 형태소 우연 매치로 진 거다." `_search?explain=true`로 잡았다.
- **BM25가 한글에서 `인증서`와 `인증서가`를 같은 토큰으로 보려면 nori가 있어야 한다** (ur2e).
- jjinthung의 카카오톡 실습은 분석기 설정을 문서에 적지 않았고 BM25 Hit@5 45%, 벡터 2.5%라는 낮은 수치를 냈다. 분석기 부재가 원인 후보지만 근거가 없어 불명.

## 함정 체크리스트

1. 결과가 이상하면 `_analyze`로 질의와 문서의 토큰을 먼저 본다. `explain=true`로 어느 토큰이 점수를 냈는지 본다.
2. 기본 `match`는 OR다. 후보가 폭발하면 `minimum_should_match`나 `match_phrase`를 고려한다 → [[역색인과-BM25]].
3. `multi_match`의 `best_fields`는 필드 점수를 합산하지 않는다. 제목 부스트가 습관적 단어로 문서 전체를 밀어올릴 수 있다.
4. 한 글자·공백 포함 질의는 n-gram 필드에서 0건이 될 수 있다.
5. 토큰 분석 실습을 할 때는 실제 대화 대신 직접 만든 예시 문장을 쓴다 (do-dop) → [[개인-데이터-가명화와-공개-범위]].

## 관련

- [[역색인과-BM25]] · [[Elasticsearch-운영-함정]] · [[grep-문자열-매칭]] · [[청킹-전략]]

## 출처

- yujeong430 · 1세대 검색 (§한국어 토크나이징) — [members/yujeong430/notes/02-keyword-search-bm25.md](../../members/yujeong430/notes/02-keyword-search-bm25.md)
- dldusgh318 · 1세대 — 역색인과 BM25 (§3, §4) — [members/dldusgh318/notes/week2/02-inverted-index-bm25.md](../../members/dldusgh318/notes/week2/02-inverted-index-bm25.md)
- do-dop · 노트 (§n-gram), 실습 (§nori와 2-gram) — [members/do-dop/notes/02-search-generations.md](../../members/do-dop/notes/02-search-generations.md), [labs/02-kakaotalk-search/README.md](../../members/do-dop/labs/02-kakaotalk-search/README.md)
- kdyann · 검색의 세 세대 (§형태소 분석: Nori) — [members/kdyann/notes/02-search-generations.md](../../members/kdyann/notes/02-search-generations.md)
- e0ng · 검색의 세 세대를 직접 만든다 (§형태소 분석과 n-gram 비교) — [members/e0ng/notes/02-search-generations.md](../../members/e0ng/notes/02-search-generations.md)
- ur2e · 검색 방식 비교 실험 (실험 2) — [members/ur2e/notes/01-search-methods-comparison.md](../../members/ur2e/notes/01-search-methods-comparison.md) (PR #11 미머지)
- lys0611 · 역색인과 BM25 (§한국어에서는 분석기가 먼저다) — [members/lys0611/notes/01-inverted-index-bm25.md](../../members/lys0611/notes/01-inverted-index-bm25.md); 카톡 대화 적재 — [labs/01-ingest/README.md](../../members/lys0611/labs/01-ingest/README.md) (PR #15 미머지)
- jjinthung · 결과 — [members/jjinthung/notes/01_results.md](../../members/jjinthung/notes/01_results.md)
- 외부: Elastic, Nori 공식 플러그인 소개 https://www.elastic.co/blog/nori-the-official-elasticsearch-plugin-for-korean-language-analysis · nori_tokenizer https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer · n-gram tokenizer https://www.elastic.co/docs/reference/text-analysis/analysis-ngram-tokenizer
