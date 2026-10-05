---
title: RAG 실패 유형 — 어디서 끊겼는지 기록하는 법
type: concept
tags: [concept, comparison]
status: maintained
created: 2026-09-16
updated: 2026-10-02
members: [dldusgh318, lys0611, e0ng, sese2204, kungbi, do-dop, Yeongeunn, yujeong430, kdyann]
weeks: [3, 4, 5]
---

> "RAG가 안 됐다"가 아니라 "왜 안 됐는가"를 남기기 위한 분류 체계. 네 멤버가 각자 다른 축으로 나눴고, 이 페이지는 그것들을 한 표에 대응시킨다. 실측으로는 dldusgh318의 Oracle Context 실험과 lys0611의 R0~G4 코드 분류가 있다.

## 네 가지 분류 축

| 축 | 누가 | 분류 |
|---|---|---|
| 파이프라인 단계 (5종) | dldusgh318 05 | `retrieval` 못 찾음 / `assembly` 찾았는데 못 넘김 / `generation` 있는데 못 씀 / `citation` 답은 했는데 엉뚱한 근거 / `no_data` 애초에 없음 |
| 파이프라인 단계 (4종) | dldusgh318 06 | `retrieval` / `assembly` / `composition` / `no_data` |
| 실패 원인 (4종) | e0ng | 검색 실패(표현 불일치) / Ranking 실패(검색은 됐지만 Top-K → Reranker → Top-N에서 탈락) / Context 한계(토큰 예산 초과로 제외) / Multi-hop(단일 검색으로 근거 확보 불가) |
| 단계 코드 (8종) | lys0611 failures.md | **R0** 데이터 부재 / **R1** 검색 실패(top-5 밖 또는 후보 50 밖) / **R2** 부분 검색(다중 홉 근거 일부만) / **C1** 조립 실패 / **G1** 집계 불가 / **G2** 관계 조인 불가 / **G3** 시간 유효성 / **G4** 생성 실패 |
| 두 층 | sese2204 07 | **검색 실패**(관련 청크가 top-k에 없었다) vs **생성 실패**(있었는데 못 썼다). 반드시 구분 |

> ⚠️ Contradiction: 같은 저자 dldusgh318의 두 노트가 다르다. 05는 `generation`·`citation`을 포함한 5종, 06은 `composition`을 쓰는 4종. 출처: [05](../../members/dldusgh318/notes/week3/05-rag-loop.md) §7, [06](../../members/dldusgh318/notes/week3/06-multi-hop-rag.md) §7. 2026-09-23 개정된 실습 문서와 README는 실제 판정에 `retrieval`·`composition`·`citation`을 썼으므로(브릿지 숨김 3문항: retrieval 1, composition 2) 운영 분류는 06 쪽으로 수렴했다. 이 위키는 lys0611의 코드 체계를 정본으로 쓰고 다른 분류는 거기에 대응시킨다: dldusgh318 `retrieval` = R1/R2, `assembly` = C1, `generation`/`composition` = G4, `citation` = G4의 하위(인용 검증 실패), `no_data` = R0; e0ng의 Ranking 실패 = R1(후보 50 안에는 있었음), Context 한계 = C1, Multi-hop = R2.

kungbi의 Retrieval(후보 찾기) vs Validation(현재 원문으로 검증)은 실패 분류가 아니라 프로세스 단계 분해다. 섞어 쓰지 않는다 → [[OpenViking-컨텍스트-데이터베이스]].

## 2026-10-02 추가 — 코드가 없는 실패들

