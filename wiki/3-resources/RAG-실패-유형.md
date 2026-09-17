---
title: RAG 실패 유형 — 어디서 끊겼는지 기록하는 법
type: resource
tags: [concept, comparison]
status: maintained
created: 2026-09-16
updated: 2026-09-16
members: [dldusgh318, lys0611, e0ng, sese2204, kungbi]
weeks: [3]
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

> ⚠️ Contradiction: 같은 저자 dldusgh318의 두 노트가 다르다. 05는 `generation`·`citation`을 포함한 5종, 06은 `composition`을 쓰는 4종. 출처: [05](../../members/dldusgh318/notes/week3/05-rag-loop.md) §7, [06](../../members/dldusgh318/notes/week3/06-multi-hop-rag.md) §7. 이 위키는 lys0611의 코드 체계를 정본으로 쓰고 다른 분류는 거기에 대응시킨다: dldusgh318 `retrieval` = R1/R2, `assembly` = C1, `generation`/`composition` = G4, `citation` = G4의 하위(인용 검증 실패), `no_data` = R0; e0ng의 Ranking 실패 = R1(후보 50 안에는 있었음), Context 한계 = C1, Multi-hop = R2.

kungbi의 Retrieval(후보 찾기) vs Validation(현재 원문으로 검증)은 실패 분류가 아니라 프로세스 단계 분해다. 섞어 쓰지 않는다 → [[OpenViking-컨텍스트-데이터베이스]].

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
| H01 | 3-hop | 불완전 | 정답 | **Retrieval 실패** (Gold 3개 중 검색 1 / 실패 2) |

- **Gold Chunk ID 누락 ≠ 검색 실패** (A01): 같은 프로젝트 경험이 팀피셜 원본·A/B/C기업 포트폴리오·경력기술서에 중복 기록돼 있어 Gold ID를 놓쳐도 다른 청크가 같은 정보를 줬다. Retrieval Coverage 1/3 = 0.333인데 답은 정확. "Recall은 검색기 비교에 유용하지만 실제 RAG에서는 최종 Context에 필요한 정보가 있는지와 LLM이 그걸로 답했는지까지 봐야 한다." **Recall과 Answerability는 다르다** → [[RAG-평가-지표]].
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

## 관련

- [[RAG-루프와-근거-인용]] · [[멀티홉-질문과-Bridge-Entity]] · [[RAG-평가-지표]] · [[지식그래프와-온톨로지]] · [[OpenViking-컨텍스트-데이터베이스]]

## 출처

- dldusgh318 · RAG (§7 실패 기록), Multi-hop (§3 Oracle, §7 실패 기록, §8 대조군) — [members/dldusgh318/notes/week3/05-rag-loop.md](../../members/dldusgh318/notes/week3/05-rag-loop.md), [06-multi-hop-rag.md](../../members/dldusgh318/notes/week3/06-multi-hop-rag.md); 실습 §7–11 — [labs/01-three-generations/WEEK3_rag_agent.md](../../members/dldusgh318/labs/01-three-generations/WEEK3_rag_agent.md)
- lys0611 · 못 답하는 질문 — 실패 단계별 기록 — [members/lys0611/labs/02-hybrid-rag-agent/results/failures.md](../../members/lys0611/labs/02-hybrid-rag-agent/results/failures.md); RAG 루프 노트 — [notes/05-rag-loop-citation-multihop.md](../../members/lys0611/notes/05-rag-loop-citation-multihop.md) (PR #15 미머지)
- e0ng · RRF와 RAG 루프 (§RAG의 한계) — [members/e0ng/notes/03-rrf.md](../../members/e0ng/notes/03-rrf.md)
- sese2204 · RAG 평가와 실습 로드맵 (§실패 분해) — [members/sese2204/notes/07-rag-evaluation.md](../../members/sese2204/notes/07-rag-evaluation.md)
- kungbi · OpenViking (§검색 결과가 곧 현재의 근거는 아니다) — [members/kungbi/notes/01-openviking-context-database.md](../../members/kungbi/notes/01-openviking-context-database.md)
