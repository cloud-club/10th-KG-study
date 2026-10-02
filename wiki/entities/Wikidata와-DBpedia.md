---
title: Wikidata와 DBpedia — 공개 지식그래프의 데이터 모델
type: entity
tags: [tool, dataset]
status: maintained
created: 2026-10-02
updated: 2026-10-02
members: [do-dop, dldusgh318, e0ng, heebindev, lys0611, Yeongeunn, kdyann, kungbi, sunghyun]
weeks: [4]
---

> 스터디가 실제로 손으로 질의해 본 유일한 외부 지식그래프 둘. DBpedia(2007)는 위키백과 infobox를 추출해 RDF로 만든 Linked Open Data의 허브이고, Wikidata(2012)는 처음부터 공동 편집으로 쌓은 그래프로 **statement에 qualifier(유효 시점·범위)와 reference(출처)를 붙이는 모델**이 핵심이다. "선수 –PLAYS_FOR– 팀 + 시작일·종료일·출처"가 왜 중요한지의 원형이며, [[RDF와-트리플]]의 n항 관계 문제를 공개 KG가 어떻게 푸는지 보여준다.

## 개요

| | DBpedia | Wikidata |
|---|---|---|
| 시작 | 2007 | 2012 |
| 데이터 출처 | 위키백과 문서(infobox) **추출** | 항목·속성·값을 **직접 공동 작성·관리** |
| 식별자 | `dbr:The_Little_Prince`, 속성 `dbo:author` | 항목 `Q`(Q42 더글러스 애덤스, Q80 팀 버너스리, Q884 대한민국), 속성 `P`(P31 instance of, P279 subclass of, P50 저자, P69 교육기관, P108 고용주, P569 생년월일, P19 출생지) |
| 관계의 부가 정보 | — | **Item – Statement – Property – Value – Qualifier – Reference – Rank** (do-dop). Qualifier = 시간·순서 맥락, Reference = 근거 출처 |
| endpoint | https://dbpedia.org/sparql | https://query.wikidata.org/ |

- Wikidata 접두어 5종 (lys0611, dldusgh318): `wd:`(entity) / `wdt:`(값으로 직행) / `p:`(statement 노드로) / `ps:`(statement의 주된 값) / `pq:`(qualifier). `wdt:P69`로는 학교만 나오고, 재학 기간은 `p:P69 → ps:P69 / pq:P580(시작) · pq:P582(종료)`로 가야 보인다. "공식 모델에서도 statement는 S–P–O를 기본으로 하고 qualifier로 확장한다" (lys0611).
- **claim vs statement** (Yeongeunn): claim = 주요 속성–값 + 한정어, statement = claim + 출처 + 순위(rank: preferred·normal·deprecated). "화면이나 설명 문서에서 용어가 느슨하게 쓰이므로 구현할 때는 데이터 모델을 확인한다." `wdt:`는 rank를 반영한 **truthy** 진술 — deprecated 제외, preferred가 있으면 그것, 없으면 normal (kdyann·Yeongeunn 독립 확인). "'truthy'라는 명칭이 현실의 진실을 보증하는 것은 아니다" (Yeongeunn). "랭크는 사실의 확률 점수가 아니다" (sunghyun), "검색 1·2위나 모델 confidence 0.9와 다른 개념. 오래됐다는 이유만으로 deprecated가 아니다" (Yeongeunn). 읽는 순서: 대상 → 속성/값 → 한정어(start time·end time) → 출처 (kungbi 그림 4).
- dldusgh318은 자기 스키마와 대응시켰다: statement ↔ `TechnologyUse` 중간 노드, statement의 주된 값 ↔ 사용한 기술, qualifier ↔ 목적·상태. "완전히 같은 데이터 모델은 아니지만 문제의식은 비슷하다."
- 역사적 자리: 시맨틱 웹의 "완벽한 온톨로지 → 사람이 입력"에서 "이미 있는 데이터 → 구조화 → 연결"로의 전환(DBpedia), 개방성(공개 데이터·SPARQL)과 실용성(기간·출처 관리)의 절충(Wikidata). "하나의 사실이 항상 절대적 참/거짓으로 떨어지지 않는다"는 점을 데이터 모델에 반영 (dldusgh318) → [[시맨틱-웹에서-지식그래프까지]].
- Google Knowledge Graph는 Wikipedia·Freebase를 통합해 만들었고 내부 ID를 쓴다 → [[기업-지식그래프-사례]].

## 스터디 그래프로의 번역 (Yeongeunn)

- 출발 문제: `배송서비스 –담당 팀→ A팀`과 `→ B팀`이 둘 다 저장되면 겉으로 충돌하고, 지우면 과거를 잃는다. 필요한 것은 **언제의 사실인가 + 누가 주장했나 + 무슨 문서 근거인가**. Wikidata에 올리자는 게 아니라 "표시 이름과 안정적인 식별자를 분리하는 설계 원리"를 배우는 것.
- rank를 복사하지 말고 **쪼갠다**: `review_status`(미검토/승인/반려) / `valid_from`, `valid_to` / `source_version`. **"'검토자가 승인함'과 '현재에도 유효함'은 서로 다른 상태다."** 출처는 "진실 인증서가 아니라 검토 가능한 근거" — `문서 ID + 버전 + 청크 ID + 인용문`. "생성 모델 이름만 저장하는 것은 원문 근거를 대신하지 못한다." 출처의 존재 여부와 근거의 적절성은 따로 평가한다.
- 한정어가 필요한 지점: 담당 팀 → 어느 기간 / API 제한 횟수 → 어떤 버전·시간 단위 / 정책의 차단 → 어떤 사용자·상태. "모든 조건을 자유 문자열로 붙이면 질의하기 어렵다." lys0611의 `WORKS_AT(valid_from, valid_to)` 스키마 후보와 같은 처방 → [[멀티홉-질문과-Bridge-Entity]].
- 적용 체크리스트 5: ID로 연결하나 / 버전·시점·조건을 잃지 않나 / 원문이 바뀌어도 출처를 확인할 수 있나 / 상충하는 두 진술을 덮어쓰지 않고 검토할 수 있나 / 사람 승인·모델 자신감·현재 유효성을 구분하나. 결론: "더 많은 관계를 추출하기"에서 "추출한 관계를 설명하고 검토할 수 있게 만들기"로. Yeongeunn의 5주차 `assertions.review_status`·`evidence.source_version` 컬럼이 이 번역의 구현 → [[그래프-적재-Postgres와-Neo4j]], [[데이터-수집과-출처-추적]].

