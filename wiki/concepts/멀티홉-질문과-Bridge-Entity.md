---
title: 멀티홉 질문과 Bridge Entity — RAG는 왜 관계를 따라가지 못하나
type: concept
tags: [concept]
status: maintained
created: 2026-09-16
updated: 2026-10-02
members: [dldusgh318, e0ng, lys0611, heebindev, sunghyun, sese2204, do-dop, kungbi, Yeongeunn, yujeong430, kdyann]
weeks: [1, 3, 4, 5]
---

> 두 개 이상의 정보를 순서대로 연결해야 답이 나오는 질문. 기본 RAG가 막히는 이유는 LLM이 추론을 못해서가 아니라 **한 번의 검색으로 필요한 정보를 다 가져오기 어렵기** 때문이다. 첫 검색 결과가 두 번째 검색어를 결정하는데, 청크에는 관계가 저장돼 있지 않다. 2026-09-23 dldusgh318의 **브릿지 숨김 실험 X01**이 이 정의를 그대로 재현했다 — 질문에 `Redis`가 없고, 첫 검색은 됐지만 두 번째가 안 됐고, Oracle Context로는 답했다.

## 정의

- Multi-hop Question: 하나의 정보만으로 답할 수 없고 여러 정보를 순서대로 연결해야 하는 질문. Hop = 정보 → 정보의 추론 단계 (e0ng, heebindev, sunghyun).
- **Bridge Entity**: 첫 단계에서 찾은 답이 다음 검색의 연결고리가 되는 것. 그 이름은 첫 검색을 하기 전에는 검색어로 주어져 있지 않다 (dldusgh318).
- 공통 예제 "부산 같이 간 사람들 중 같은 회사 다니는 사람?"이 네 노트에 등장한다. [Hop 1] 부산 동행 = 민지/주영/지훈 → [Hop 2] 각자의 회사 → [Final] 같은 회사인 사람.

> ⚠️ Contradiction: 같은 예제의 인물·정답이 노트마다 다르다. dldusgh318 06은 민지/주영/지훈, X사·Y사, 답 "민지/주영"; e0ng은 민지/수현/지훈, A·B회사, 답 "민지와 지훈"; dldusgh318 05는 동욱/채영. 전부 가상 예시라 사실 충돌은 아니지만 인용할 때 섞지 않는다.

## 왜 실패하나 (dldusgh318)

- 2-hop 후보 문서에는 `부산`이라는 단어가 없다. BM25 기준 겹치는 term이 거의 없고, 벡터도 여행 이야기와 입사 이야기는 의미적으로 멀 수 있다. **RRF는 검색 결과를 잘 합쳐주는 기술이지 존재하지 않는 두 번째 검색을 만들어주는 기술이 아니다** → [[하이브리드-검색과-RRF]].
- 그러나 멀티홉이라고 무조건 실패하는 건 아니다. M01(2-hop)은 질문 자체에 `AFTER_COMMIT`, `FastAPI`, `Redis/RQ Worker` 같은 양쪽 청크의 단서가 들어 있어 한 번의 검색에 Gold 2/2가 모두 들어왔고 LLM이 연결해 답했다. 중요한 건 hop 수가 아니라 **필요한 청크를 한 번의 검색으로 충분히 확보할 수 있는가**. "여러 청크 조합이 필요한 것"과 "중간 결과로 재검색해야 하는 엄밀한 multi-hop retrieval"은 구분해야 한다.
- H01(운영 DB 인증 장애의 원인·수정·검증): Gold 3개 중 검증 청크만 검색되고 원인·수정 청크는 실패. Oracle Context로 넣자 정확한 답. 정보는 데이터에 있었지만 독립된 텍스트 조각이라 검색기가 셋 다 찾아줘야만 LLM이 관계를 연결할 수 있었다 → [[RAG-실패-유형]]. **단, 저자가 4주차에 H01의 성격을 고쳐 적었다**: 세 청크가 모두 같은 장애를 설명하는 자료이므로 "구조적인 3-hop 사례로 확정하지 않고 여러 근거를 요구하는 Retrieval 사례"로 재분류했고, 절 제목도 "Multi-hop 자체가 실패 원인은 아니었다"에서 "Multi-hop이라는 이름만으로 실패를 판정할 수 없었다"로 바꿨다. 멀티홉의 근거는 아래 X01로 옮긴다.
- **X01 — 브릿지가 숨은 질문** (dldusgh318, 2026-09-23 추가 실험): "프로젝트 A에서 작업 큐에 사용한 기술을 다른 프로젝트에서도 사용했는가?" 사람은 `프로젝트 A → 작업 큐로 Redis` 와 `프로젝트 B → 집계 캐시로 Redis`를 잇는다. **질문에 `Redis`라는 단어가 없다.** 먼저 프로젝트 A·작업 큐 청크를 찾아 Redis를 알아낸 뒤 다른 프로젝트의 Redis 기록을 다시 찾아야 하는데, 실제로 첫 번째 정보는 찾았고 두 번째가 검색되지 않아 실패했다. Normal 실패 / Oracle 성공 → Retrieval 실패. 같은 조건의 X02(Health Check·rollback 숨김)는 **Oracle도 틀렸고**(Composition 실패), X03(캐시 숨김)은 Normal이 오조합+Citation 실패, Oracle 정답(Composition 실패). 저자 스스로 "질문이 세 개뿐이므로 일반화하지 않는다".
- **집계 질문**("가장 자주", "몇 명", "모두")도 top-k 검색에는 어렵다. 결과 5개만 가져와 놓고 전체에서 누가 가장 많이 등장했는지 알 수 없다. lys0611의 집계 3문항은 모두 정직하게 거절됐다(정확도 0, 환각 없음). 최다 발신자는 정본 RDB `GROUP BY`가 먼저 정확하다 (lys0611).