- **검색 성공 + 융합 탈락** (do-dop): BM25가 20후보 중 1위(21.56점)로 정확히 찾은 정답이 벡터 후보에 없다는 이유로 RRF에서 11위로 밀렸다. 처음엔 "검색 실패"로 판단했다가 확인하니 융합 단계였다 — "구분 안 했으면 임베딩 모델 교체 같은 엉뚱한 곳을 고쳤을 것". lys0611 코드로는 R1도 C1도 아니다(후보 50 안에는 있었고 조립 전이다). e0ng의 Ranking 실패와 가깝지만 범인이 리랭커가 아니라 RRF 자체. 같은 메커니즘을 heebindev·sunghyun·Yeongeunn도 관측했다 → [[하이브리드-검색과-RRF]].
- **엔티티 귀속 오류 / 정답 없는 질문의 과잉 확신** (do-dop): 코퍼스에 정답이 없는 질문에서 top-k를 넓히자 주제가 비슷한 다른 회사의 사실로 자신 있게 틀린 답. 근거마다 회사를 명시해도 "질문의 전제와 안 맞는다"는 걸 못 알아챈다. 모델을 2.4b → 7.8b로 키워도 "이 근거가 질문이 가리키는 그 회사의 것이 맞는지"는 검증하지 못했다. 독립 분해(`--decompose`)는 하위 질의가 앞 결과를 넘겨받지 않아 두 회사 근거를 섞은 회피성 답변 → [[쿼리-재작성]].
- **연결 실패** — 청크는 다 찾았는데 동일 인물·사건·시간을 잘못 잇는 것. lys0611 "관계 방향 1건"(G4 안), Yeongeunn q10(근거를 다 찾고 서비스와 거래 유형을 혼동), yujeong430의 실패 4유형 중 하나(근거 검색 실패 / **연결 실패** / 근거 부족 / 답변 근거성 실패). 세 멤버가 독립적으로 같은 범주에 닿았고, Yeongeunn 09는 "검색이 문서 B를 놓친 경우와 두 문서를 찾았지만 대상을 잘못 연결한 경우는 다른 오류"라고 선을 그었다.
- **라벨의 대체 근거 누락** (Yeongeunn q05): 지정 근거를 놓쳤지만 대체 문서로 맞게 답해 "답은 맞는데 점수 0". dldusgh318 A01(Gold 누락 ≠ 검색 실패)의 반복. 평가셋이 실패한 것.
- do-dop이 MultiHop-RAG 논문에 대응시킨 **멀티홉 실패 7유형**: Retrieval / Coverage(근거 일부만) / Entity(다른 회사를 연결) / Temporal / Metric / Scope / Relation(공급 방향 역전). **논문이 정의한 것은 질의 4종(Inference·Comparison·Temporal·Null)이고 7유형은 do-dop의 구성이다.** 7개 중 직접 확인한 것은 Coverage(q009, 정답 3개 중 2개)와 Entity 둘뿐이고 나머지 다섯은 "아직 테스트 안 함". Entity·Metric·Scope는 R0~G4에 대응 코드가 없다. do-dop의 통찰: **"실패 유형표가 곧 KG 엣지 속성 설계표"** — Entity는 다른 노드라 섞일 수 없고, Relation은 엣지 방향이 명시되고, Temporal·Scope·Metric은 엣지에 `period`·`scope`·`unit`을 달면 혼동이 준다 → [[RAG-vs-그래프-질의]].
- kungbi의 그래프 쪽 3분할: 못 답하는 이유가 **관계가 없어서**인지 / **원문은 있지만 엔티티 식별이 안 돼서**인지 / **애초에 데이터가 수집되지 않아서**인지를 구별한다 → [[멀티홉-질문과-Bridge-Entity]].

## Oracle Context 실험 (dldusgh318)

- 검색 단계를 건너뛰고 사람이 정답 청크를 직접 LLM에 넣어 **추론 문제인지 검색 문제인지** 가른다. Context만 바꾸고 조립 방식·LLM·프롬프트·인용 검증은 동일하게 고정.

| 일반 RAG | Oracle | 판정 |
|---|---|---|
| ❌ | ✅ | 검색 문제 |
| ❌ | ❌ | 추론/생성 문제 |
| ✅ | ✅ | 기존 RAG로 해결 가능 |

- 실측 4사례 (Notion 1,562청크, Hybrid top-5):

| 사례 | 유형 | Normal | Oracle | 최종 판정 |
|---|---|---|---|---|
| S01 | Single-hop | 정답 | 정답 | 성공 |
| M01 | 2-hop | 정답 | 정답 | 성공 (Gold 2/2가 한 번의 검색에 들어옴) |
| A01 | Aggregation | 정답 | 정답 | **Citation 실패** (Gold 3개 중 1개만 검색됐는데 답은 맞음, 인용 1건 불일치) |
| H01 | 3-hop 후보 → Retrieval 질문으로 재분류 | 불완전 | 정답 | **Retrieval 실패** (Gold 3개 중 검색 1 / 실패 2) |
| X01 | 브릿지 숨김 (Redis) | 실패 | 정답 | **Retrieval 실패** — 첫 홉은 찾고 두 번째 홉 미검색 → [[멀티홉-질문과-Bridge-Entity]] |
| X02 | 브릿지 숨김 (Health Check·rollback) | rollback만 답함 | **rollback만 답함** | **Composition 실패** (+Normal에 Retrieval 문제 공존). **Oracle도 틀렸다** |
| X03 | 브릿지 숨김 (캐시) | 오조합 + Citation 실패 | 정답 | **Composition 실패** (부수 Citation) |