## 겪은 문제 · 함정

- 결과가 Q ID만 나온다 → `SERVICE wikibase:label` + `"ko,en"` (전원). `rdfs:label` + `FILTER(LANG(?name) = "ko")`로 걸면 해당 언어 라벨이 없는 항목은 결과에서 빠진다 (yujeong430).
- `ORDER BY`가 없으면 행 순서가 달라도 정상이고, 공개 데이터의 값·표시는 시간이 지나면 변한다 (kdyann).
- 전체 Wikidata가 대상이라 `LIMIT` 필수 (dldusgh318). 집계 쿼리(`COUNT … GROUP BY`)는 체감상 더 느렸다 (e0ng, 수치 없음).
- 같은 질문을 두 endpoint로 옮기면 식별자·속성 체계가 달라 질의를 다시 써야 한다 — `wdt:P50` vs `dbo:author` (do-dop 실측) → [[SPARQL]].
- Q ID는 Wikidata 내부에서 정리된 동일성이지, 내 데이터의 대상과 같은지는 별도 판단 (dldusgh318).

## 의사결정 · 남은 일

- 스터디 그래프와 Wikidata를 `owl:sameAs`로 잇는 시도는 아무도 하지 않았다. 개인 데이터(사람·프로젝트)는 Wikidata에 없으므로 연결 대상은 기술명(Redis, PostgreSQL) 정도다.
- Wikidata 질의를 실제로 실행한 멤버: do-dop, dldusgh318, e0ng, heebindev, kdyann(3건, 2026-09-29, 실패 0), sunghyun(Q64→Q183). Yeongeunn·yujeong430·lys0611은 예제만 적고 실행 결과를 기록하지 않았다 → [[SPARQL]].

## 관련

- [[SPARQL]] · [[RDF와-트리플]] · [[시맨틱-웹에서-지식그래프까지]] · [[기업-지식그래프-사례]]

## 출처

- do-dop · 시맨틱 웹에서 지식그래프까지 (§7 DBpedia·Wikidata, §5 실행) — [members/do-dop/notes/04-semantic-web-to-knowledge-graph.md](../../members/do-dop/notes/04-semantic-web-to-knowledge-graph.md)
- dldusgh318 · SPARQL 맛보기 (§접두어, §Wikidata statement), 변천사 (§6) — [members/dldusgh318/notes/week4/02-sparql.md](../../members/dldusgh318/notes/week4/02-sparql.md), [04-history.md](../../members/dldusgh318/notes/week4/04-history.md)
- e0ng · 지식 그래프의 변천사 (§DBpedia·Wikidata), RDF·OWL·SPARQL (§실행) — [members/e0ng/notes/04-1-knowledge-graph-history.md](../../members/e0ng/notes/04-1-knowledge-graph-history.md), [04-2-knowledge-graph-basics.md](../../members/e0ng/notes/04-2-knowledge-graph-basics.md)
- heebindev · 지식 그래프의 배경과 기업 사례 (§6) — [members/heebindev/notes/04-knowledge-graph-background.md](../../members/heebindev/notes/04-knowledge-graph-background.md)
- lys0611 · 지식 그래프의 배경 (§4 Wikidata 접두어) — [members/lys0611/notes/06-knowledge-graph-foundations.md](../../members/lys0611/notes/06-knowledge-graph-foundations.md)
- Yeongeunn · Wikidata의 식별자·진술·근거 — [members/Yeongeunn/notes/11-week4-wikidata-statements.md](../../members/Yeongeunn/notes/11-week4-wikidata-statements.md)
- kdyann · SPARQL 질의와 계약 비교 그래프 모델링 — [members/kdyann/labs/04-sparql-graph/README.md](../../members/kdyann/labs/04-sparql-graph/README.md)
- kungbi · W4 지식 그래프의 배경 (그림 3·4) — [members/kungbi/notes/02-knowledge-graph-background.md](../../members/kungbi/notes/02-knowledge-graph-background.md)
- sunghyun · 지식 그래프는 왜 필요한가 (§Wikidata) — [members/sunghyun/notes/04-knowledge-graph-background.md](../../members/sunghyun/notes/04-knowledge-graph-background.md)
- 외부: Wikidata Data Model https://www.wikidata.org/wiki/Help:Data_model · Help:Statements https://www.wikidata.org/wiki/Help:Statements · Help:Qualifiers https://www.wikidata.org/wiki/Help:Qualifiers · Help:Sources https://www.wikidata.org/wiki/Help:Sources · Help:Ranking https://www.wikidata.org/wiki/Help:Ranking · SPARQL tutorial https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial · DBpedia https://www.dbpedia.org/about/ · Wikidata Query Service https://query.wikidata.org/