## 세 갈래 처방

| 처방 | 무엇 | 한계 |
|---|---|---|
| **재검색 (Agentic Search, Iterative Retrieval, IRCoT)** | 검색 → 생각 → 재검색 → 답변. bridge entity로 후속 문서를 다시 찾는다 | 첫 검색이 틀리면 오류 누적, 정지 시점 판단을 LLM에 맡김, 홉마다 검색·LLM 호출 비용 증가. 관계를 매번 텍스트 검색으로 다시 찾아야 한다는 점은 그대로 (dldusgh318). **do-dop 실측**: `exaone3.5:2.4b`는 재질의를 한 번도 안 하고 근거 제목을 베꼈고(자기 점검 불가), `7.8b`는 재질의로 정답 문서를 찾아왔지만 `ANSWER` 없이 표현만 바꾼 `SEARCH`를 반복(`--max-hops` 6까지 동일)하며 **이미 쥔 두 사실을 잇지 못했다**. error propagation을 그대로 겪었다 |
| **쿼리 분해** | 멀티홉 질문을 서브 질문으로 미리 쪼갬 (sese2204) | 사전 분해를 전제하므로 첫 결과가 둘째 검색어를 정하는 순차 의존에는 약함 → [[쿼리-재작성]]. **do-dop 실측**: 같은 문서 안의 얕은 멀티홉(q009)은 분해로 정답, 회사가 다른 두 소스를 조인해야 하는 질문은 하위 질의가 독립 생성돼 근거 15개가 섞인 회피성 답변 |
| **관계를 저장** | 청크 위에 엔티티·관계를 추출해 트리플로 저장하고 관계 경로를 질의 | 추출 비용·오류, 스키마 설계. "청크는 문서 조각이고, Triple은 관계다" → [[지식그래프와-온톨로지]] |

