---
title: 멀티홉 질문과 Bridge Entity — RAG는 왜 관계를 따라가지 못하나
type: concept
tags: [concept]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [dldusgh318, e0ng, lys0611, heebindev, sunghyun, sese2204]
weeks: [1, 3]
---

> 두 개 이상의 정보를 순서대로 연결해야 답이 나오는 질문. 기본 RAG가 막히는 이유는 LLM이 추론을 못해서가 아니라 **한 번의 검색으로 필요한 정보를 다 가져오기 어렵기** 때문이다. 첫 검색 결과가 두 번째 검색어를 결정하는데, 청크에는 관계가 저장돼 있지 않다.

## 정의

- Multi-hop Question: 하나의 정보만으로 답할 수 없고 여러 정보를 순서대로 연결해야 하는 질문. Hop = 정보 → 정보의 추론 단계 (e0ng, heebindev, sunghyun).
- **Bridge Entity**: 첫 단계에서 찾은 답이 다음 검색의 연결고리가 되는 것. 그 이름은 첫 검색을 하기 전에는 검색어로 주어져 있지 않다 (dldusgh318).
- 공통 예제 "부산 같이 간 사람들 중 같은 회사 다니는 사람?"이 네 노트에 등장한다. [Hop 1] 부산 동행 = 민지/주영/지훈 → [Hop 2] 각자의 회사 → [Final] 같은 회사인 사람.

> ⚠️ Contradiction: 같은 예제의 인물·정답이 노트마다 다르다. dldusgh318 06은 민지/주영/지훈, X사·Y사, 답 "민지/주영"; e0ng은 민지/수현/지훈, A·B회사, 답 "민지와 지훈"; dldusgh318 05는 동욱/채영. 전부 가상 예시라 사실 충돌은 아니지만 인용할 때 섞지 않는다.

## 왜 실패하나 (dldusgh318)

- 2-hop 후보 문서에는 `부산`이라는 단어가 없다. BM25 기준 겹치는 term이 거의 없고, 벡터도 여행 이야기와 입사 이야기는 의미적으로 멀 수 있다. **RRF는 검색 결과를 잘 합쳐주는 기술이지 존재하지 않는 두 번째 검색을 만들어주는 기술이 아니다** → [[하이브리드-검색과-RRF]].
- 그러나 멀티홉이라고 무조건 실패하는 건 아니다. M01(2-hop)은 질문 자체에 `AFTER_COMMIT`, `FastAPI`, `Redis/RQ Worker` 같은 양쪽 청크의 단서가 들어 있어 한 번의 검색에 Gold 2/2가 모두 들어왔고 LLM이 연결해 답했다. 중요한 건 hop 수가 아니라 **필요한 청크를 한 번의 검색으로 충분히 확보할 수 있는가**. "여러 청크 조합이 필요한 것"과 "중간 결과로 재검색해야 하는 엄밀한 multi-hop retrieval"은 구분해야 한다.
- H01(3-hop, RDS 인증 실패의 원인·수정·검증): Gold 3개 중 검증 청크만 검색되고 원인·수정 청크는 실패. Oracle Context로 넣자 정확한 답. 정보는 데이터에 있었지만 독립된 텍스트 조각이라 검색기가 셋 다 찾아줘야만 LLM이 관계를 연결할 수 있었다 → [[RAG-실패-유형]].
- **집계 질문**("가장 자주", "몇 명", "모두")도 top-k 검색에는 어렵다. 결과 5개만 가져와 놓고 전체에서 누가 가장 많이 등장했는지 알 수 없다. lys0611의 집계 3문항은 모두 정직하게 거절됐다(정확도 0, 환각 없음). 최다 발신자는 정본 RDB `GROUP BY`가 먼저 정확하다 (lys0611).

## 세 갈래 처방

| 처방 | 무엇 | 한계 |
|---|---|---|
| **재검색 (Agentic Search, Iterative Retrieval)** | 검색 → 생각 → 재검색 → 답변. bridge entity로 후속 문서를 다시 찾는다 | 첫 검색이 틀리면 오류 누적, 정지 시점 판단을 LLM에 맡김, 홉마다 검색·LLM 호출 비용 증가. 관계를 매번 텍스트 검색으로 다시 찾아야 한다는 점은 그대로 (dldusgh318) |
| **쿼리 분해** | 멀티홉 질문을 서브 질문으로 미리 쪼갬 (sese2204) | 사전 분해를 전제하므로 첫 결과가 둘째 검색어를 정하는 순차 의존에는 약함 → [[쿼리-재작성]] |
| **관계를 저장** | 청크 위에 엔티티·관계를 추출해 트리플로 저장하고 관계 경로를 질의 | 추출 비용·오류, 스키마 설계. "청크는 문서 조각이고, Triple은 관계다" → [[지식그래프와-온톨로지]] |