- **Gold Chunk ID 누락 ≠ 검색 실패** (A01): 같은 프로젝트 경험이 팀피셜 원본·A/B/C기업 포트폴리오·경력기술서에 중복 기록돼 있어 Gold ID를 놓쳐도 다른 청크가 같은 정보를 줬다. Retrieval Coverage 1/3 = 0.333인데 답은 정확. "Recall은 검색기 비교에 유용하지만 실제 RAG에서는 최종 Context에 필요한 정보가 있는지와 LLM이 그걸로 답했는지까지 봐야 한다." **Recall과 Answerability는 다르다** → [[RAG-평가-지표]].
- Oracle Context 실험의 두 번째 사례 (Yeongeunn q02): 세 방식 모두 R@5 0인 질문에 지정 근거를 직접 주자 답했다 — "모든 실패의 원인을 증명하지는 않는다"는 유보와 함께.
- **Oracle이 항상 성공하지는 않는다** (X02, 2026-09-23 추가). 정답 청크를 손으로 넣어도 LLM이 Health Check를 빠뜨렸다. 그래서 Oracle 성공/실패가 Retrieval(검색 문제)과 Composition(조립·생성 문제)을 **가르는 장치**다. 저자는 "질문이 세 개뿐이므로 일반화하지 않는다"고 적었다. lys0611 코드로는 X01 = R1/R2, X02·X03 = G4.
- 실험 질문은 단일 홉을 **대조군**으로 함께 넣어야 한다. 단일 홉은 되는데 멀티홉부터 실패하면 검색 시스템 전체가 망가진 게 아니라 정보 연결에서 문제가 생긴다는 걸 보일 수 있다.
- 기록 스키마(YAML): `question / expected / retrieved / missing / oracle_test / failure_type`.

## lys0611의 실측 (카카오톡 1,922청크, 34문항)

- 검색 실패 2건은 모두 **구조화된 정보**(요청 목록 `– / 19 / 39`, 실습 배분표 `– / 36 / 65`)였다. nori는 `맡았어`와 표의 `-`를 연결할 수 없다. 문장 검색이 아니라 관계 질의가 맞는 자리 → [[지식그래프와-온톨로지]].
- R2 부분 검색: "Lab8을 curl에서 무엇으로 바꿨어?"의 두 번째 근거가 BM25 8위 → RRF 11위로 밀렸다. 두 방을 가로지르는 **방향 있는** 엔티티 링크가 필요하다.
- C1 조립 위험: "11월 9일 회식"은 제안 청크와 한 시간 뒤 취소 청크가 RRF 3위·1위로 둘 다 들어왔지만 취소 **이유**는 어느 청크에도 없다(C1 → R0). 이유를 지어내면 G4.
- G1 집계 3문항(최다 언급 기능·회의 최다 참석·최다 발신자): 최다 발신자는 정본 RDB `GROUP BY`로 바로 나오므로 그래프보다 SQL 도구가 맞는 자리, 회의 참석은 대화에서 이벤트·참석을 추출해야 셀 수 있으므로 그래프의 일.
- G3 시간 유효성 2문항: 관계에 `valid_from/valid_to`가 없으면 "지금"에 답할 수 없다.
- G4 생성 실패 12건의 유형별 건수는 [[RAG-루프와-근거-인용]]에. 절반은 그래프와 무관한 프롬프트·조립 문제이고, W4 그래프로 넘길 것은 **시간 축 붕괴**와 **관계 방향** 두 유형.
- 라벨 오류 자인 2건: 청크 경계 건에서 두 청크를 대체 가능으로 묶은 것, 판교 질문에 날짜 앵커가 없던 것. 평가셋도 실패한다.

## 부정 질문과 답 없음 — 왜 근본적으로 어려운가