- dldusgh318의 4주차 설계(2026-09-23, 3주차 예고와 다르다): 기존 청크를 버리지 않고 그 위에 관계 구조를 **추가**하되, 트리플 셋이 아니라 중간 노드 `TechnologyUse`에 `PART_OF` / `USES_TECHNOLOGY` / `HAS_PURPOSE` / `HAS_STATUS` 네 관계를 매단 **작은 폐쇄형 스키마**다(3주차에 예고했던 `caused_by`·`resolved_by`·`verified_by`는 4주차 소재에 등장하지 않는다). X01을 그래프로 그리면 Redis가 두 프로젝트를 잇는 브릿지 노드가 되고, 문제가 "질문과 비슷한 문서를 찾아라"에서 **"찾은 Entity와 연결된 관계를 따라가라"**로 바뀐다. 5주차 비교는 정확도가 아니라 "어떤 방식이 필요한 근거를 더 잘 가져오는지"이고, 가설은 좁다 — "서술적으로 비슷한 문서는 기존 검색이 잘 처리하고, 여러 문서에 흩어진 관계를 따라가야 하는 질문에서 명시적 그래프가 도움이 될 수 있다." 그래프가 검색을 대체한다고 가정하지 않는다 → [[RDF와-트리플]], [[온톨로지와-추론]], [[지식그래프와-온톨로지]].
- **그래프에서 홉은 변수 공유다**: SPARQL은 두 트리플 패턴이 같은 변수를 쓰면 조인이 되고, 패턴을 이으면 멀티홉 질의가 된다(dldusgh318, lys0611). 전제는 관계가 제대로 추출·저장돼 있다는 것 — "잘못된 관계를 저장하면 SPARQL은 그 잘못된 관계를 아주 정확하게 조회할 뿐이다" → [[SPARQL]].
- lys0611의 4주차 방법론(스터디 공통 예제 기준, 자기 카톡 스키마와는 다른 데이터셋): 질문 선택 → 필요한 사실 분해(A·B가 부산여행 참가, A·B가 회사 X 근무) → **명사 = Node, 동사 = Relationship**(클래스 사람·여행·회사, 관계 참가·근무) → 경로 연결 → Hop 수 확인. "텍스트 검색에서는 흩어진 사실을 모두 가져와야 하지만 그래프에서는 조인·경로 탐색 문제로 표현할 수 있다." failures.md의 "회사명 없이 '회사'라고만 말한 대화가 대부분이라 노드를 못 만들 수 있다"는 우려에는 아직 답이 없다.
- e0ng의 GraphRAG 3단계: ① 원본 → 청킹 → 개체·관계 추출 → KG 저장, ② 질문의 Entity 식별 → 관련 Entity·Relationship 탐색 → **연결된 원본 청크** 검색, ③ 관계 + 근거 청크 → LLM. 실패 원인을 "벡터 검색이 질문과 청크를 개별적으로 비교한다"는 스코어링 층위로 설명한다. 네 멤버의 층위 차이(분포·스코어링·융합·표현)는 [[시맨틱-웹에서-지식그래프까지]].
- lys0611의 4주차 스키마 후보(failures.md): `REQUEST(by, to, item, date)`, `PERSON –ASSIGNED_TO→ LAB_TOPIC`, `DECISION –IMPLEMENTED_BY→ TASK`, `PERSON –WORKS_AT(valid_from, valid_to)→ COMPANY`, `MEETING / ATTENDED / ABSENT`. bridge 다중 홉은 검색 단계에서 반쯤 되므로 RRF가 아니라 두 방을 잇는 **방향 있는** 엔티티 링크가 필요하다. 다만 "회사명 없이 '회사'라고만 말한 대화가 대부분이라 노드 자체를 못 만들 수 있다."
- 실험 질문은 난이도별로 만든다 (dldusgh318): 단일 홉 → 2-hop → 집계 → 3-hop → 조건 결합("작년 이후 만난 사람 중 개발자는?"). lys0611의 평가셋도 exact 12 / semantic 12 / hard 10(다중 홉·시간·집계·답 없음).

## 멤버들이 확인한 것

