---
title: grep — 문자열 매칭은 무엇을 잡고 무엇을 놓치는가
type: concept
tags: [concept]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [dldusgh318, yujeong430, kdyann, e0ng, do-dop, heebindev, sunghyun, jjinthung, ur2e, lys0611]
weeks: [2]
---

> 0세대 검색. 인덱스 없이 파일을 처음부터 훑어 패턴과 일치하는 **줄**을 돌려준다. 정확한 문자열·코드·ID에는 강하고, 표현이 다르거나 순위가 필요하면 무너진다. 스터디 멤버 전원이 자기 데이터로 이 한계를 직접 확인했다.

## 정의

- grep은 조건을 만족하는 줄을 **판정**한다(맞음/틀림). 정보 검색(IR)은 질의와 문서의 관련도를 계산해 **순위화**한다. 이 차이가 [[역색인과-BM25|BM25]]와 [[임베딩과-벡터-검색|벡터 검색]]의 결과가 점수와 정렬을 갖는 이유다 (yujeong430).
- 정규표현식(BRE/ERE/PCRE, 고정 문자열은 `-F`)은 알려진 표기 변형을 표현할 수 있지만 사람이 규칙을 미리 설계해야 하고, "수업을 다시 듣는다"가 "재수강"이라는 의미 관계는 추론하지 않는다 (yujeong430, e0ng).
- 비용 모델: 인덱스를 만드는 사전 비용은 없지만 검색 비용이 읽어야 하는 텍스트 양에 비례하고 질의가 반복될수록 쌓인다. ripgrep은 스캔을 빠르게 한 것이지 스캔을 없앤 게 아니다 (yujeong430, dldusgh318).

## 세 가지 한계

1. **표현 불일치.** `트러블 슈팅 ≠ 트러블슈팅`, `Elasticsearch ≠ 엘라스틱서치`, `지식그래프 ≠ 지식 그래프`. 한국어는 조사·어미가 붙어 더 자주 터지고 `grep -w`도 형태소를 아는 게 아니다 (dldusgh318).
2. **순위 없음.** 결과 순서는 파일을 읽은 순서와 줄 위치다. `캐시` 407건 중 Look-Aside 전략과 Gradle 빌드 캐시와 캐시 파일 삭제가 grep에게는 전부 같은 MATCH다 (dldusgh318).
3. **단위가 줄이다.** GNU grep은 패턴 목록 구분에 줄바꿈을 쓰므로 한 패턴이 줄바꿈을 가로질러 일치할 수 없다. 카카오톡 내보내기처럼 맥락이 여러 줄에 걸치면 각 줄이 따로 검색된다. `-C 3`은 앞뒤를 보여줄 뿐 문서 단위로 묶거나 점수화하지 않는다 (do-dop, yujeong430).

## 멤버들이 확인한 것

| 멤버 | 데이터 | 관찰 |
|---|---|---|
| dldusgh318 | Notion 131개 문서, 0.95MB | `캐시` 407건(Feast), `학교` 51건(`홍익대학교`까지 과대매칭), `트러블 슈팅` 1건(`트러블슈팅` 14건 놓침), `성능을 개선한 경험`·`검색이 왜 어려운가` 0건(Famine). "많이 찾는 것과 잘 찾는 것은 다르다" |
| dldusgh318 | 같은 데이터, 프로브 10개 | 의미 질의 3개 전부 0건, 오타 `쿠버네티즈` 0건, 띄어쓰기 `엘라스틱 서치` 0건. 검색 시간 약 20~30ms |
| e0ng | 채팅 CSV 9,491건 | `수강 신청` 0건인데 `수강신청` 5건. 검색 시간 6.2ms |
| do-dop | 카카오톡 1,203건 | `다음 모임 날짜` 0건, 자연어 질문 2건 모두 0줄. `곡` 38줄처럼 흔한 글자는 과다 |
| heebindev | Notion 운영체제 노트 | `process` 113줄, `CPU 작업 순서` 0건(문서에는 `스케줄링`으로 있음) |
| kdyann | Instagram 게시물 13개 | `야구` 7줄(순위 없음), `개발 공부`·`집중 시간을 관리하는 생산성 도구` 0건 |
| jjinthung | 카카오톡 753청크, 정답 40개 | Hit@1 0%, Hit@5 0%, 평균 4.37ms |
| ur2e | 합성 옵시디언 vault | 패러프레이즈 질의·시간 질의 0건 |
| lys0611 | 카카오톡 2개 방 1,922청크, 질문 10개 | 10개 중 8개 0건. `회의록 오늘 중으로`는 정확 문구 1건이 있어 **grep이 이긴** 유일한 질문(순위화가 필요 없었다) |

