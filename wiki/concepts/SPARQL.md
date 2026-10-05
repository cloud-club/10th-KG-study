---
title: SPARQL — 변수를 공유하면 조인이고, 패턴을 이으면 멀티홉이다
type: concept
tags: [concept]
status: maintained
created: 2026-10-02
updated: 2026-10-02
members: [dldusgh318, e0ng, do-dop, heebindev, lys0611, kdyann, sunghyun, Yeongeunn, yujeong430]
weeks: [4]
---

> RDF 그래프의 표준 질의 언어. 찾고 싶은 자리를 변수로 비워 둔 트리플 패턴을 적고, **같은 변수를 두 패턴에 쓰면 조인**이 되며, 패턴을 연속해 이으면 멀티홉 질의가 된다 — `JOIN` 키워드가 없다. 4주차 공통 실측은 이것 하나다: 여섯 멤버가 Wikidata·DBpedia 공개 endpoint에서 직접 질의를 돌렸다. 단, "SPARQL 문법이 간단하다고 멀티홉 문제가 자동으로 풀리는 건 아니다. 필요한 관계가 그래프에 제대로 추출·저장돼 있다는 전제가 먼저다" (dldusgh318).

## 문법

- 트리플 패턴 3형: `A 관계 ?x` / `?x 관계 B` / `A ?x B` (dldusgh318). 골격 `PREFIX → SELECT|ASK|CONSTRUCT|DESCRIBE → WHERE { … } → LIMIT` (lys0611, e0ng). 패턴 끝은 마침표, 같은 주어는 `;` (e0ng).
- **조인 = 변수 공유**: `?person wdt:P69 wd:Q691283 . ?person wdt:P108 ?org .` → 학교 ← ?person → 고용주 (dldusgh318). "여러 패턴이 같은 변수를 공유하면 조인이 발생하고, 패턴을 연속해 연결하면 multi-hop 질의가 된다" (lys0611). 멀티홉이 "문서 검색 문제"에서 "그래프 관계를 따라가는 문제"로 바뀐다 → [[멀티홉-질문과-Bridge-Entity]].
- `OPTIONAL`: 속성이 없는 대상은 일반 패턴에서 **결과 자체가 탈락**하므로, 대상은 남기고 값만 비우려면 `OPTIONAL`로 감싼다 (dldusgh318). `FILTER`, `ORDER BY`, `LIMIT`, `COUNT/GROUP BY`.
- **Property Path**: `/`로 연속, `*`로 0회 이상. `?item wdt:P31/wdt:P279* ?class`. RDB의 Recursive CTE와 달리 "관계를 따라간다는 개념이 문법에 직접 들어가 있다" (dldusgh318).
- SPARQL은 탐색이지 추론이 아니다. 추론 결과가 질의에 반영되는지는 저장소 설정에 달렸다 (do-dop) → [[온톨로지와-추론]].

## 멤버들이 확인한 것 — 공개 endpoint 실행

| 멤버 | endpoint | 질의 | 증거 |
|---|---|---|---|
| dldusgh318 | Wikidata | ① `wd:Q42 wdt:P69 ?education` ② 같은 학교 출신·고용주 조인 ③ `p:/ps:/pq:`로 재학 시작·종료일(`pq:P580`·`pq:P582`) `OPTIONAL` | 캡처 2장(00-summary), 결과 행 수·시간 미기록 |
| do-dop | **Wikidata + DBpedia** 같은 질문 | 『어린 왕자』의 저자: Wikidata `wd:Q25338 wdt:P50 ?author` vs DBpedia `dbr:The_Little_Prince dbo:author ?author` + `FILTER(lang(?authorLabel)="en")` → 둘 다 생텍쥐페리 | 캡처 3장 (`notes/images/`). "같은 사실을 묻는데도 두 KG의 식별자·데이터 모델이 달라 질의 표현이 달라진다" |
| e0ng | Wikidata | ① 한국의 수도 `wd:Q884 wdt:P36` ② 봉준호 영화 `?film wdt:P57 wd:Q495980` ③ 봉준호 영화 최다 출연 배우 `COUNT … GROUP BY … ORDER BY DESC` | 실행했다고 적었으나 **캡처 파일이 저장소에 없다**(링크 깨짐). 관측 1건: 집계 쿼리가 다른 쿼리보다 오래 걸렸다 |
| heebindev | Wikidata | 팀 버너스리 생년월일·출생지 `wd:Q80 wdt:P569 / wdt:P19` | 캡처 2장 |
| kdyann | Wikidata | ① 대한민국 수도 `wd:Q884 wdt:P36` → Q8684 서울특별시 ② `VALUES` 3개국 수도+좌표 `wdt:P625` → 3행(`Point(경도 위도)`) ③ 좌표 패턴 제거 → 3쌍. 2026-09-29, 실패 0 | 캡처 5장, `.rq` 파일 3개. 결과 값까지 기록한 유일한 멤버 |
| sunghyun | Wikidata | `wd:Q64 wdt:P17 ?country` → `Q183` 반환 확인 | 노트 기록 |
| lys0611, Yeongeunn, yujeong430 | — | 예제만(`wd:Q884 wdt:P36`, 베를린→나라). "실행 결과를 기록한 실습 보고서는 아니다"(Yeongeunn) | — |