- dldusgh318: 위 S01/M01/A01/H01과 X01–X03. e0ng은 3주차에는 실측 없이 누락 시나리오 두 방향을 제시했고, **5주차에 실제 그래프로 풀었다** — 3주차 RAG가 "역량검사" 청크와 기업명 청크를 따로 검색해 못 이은 질문을 `(Organization)<-[:RELATED_TO_ORGANIZATION]-(Activity)-[:HAS_DOCUMENT]->(Document)` 한 경로로 3행 반환(PR #36 미머지) → [[RAG-vs-그래프-질의]].
- **다중 홉이라고 그래프가 필요한 건 아니다**: Yeongeunn q10(서비스·메서드·경로)은 RRF가 정확히 답했다 — "이번 다중 홉 질문은 텍스트 RAG로도 답할 수 있었음", 그래프까지 만든 뒤에도 "'다중 홉은 RAG로 불가능하다'고 해석하지 않는다". kdyann 3주차 노트도 "반드시 그래프가 필요한 것은 아니다 — 질문 분해·추가 검색 같은 보완책이 있다". yujeong430·Yeongeunn 둘 다 평가셋의 `multi_evidence`·다중홉 문항이 "관계를 따라가는 다중 홉이 아니라 여러 근거 청크를 한 번에 회수하는지"를 잰다고 구분했고, do-dop도 q009가 같은 문서 안이라 검색 한 번으로 풀린다고 자인했다. **세 멤버가 독립적으로 "정답이 여러 청크에 있음" ≠ "여러 문서를 조인해야 함"에 도달했다.** 반대로 3주차에 다중 홉 실측에 도달한 멤버는 dldusgh318·lys0611·do-dop뿐이고 heebindev("답하지 못한 질문을 아직 찾지 못했다")·sunghyun("다중 홉 실패 실습은 아직")은 공백으로 남겼다.
- **못 답한 질문을 그래프로 바꾸는 5칸 템플릿** (kungbi): 질문 / 필요한 대상(노드) / 필요한 관계(화살표) / 답하려면 필요한 근거 / 현재 빠진 사실 또는 불확실한 연결. "답을 먼저 만들지 말고 필요한 사실의 모양부터 그린다." 그래야 관계 부재 / 엔티티 식별 실패 / 데이터 미수집을 구별한다. lys0611의 명사=Node·동사=Relationship 절차, dldusgh318의 X01 그래프, kdyann의 "계약을 별도 대상으로 승격"(회사에 지급기한을 직접 붙이면 개정 계약을 구분 못 함 → 회사 → 계약 → 조건·근거문서)과 같은 처방이다.
- 유형 분류 (yujeong430): 연결(bridge)·교집합·비교·시간 순서. 어려운 이유에 "'그 사람'·지시 표현이 섞이면 동일 대상 연결이 어렵다", "비어 있는 연결을 추측한다"를 추가. "상위 문서를 단순히 늘리는 것만으로 해결되지 않는다." MultiHop-RAG 벤치마크의 질의 4종은 Inference·Comparison·Temporal·Null (do-dop). HotpotQA의 핵심은 답뿐 아니라 **supporting facts**를 문장 단위로 제공하는 것 — `Fact A + Fact B → Answer`는 Claim → Evidence와 같은 모양 (do-dop).
- RAGAS 합성기 `MultiHopSpecificQuerySynthesizer`가 엔티티 겹침 엣지로 bridge 평가셋을 자동 생성한다 (sese2204) — lys0611의 "50문항 확대" TODO와 직결 → [[RAGAS]].
- lys0611 (27문항 중 hard 3): R@5 BM25 0.833 / 벡터 0.667 / RRF 0.833. 34문항 생성 평가에서 hard 정확도 0.417. 재질의 루프는 hard 5문항에만 최대 2 hop·3회 검색으로 제한해 시도 예정("목적은 해결이 아니라 중간 질의가 어디서 어긋나는지 기록").
- kdyann이 정리한 Adaptive-RAG는 "여러 근거를 연결해야 하는 질문은 반복 검색"으로 라우팅한다 → [[RAG-변천사]].
- 시간 조건: "관계에 `valid_from/valid_to`가 없으면 '지금'에 답할 수 없다"(lys0611 G3)는 Wikidata 한정어와 같은 처방이고, Yeongeunn은 `review_status`·`valid_from/to`·`source_version`으로 번역했다. kdyann의 열린 질문 "계약이 개정되면 과거 조건과 현재 유효 조건을 어떻게 구분할까"도 같은 자리 → [[Wikidata와-DBpedia]].
- 집계 질문은 그래프에서는 가능하되 비용이 든다 — e0ng이 Wikidata에서 돌린 `COUNT … GROUP BY` 질의가 단순 조회보다 체감상 오래 걸렸다(수치 없음) → [[SPARQL]]. 경로 길이는 관계 수로 세고, "경로가 없다 ≠ 관계가 없다"(열린 세계 가정, do-dop) → [[온톨로지와-추론]].

## 관련

- [[RAG-실패-유형]] · [[RAG-루프와-근거-인용]] · [[지식그래프와-온톨로지]] · [[쿼리-재작성]] · [[하이브리드-검색과-RRF]] · [[RAG-평가-지표]] · [[SPARQL]] · [[RDF와-트리플]] · [[온톨로지와-추론]] · [[시맨틱-웹에서-지식그래프까지]]

## 출처

- dldusgh318 · Multi-hop — RAG는 왜 여러 관계를 따라가지 못할까? — [members/dldusgh318/notes/week3/06-multi-hop-rag.md](../../members/dldusgh318/notes/week3/06-multi-hop-rag.md); RAG Agent 실습 §8–14, §12 브릿지 숨김 X01–X03 (2026-09-23 개정) — [labs/01-three-generations/WEEK3_rag_agent.md](../../members/dldusgh318/labs/01-three-generations/WEEK3_rag_agent.md); W4 못 답한 질문을 그래프로 표현해보기 — [notes/week4/w4_failed_question_graph.md](../../members/dldusgh318/notes/week4/w4_failed_question_graph.md); SPARQL 맛보기 — [notes/week4/02-sparql.md](../../members/dldusgh318/notes/week4/02-sparql.md)
- e0ng · 지식 그래프의 변천사 (§GraphRAG), RDF·OWL·SPARQL (§못 답한 질문) — [members/e0ng/notes/04-1-knowledge-graph-history.md](../../members/e0ng/notes/04-1-knowledge-graph-history.md), [04-2-knowledge-graph-basics.md](../../members/e0ng/notes/04-2-knowledge-graph-basics.md)
- lys0611 · 지식 그래프의 배경 (§6 방법론) — [members/lys0611/notes/06-knowledge-graph-foundations.md](../../members/lys0611/notes/06-knowledge-graph-foundations.md)
- e0ng · RRF와 RAG 루프 (§Multi-hop Question) — [members/e0ng/notes/03-rrf.md](../../members/e0ng/notes/03-rrf.md)
- lys0611 · RAG 루프와 근거 인용, 실패 기록 — [members/lys0611/notes/05-rag-loop-citation-multihop.md](../../members/lys0611/notes/05-rag-loop-citation-multihop.md), [labs/02-hybrid-rag-agent/results/failures.md](../../members/lys0611/labs/02-hybrid-rag-agent/results/failures.md)
- heebindev · 지식 그래프 기초 용어 (§다중 홉 질문) — [members/heebindev/notes/01-knowledge-graph-glossary.md](../../members/heebindev/notes/01-knowledge-graph-glossary.md)
- sunghyun · RAG, 지식 그래프와 온톨로지 기초 — [members/sunghyun/note/01-knowledge-graph-and-ontology.md](../../members/sunghyun/note/01-knowledge-graph-and-ontology.md)
- sese2204 · 쿼리 재작성 (쿼리 분해) — [members/sese2204/notes/06-query-rewriting.md](../../members/sese2204/notes/06-query-rewriting.md)
- do-dop · 멀티홉에서 KG로, 못 답한 질문 — [members/do-dop/notes/03-multihop-to-kg.md](../../members/do-dop/notes/03-multihop-to-kg.md), [labs/03-company-analysis-kg/failed_questions.md](../../members/do-dop/labs/03-company-analysis-kg/failed_questions.md)
- kungbi · W4 지식 그래프의 배경 (§7 템플릿) — [members/kungbi/notes/02-knowledge-graph-background.md](../../members/kungbi/notes/02-knowledge-graph-background.md)
- Yeongeunn · 지식 그래프와 온톨로지 (§멀티홉), 평가 실습 (q10), 트리플 적재 실습 — [members/Yeongeunn/notes/09-week4-ontology-background.md](../../members/Yeongeunn/notes/09-week4-ontology-background.md), [labs/04-hybrid-evaluation/README.md](../../members/Yeongeunn/labs/04-hybrid-evaluation/README.md), [labs/05-triple-extraction/README.md](../../members/Yeongeunn/labs/05-triple-extraction/README.md)
- yujeong430 · 다중 홉 질문 — [members/yujeong430/notes/08-multi-hop-questions.md](../../members/yujeong430/notes/08-multi-hop-questions.md) (PR #19 미머지)
- kdyann · 하이브리드 검색과 RAG (§다중 홉), SPARQL·계약 모델링 실습 — [members/kdyann/notes/03-hybrid-search.md](../../members/kdyann/notes/03-hybrid-search.md), [labs/04-sparql-graph/README.md](../../members/kdyann/labs/04-sparql-graph/README.md)
- e0ng · 지식그래프 적재와 Cypher 다중 홉 — [members/e0ng/labs/05-graph-store/README.md](../../members/e0ng/labs/05-graph-store/README.md) (PR #36 미머지)
- 외부: Tang & Yang, MultiHop-RAG (2024) https://arxiv.org/abs/2401.15391 (lys0611·do-dop 인용) · When to use Graphs in RAG (ICLR 2026, lys0611 readings) · Yang et al., HotpotQA (EMNLP 2018) https://aclanthology.org/D18-1259/ · Trivedi et al., IRCoT (ACL 2023) https://aclanthology.org/2023.acl-long.557/ (do-dop readings — 재검색 처방의 논문 근거)