## grep이 오히려 맞는 경우

- 정확한 고유명사·코드·URL·오류 문구(`HTTP 404`, `@Transactional`, `NullPointerException`, `x509: certificate has expired`), 데이터가 작고 한두 파일을 빨리 볼 때, 결과가 왜 나왔는지 한 글자 단위로 설명해야 할 때 (yujeong430, dldusgh318, ur2e의 `exact-token` 유형).
- 핵심 질문은 "grep은 나쁜가"가 아니라 "grep은 무엇을 잡고 무엇을 놓치는가"다 (dldusgh318). [[검색의-세-세대]]는 대체가 아니라 누적이다.

## 함정

- 맥 기본 `sed`는 UTF-8 한글에 안전하지 않다. 프로파일링도 파이썬으로 (sese2204).
- Windows에서는 Git 동봉 grep을 절대경로로 호출해야 한다: `'C:\Program Files\Git\usr\bin\grep.exe' -nF …` (yujeong430).
- 비교 실험에서 grep만 원본 파일을, BM25·벡터는 청크를 검색하면 단위가 달라 비교가 깨진다 → [[검색의-세-세대]] §검색 단위.

## 관련

- [[검색의-세-세대]] · [[역색인과-BM25]] · [[한국어-토크나이징-nori와-n-gram]] · [[임베딩과-벡터-검색]]

## 출처

- dldusgh318 · 0세대 — grep은 왜 문서 검색에 실패하는가 — [members/dldusgh318/notes/week2/01-grep-limits.md](../../members/dldusgh318/notes/week2/01-grep-limits.md); 프로브 비교 — [results/compare.md](../../members/dldusgh318/labs/01-three-generations/results/compare.md)
- yujeong430 · 0세대 검색 - grep 문자열 매칭 — [members/yujeong430/notes/01-grep-string-matching.md](../../members/yujeong430/notes/01-grep-string-matching.md)
- kdyann · 검색의 세 세대 (§0세대) — [members/kdyann/notes/02-search-generations.md](../../members/kdyann/notes/02-search-generations.md); Instagram 실습 — [labs/01-instagram-search/README.md](../../members/kdyann/labs/01-instagram-search/README.md)
- e0ng · 검색의 세 세대를 직접 만든다 — [members/e0ng/notes/02-search-generations.md](../../members/e0ng/notes/02-search-generations.md); 실습 — [labs/02-search-generations/README.md](../../members/e0ng/labs/02-search-generations/README.md)
- do-dop · grep에서 벡터 검색까지 — [members/do-dop/notes/02-search-generations.md](../../members/do-dop/notes/02-search-generations.md); 실습 — [labs/02-kakaotalk-search/README.md](../../members/do-dop/labs/02-kakaotalk-search/README.md)
- heebindev · 검색의 세 세대 — [members/heebindev/notes/02-search-generations.md](../../members/heebindev/notes/02-search-generations.md); 실습 — [labs/01-notion-search/README.md](../../members/heebindev/labs/01-notion-search/README.md) (PR #12 미머지)
- sunghyun · grep, BM25, 벡터 검색 정리 — [members/sunghyun/note/02-search-methods.md](../../members/sunghyun/note/02-search-methods.md)
- jjinthung · Grep vs BM25 vs Vector Search — [members/jjinthung/notes/01_results.md](../../members/jjinthung/notes/01_results.md)
- ur2e · 검색 방식 비교 실험 — [members/ur2e/notes/01-search-methods-comparison.md](../../members/ur2e/notes/01-search-methods-comparison.md) (PR #11 미머지)
- lys0611 · 카톡 대화 적재 비교표 — [members/lys0611/labs/01-ingest/compare.md](../../members/lys0611/labs/01-ingest/compare.md) (PR #15 미머지)
- 외부: GNU grep manual https://www.gnu.org/software/grep/manual/grep.html · Furnas et al., The Vocabulary Problem (CACM 1987) · ripgrep 블로그 https://blog.burntsushi.net/ripgrep/ (dldusgh318 readings)