- "아직 구현하지 않은 기능은?"에 답하려면 `구현 기록 없음 ≠ 구현하지 않음`의 간극을 메워야 하고, 그러려면 "내가 가진 목록이 전체다"라는 **닫힌 세계 가정**이 필요하다. RDF·온톨로지는 반대로 **열린 세계**(적혀 있지 않은 것은 거짓이 아니라 모름)를 전제한다. 3주차에 답 없음 문항(R0)을 별도 실패 유형으로 다룬 이유가 여기 있다 (dldusgh318 4주차, do-dop·lys0611 동일) → [[온톨로지와-추론]]. 그래프로 가도 "없다"를 더 확신 있게 말하게 할 뿐 답이 생기지는 않는다 → [[RAG-루프와-근거-인용]].

## 관련

- [[RAG-루프와-근거-인용]] · [[멀티홉-질문과-Bridge-Entity]] · [[RAG-평가-지표]] · [[지식그래프와-온톨로지]] · [[OpenViking-컨텍스트-데이터베이스]] · [[온톨로지와-추론]]

## 출처

- dldusgh318 · RAG (§7 실패 기록), Multi-hop (§3 Oracle, §7 실패 기록, §8 대조군) — [members/dldusgh318/notes/week3/05-rag-loop.md](../../members/dldusgh318/notes/week3/05-rag-loop.md), [06-multi-hop-rag.md](../../members/dldusgh318/notes/week3/06-multi-hop-rag.md); 실습 §7–12 (2026-09-23 개정, X01–X03) — [labs/01-three-generations/WEEK3_rag_agent.md](../../members/dldusgh318/labs/01-three-generations/WEEK3_rag_agent.md), [README.md](../../members/dldusgh318/README.md); RDFS와 OWL (§OWA) — [notes/week4/03-rdfl&owl.md](../../members/dldusgh318/notes/week4/03-rdfl&owl.md)
- lys0611 · 못 답하는 질문 — 실패 단계별 기록 — [members/lys0611/labs/02-hybrid-rag-agent/results/failures.md](../../members/lys0611/labs/02-hybrid-rag-agent/results/failures.md); RAG 루프 노트 — [notes/05-rag-loop-citation-multihop.md](../../members/lys0611/notes/05-rag-loop-citation-multihop.md)
- e0ng · RRF와 RAG 루프 (§RAG의 한계) — [members/e0ng/notes/03-rrf.md](../../members/e0ng/notes/03-rrf.md)
- sese2204 · RAG 평가와 실습 로드맵 (§실패 분해) — [members/sese2204/notes/07-rag-evaluation.md](../../members/sese2204/notes/07-rag-evaluation.md)
- kungbi · OpenViking (§검색 결과가 곧 현재의 근거는 아니다) — [members/kungbi/notes/01-openviking-context-database.md](../../members/kungbi/notes/01-openviking-context-database.md)
- do-dop · RAG 루프 (§진단), 멀티홉에서 KG로 (7유형), 못 답한 질문 — [members/do-dop/notes/03-rag-loop.md](../../members/do-dop/notes/03-rag-loop.md), [03-multihop-to-kg.md](../../members/do-dop/notes/03-multihop-to-kg.md), [labs/03-company-analysis-kg/failed_questions.md](../../members/do-dop/labs/03-company-analysis-kg/failed_questions.md)
- Yeongeunn · 평가 실습 (§생성 관찰), 지식 그래프와 온톨로지 (§검색 실패 vs 연결 실패) — [members/Yeongeunn/labs/04-hybrid-evaluation/README.md](../../members/Yeongeunn/labs/04-hybrid-evaluation/README.md), [notes/09-week4-ontology-background.md](../../members/Yeongeunn/notes/09-week4-ontology-background.md)
- yujeong430 · 다중 홉 질문 (§실패 유형) — [members/yujeong430/notes/08-multi-hop-questions.md](../../members/yujeong430/notes/08-multi-hop-questions.md) (PR #19 미머지)
- kungbi · W4 지식 그래프의 배경 (§7) — [members/kungbi/notes/02-knowledge-graph-background.md](../../members/kungbi/notes/02-knowledge-graph-background.md)
- 외부: Tang & Yang, MultiHop-RAG https://arxiv.org/abs/2401.15391 (do-dop)