- dldusgh318의 4주차 계획: 기존 청크를 버리지 않고 그 위에 관계 구조를 **추가**한다. `(RDS 인증 실패, caused_by, 오래된 운영 비밀번호)`, `(오래된 설정, resolved_by, 환경변수 참조)`, `(배포 정상화, verified_by, Health Check)`. 동일한 H01 질문과 Gold Chunk로 청크 하이브리드 검색 vs 관계/그래프 검색을 비교.
- lys0611의 4주차 스키마 후보(failures.md): `REQUEST(by, to, item, date)`, `PERSON –ASSIGNED_TO→ LAB_TOPIC`, `DECISION –IMPLEMENTED_BY→ TASK`, `PERSON –WORKS_AT(valid_from, valid_to)→ COMPANY`, `MEETING / ATTENDED / ABSENT`. bridge 다중 홉은 검색 단계에서 반쯤 되므로 RRF가 아니라 두 방을 잇는 **방향 있는** 엔티티 링크가 필요하다. 다만 "회사명 없이 '회사'라고만 말한 대화가 대부분이라 노드 자체를 못 만들 수 있다."
- 실험 질문은 난이도별로 만든다 (dldusgh318): 단일 홉 → 2-hop → 집계 → 3-hop → 조건 결합("작년 이후 만난 사람 중 개발자는?"). lys0611의 평가셋도 exact 12 / semantic 12 / hard 10(다중 홉·시간·집계·답 없음).

## 멤버들이 확인한 것

- dldusgh318: 위 S01/M01/A01/H01. e0ng은 실측 없이 누락 시나리오 두 방향(문서 1만 찾고 2~4 누락 / 문서 1이 누락되고 2~4만)을 제시.
- lys0611 (27문항 중 hard 3): R@5 BM25 0.833 / 벡터 0.667 / RRF 0.833. 34문항 생성 평가에서 hard 정확도 0.417. 재질의 루프는 hard 5문항에만 최대 2 hop·3회 검색으로 제한해 시도 예정("목적은 해결이 아니라 중간 질의가 어디서 어긋나는지 기록").
- kdyann이 정리한 Adaptive-RAG는 "여러 근거를 연결해야 하는 질문은 반복 검색"으로 라우팅한다 → [[RAG-변천사]].

## 관련

- [[RAG-실패-유형]] · [[RAG-루프와-근거-인용]] · [[지식그래프와-온톨로지]] · [[쿼리-재작성]] · [[하이브리드-검색과-RRF]] · [[RAG-평가-지표]]

## 출처

- dldusgh318 · Multi-hop — RAG는 왜 여러 관계를 따라가지 못할까? — [members/dldusgh318/notes/week3/06-multi-hop-rag.md](../../members/dldusgh318/notes/week3/06-multi-hop-rag.md); RAG Agent 실습 §8–14 — [labs/01-three-generations/WEEK3_rag_agent.md](../../members/dldusgh318/labs/01-three-generations/WEEK3_rag_agent.md)
- e0ng · RRF와 RAG 루프 (§Multi-hop Question) — [members/e0ng/notes/03-rrf.md](../../members/e0ng/notes/03-rrf.md)
- lys0611 · RAG 루프와 근거 인용, 실패 기록 — [members/lys0611/notes/05-rag-loop-citation-multihop.md](../../members/lys0611/notes/05-rag-loop-citation-multihop.md), [labs/02-hybrid-rag-agent/results/failures.md](../../members/lys0611/labs/02-hybrid-rag-agent/results/failures.md) (PR #15 미머지)
- heebindev · 지식 그래프 기초 용어 (§다중 홉 질문) — [members/heebindev/notes/01-knowledge-graph-glossary.md](../../members/heebindev/notes/01-knowledge-graph-glossary.md)
- sunghyun · RAG, 지식 그래프와 온톨로지 기초 — [members/sunghyun/note/01-knowledge-graph-and-ontology.md](../../members/sunghyun/note/01-knowledge-graph-and-ontology.md)
- sese2204 · 쿼리 재작성 (쿼리 분해) — [members/sese2204/notes/06-query-rewriting.md](../../members/sese2204/notes/06-query-rewriting.md)
- 외부: Tang & Yang, MultiHop-RAG (2024) https://arxiv.org/abs/2401.15391 (lys0611 인용) · When to use Graphs in RAG (ICLR 2026, lys0611 readings)
