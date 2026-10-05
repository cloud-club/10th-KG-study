---
title: RAG vs 그래프 질의 — 검색 문제가 조인 문제로 바뀌는 곳
type: comparison
tags: [comparison]
status: maintained
created: 2026-10-02
updated: 2026-10-02
members: [dldusgh318, e0ng, do-dop, Yeongeunn, heebindev, kdyann]
weeks: [3, 4, 5]
---

> 같은 질문을 하이브리드 RAG와 그래프 탐색에 던진 결과를 모은 표. 5주차 기준 "RAG가 못 풀던 질문을 그래프가 풀었다"는 사례가 둘(dldusgh318 X01, e0ng), "RAG가 4가지 방법으로 전부 실패했는데 그래프는 아직 안 만들었다"가 하나(do-dop), "다중 홉인데 RAG로도 됐다"가 하나(Yeongeunn q10) 있다. **공정한 대규모 비교는 아직 없다** — Yeongeunn은 "그래프는 소수 문서를 검토해 만들었고 검색은 전체 청크가 대상"이라고 스스로 못 박았다. 결론은 do-dop의 한 문장으로 수렴한다: **"텍스트 유사도가 관계의 정확성을 보장하지 않는다."**

## 비교표

| 멤버 | 질문 | RAG 쪽 | 그래프 쪽 | 결론 |
|---|---|---|---|---|
| **dldusgh318** | X01 "프로젝트 A에서 작업 큐에 쓴 기술을 다른 프로젝트에서도 썼나" / X03 "제안만 한 최적화를 실제 적용한 프로젝트는" | 질문에 `Redis`가 없어 다른 프로젝트의 Redis 문서로 넘어가지 못함. Oracle로는 성공 → [[멀티홉-질문과-Bridge-Entity]] | 20청크 표본에서 **Redis가 3개 프로젝트를 잇는 브릿지로 확인**, X03 proposed↔implemented 조합 6개 | "검색 문제가 조인 문제로 바뀌었다." 단 그래프 자체의 품질 문제(과잉 생성·결측)가 새로 생겼다 |
| **e0ng** (PR #36 미머지) | 특정 기업 지원 준비 관련 문서 (3주차 다중 홉 실패 목록) | "역량검사" 청크와 기업명 청크를 따로 검색해 못 이음 | `(Organization)<-[:RELATED_TO_ORGANIZATION]-(Activity)-[:HAS_DOCUMENT]->(Document)` 한 경로로 3행 | "검색은 비슷한 청크를 찾는 확률적 과정이라 연결을 놓칠 수 있지만, 그래프는 두 관계를 정해진 순서로 순회할 뿐이라 놓칠 수가 없다" |
| **do-dop** | "AMD에 HBM4를 공급하는 회사가 최근 분기 공시에서 밝힌 반도체 클러스터 이름" (69청크 코퍼스 안에서 **정답이 없는 질문**이었음) | 4가지 전부 실패: top-k 확대 → 다른 회사 사실로 **자신 있게 틀림** / 에이전틱 2.4b → 재질의 0회, 제목 베낌 / 7.8b → 정답 문서를 쥐고도 `ANSWER` 못 냄 / 독립 분해 → 근거 15개 섞인 회피성 답변 | **미구축.** "AMD –공급받음→ 회사"를 엣지로 두면 다른 회사 사실이 후보에 안 섞인다는 설계 논증만 | 엔티티 귀속 오류는 모델 크기로 안 풀린다. 단 "평범한 질문 대부분은 RAG로 충분하다"는 균형도 명시 |
| **Yeongeunn** | q10 다중 홉 (서비스·메서드·경로) / 탈퇴 API 호출 경로 | **RRF가 정확히 답했다** — "이번 다중 홉 질문은 텍스트 RAG로도 답할 수 있었음" | Cypher 5종 실행 (1-hop 2건, `1..3` 경로 19건, 정책 조건 3건), Postgres JOIN과 교차 검증 | "'다중 홉은 RAG로 불가능하다'고 해석하지 않는다." 그래프 vs 검색은 동작 비교이지 공정 벤치마크가 아니다 |
| **heebindev** | "프로세스가 I/O를 기다리면 어떤 상태가 되고 다음에 어떤 상태로 가나" | 설계 서술만 | `[:TRANSITIONS_TO*1..3]` 질의 설계·실행 절차, 결과 미기재 | 확인 항목으로만 남김 |
| **kdyann** | "최근 7일 반응 얻은 참고 게시물 중 내 콘텐츠와 주제로 연결되는 글" | — (3주차 RAG는 다른 질문) | 내 글 → 공통 Topic ← 참고 글 2-hop 경로 2건 | 공통 Topic은 탐색 후보 조건이지 적합 판정이 아니다. "AI"처럼 넓은 Topic은 이름이 같다는 것만 보여준다 |

## 갈리는 지점

- **RAG로 충분했던 것** (do-dop, 69청크·10문항): 단순 팩트(Hit@5 100%, Recall@5 96~100%), 평범한 비교 질문(수치·출처 인용, 없는 자료는 "없음"을 인정), 같은 문서 안의 얕은 멀티홉(분해로 풀림), 개방형 집계(부분). "극단적 실패 사례만 보면 못 미덥지만 평범한 질문 대부분은 잘 처리한다는 게 균형 잡힌 결론." 흔들리는 지점(융합 파라미터의 코퍼스 의존, RRF가 1등을 놓침)은 "RAG의 한계가 아니라 튜닝 영역" → [[하이브리드-검색과-RRF]].
- **RAG로 안 되는 것** (do-dop): 엔티티 혼동(주제만 비슷하면 다른 회사 사실이 섞임), 정답 없는 질문의 과잉 확신(top-k를 넓히면 "모른다"보다 나쁜 답), 이미 가진 조각을 연결하는 추론(7.8b가 정답 문서를 근거에 두고도 못 이음). "모델 크기로 해결되는 문제와 안 되는 문제가 뚜렷하게 갈렸다" → [[RAG-실패-유형]].
- **"멀티홉이면 그래프"가 아니다.** hop 수가 아니라 한 번의 검색으로 필요한 청크를 확보할 수 있는가가 기준이다(dldusgh318 M01, Yeongeunn q10, do-dop q009 — 셋 다 독립적으로 "정답이 여러 청크에 있음"과 "여러 문서를 조인해야 함"을 구분했다). kdyann 3주차 노트도 "다중 홉에 반드시 그래프가 필요한 건 아니다"라고 썼다. 반대로 lys0611의 검색 실패 2건은 구조화된 정보(표·목록)라 "관계 질의가 맞는 자리"였다 → [[멀티홉-질문과-Bridge-Entity]].
- do-dop의 구조적 비교:

| | RAG (하이브리드 검색) | 지식그래프 |
|---|---|---|
| 찾는 대상 | 질문과 **비슷한 텍스트** | 질문이 지목하는 **엔티티와 관계** |
| "이 사실이 누구 것인가" | 보장 안 됨 | 노드·엣지로 강제 |
| 여러 사실 연결 | LLM 추론 의존 | 경로 탐색으로 기계적 |
| 없는 관계를 물으면 | 비슷한 걸 끌어와 답할 위험 | 경로가 없으면 "없음" |

> ⚠️ Contradiction: **"경로가 없음"은 답인가 모름인가.** do-dop은 위 표에서 "경로가 없으면 '없음'이 명확히 나옴"을 그래프의 장점으로 썼다. dldusgh318(열린 세계 가정)·do-dop 자신의 4주차 노트·lys0611은 "그래프에 사실이 없다는 것만으로 거짓이라 판단할 수 없다 — 기록하지 않았거나 모르는 것"이라 했고, dldusgh318은 스키마 버전 차이로 인한 조용한 누락까지 경고했다. 경로 부재를 답으로 쓰려면 "그 관계를 추출 대상으로 삼았고 추출이 누락되지 않았다"는 보장이 선행돼야 한다 — 이 중재는 위키의 추론이다 → [[온톨로지와-추론]], [[LLM-트리플-추출]].

- **왜 RAG를 먼저 했나** (do-dop): 그래프 스키마는 뭘 실패했는지 알아야 설계할 수 있다 / RAG가 시작 비용이 싸다 / 청크·LLM 모듈·평가 하네스를 그래프 단계에서 재사용한다 → [[폐쇄-스키마-설계]].
- **그래프는 새 비용을 만든다** (dldusgh318): 중복 엔티티·ID 불일치·같은 사실의 중복 표현·잘못된 관계. "다음 단계의 질문은 '그래프를 만들 수 있는가'가 아니라 '자동으로 만든 그래프를 어떻게 믿을 수 있는 그래프로 만들 것인가'." → [[엔티티-신원해소]].

## 열린 질문

- 같은 질문·같은 Gold·같은 코퍼스 범위에서 청크 하이브리드 vs 그래프를 재는 공정 비교. dldusgh318의 3주차 예고는 X01/X03으로 질문이 바뀌면서 Gold 기반 Recall 비교로는 수행되지 않았고, Yeongeunn은 스스로 불공정하다고 적었다.
- 그래프를 LLM 답변 루프의 리트리버로 연결하는 GraphRAG 단계는 전원 미착수(Yeongeunn "W6 범위").
- 집계 질문: top-k 검색은 불가능, 그래프는 가능하되 비용(e0ng의 Wikidata 집계 지연), RDB `GROUP BY`가 가장 정확(lys0611) → [[SPARQL]].

## 관련

- [[멀티홉-질문과-Bridge-Entity]] · [[RAG-실패-유형]] · [[하이브리드-검색과-RRF]] · [[그래프-적재-Postgres와-Neo4j]] · [[LLM-트리플-추출]] · [[지식그래프와-온톨로지]] · [[쿼리-재작성]]

## 출처

- dldusgh318 · 결과 보고 — [members/dldusgh318/labs/01-three-generations/WEEK5_result.md](../../members/dldusgh318/labs/01-three-generations/WEEK5_result.md); 인수인계 (§X01·X03) — [WEEK5_HANDOFF.md](../../members/dldusgh318/labs/01-three-generations/WEEK5_HANDOFF.md)
- e0ng · 지식그래프 적재와 Cypher 다중 홉 (§아하 모먼트) — [members/e0ng/labs/05-graph-store/README.md](../../members/e0ng/labs/05-graph-store/README.md) (PR #36 미머지)
- do-dop · RAG vs KG 정리 — [members/do-dop/labs/03-company-analysis-kg/rag-vs-kg-summary.md](../../members/do-dop/labs/03-company-analysis-kg/rag-vs-kg-summary.md); 못 답한 질문 — [failed_questions.md](../../members/do-dop/labs/03-company-analysis-kg/failed_questions.md); 실습 README — [README.md](../../members/do-dop/labs/03-company-analysis-kg/README.md)
- Yeongeunn · 하이브리드 평가 (§생성 관찰 q10) — [members/Yeongeunn/labs/04-hybrid-evaluation/README.md](../../members/Yeongeunn/labs/04-hybrid-evaluation/README.md); 트리플 추출·적재 (§그래프 vs 검색) — [labs/05-triple-extraction/README.md](../../members/Yeongeunn/labs/05-triple-extraction/README.md)
- heebindev · 데이터 파이프라인 (§9 다중 홉) — [members/heebindev/notes/05-rdf-owl-data-pipeline.md](../../members/heebindev/notes/05-rdf-owl-data-pipeline.md)
- kdyann · 캡션 지식 그래프 (§공통 Topic) — [members/kdyann/labs/05-content-graph/README.md](../../members/kdyann/labs/05-content-graph/README.md); 하이브리드 검색과 RAG (§다중 홉) — [notes/03-hybrid-search.md](../../members/kdyann/notes/03-hybrid-search.md)