- 반환 값을 기록한 멤버는 kdyann뿐이고 소요 시간은 아무도 재지 않았다. 집계 SPARQL이 느렸다는 e0ng의 관측은 [[멀티홉-질문과-Bridge-Entity]]의 집계 질문 절과 맞물린다 — top-k 검색은 집계가 **불가능**하고 그래프는 **가능하되 비용이 든다**.
- 같은 변수로 두 패턴을 잇는 것은 조인이지 OWL 추론이 아니다 (kdyann). **Cypher와 결과 형태가 다르다** — Cypher는 주제의 이름 문자열을, SPARQL은 식별자를 돌려주므로 비교하려면 SPARQL에 라벨 패턴을 더해야 한다 (yujeong430) → [[RDF와-프로퍼티-그래프]].
- 로컬 DB 설치 없이 공개 endpoint만으로 그래프 질의를 실습할 수 있다 (kdyann, yujeong430) — [[로컬-인프라]]에는 Neo4j 컨테이너만 있다.
- Q ID도 Entity Resolution을 해결하지 않는다 — "Wikidata 내부에서 이미 같은 대상으로 정리된 항목을 하나의 Q ID로 식별"할 뿐 (dldusgh318) → [[RDF와-트리플]].

## 함정 · 주의

- 결과가 `Q1234567`만 나와 읽을 수 없다 → `SERVICE wikibase:label { bd:serviceParam wikibase:language "ko,en". }`와 `?xLabel`을 거의 항상 붙인다 (dldusgh318, do-dop, heebindev 모두 사용).
- Wikidata 전체가 대상이라 결과가 과도하다 → `LIMIT`을 습관처럼 (dldusgh318).
- `wdt:`는 값으로 바로 가는 경로라 관계에 붙은 정보(기간)가 안 보인다. `p:` → `ps:`/`pq:`로 statement를 거쳐야 한다 → [[Wikidata와-DBpedia]].
- **"잘못된 관계를 저장하면 SPARQL은 그 잘못된 관계를 아주 정확하게 조회할 뿐이다"** (dldusgh318). "KG가 RAG의 Retrieval 문제를 해결한다"는 결론이 아니라 가설이다.
- 같은 질문을 두 endpoint로 옮길 때 URI와 속성(`wdt:P50` vs `dbo:author`)을 각각 다시 찾아야 한다 (do-dop).

## 열린 질문

- 스터디 자체 그래프(Postgres·Neo4j)에는 SPARQL endpoint가 없다. dldusgh318 5주차는 Turtle로 내보내 Neo4j에 적재하고 Cypher로 질의했다 → [[지식그래프와-온톨로지]]. Jena·GraphDB로 SPARQL까지 갈 것인지는 미정.

## 관련

- [[RDF와-트리플]] · [[Wikidata와-DBpedia]] · [[온톨로지와-추론]] · [[RDF와-프로퍼티-그래프]] · [[멀티홉-질문과-Bridge-Entity]]

## 출처

- dldusgh318 · SPARQL 맛보기 (2026-09-23) — [members/dldusgh318/notes/week4/02-sparql.md](../../members/dldusgh318/notes/week4/02-sparql.md); 4주차 요약 §2 — [00-summary.md](../../members/dldusgh318/notes/week4/00-summary.md)
- do-dop · 시맨틱 웹에서 지식그래프까지 (§5 실행, §7) — [members/do-dop/notes/04-semantic-web-to-knowledge-graph.md](../../members/do-dop/notes/04-semantic-web-to-knowledge-graph.md); 프로퍼티 그래프와 RDF (§6) — [04-relational-and-graph-data-models.md](../../members/do-dop/notes/04-relational-and-graph-data-models.md)
- e0ng · RDF·OWL·SPARQL과 그래프 모델 (§SPARQL) — [members/e0ng/notes/04-2-knowledge-graph-basics.md](../../members/e0ng/notes/04-2-knowledge-graph-basics.md)
- heebindev · 지식 그래프의 배경과 기업 사례 (§6) — [members/heebindev/notes/04-knowledge-graph-background.md](../../members/heebindev/notes/04-knowledge-graph-background.md)
- lys0611 · 지식 그래프의 배경 (§4) — [members/lys0611/notes/06-knowledge-graph-foundations.md](../../members/lys0611/notes/06-knowledge-graph-foundations.md)
- kdyann · SPARQL 질의와 계약 비교 그래프 모델링 (§1 실행) — [members/kdyann/labs/04-sparql-graph/README.md](../../members/kdyann/labs/04-sparql-graph/README.md)
- sunghyun · 4주차 지식 그래프 실습 — [members/sunghyun/labs/04-knowledge-graph/README.md](../../members/sunghyun/labs/04-knowledge-graph/README.md)
- Yeongeunn · 지식 그래프와 온톨로지 (§10) — [members/Yeongeunn/notes/09-week4-ontology-background.md](../../members/Yeongeunn/notes/09-week4-ontology-background.md)
- yujeong430 · 시맨틱 웹에서 지식 그래프까지 (§SPARQL) — [members/yujeong430/notes/10-semantic-web-to-knowledge-graph.md](../../members/yujeong430/notes/10-semantic-web-to-knowledge-graph.md) (PR #19 미머지)
- 외부: SPARQL 1.1 Overview https://www.w3.org/TR/sparql11-overview/ · SPARQL 1.1 Query Language https://www.w3.org/TR/sparql11-query/ · Property Paths https://www.w3.org/TR/sparql11-query/#propertypaths · Wikidata Query Service https://query.wikidata.org/ · DBpedia SPARQL endpoint https://dbpedia.org/sparql
