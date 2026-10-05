---
title: RAG 평가 지표 — 골든셋, Recall@k, 그리고 누가 정답을 정했나
type: concept
tags: [concept, comparison]
status: maintained
created: 2026-09-16
updated: 2026-10-02
members: [sese2204, dldusgh318, lys0611, e0ng, ur2e, jjinthung, kdyann, heebindev, sunghyun, Yeongeunn, yujeong430, do-dop, sdunge]
weeks: [2, 3, 5]
---

> 모든 RAG 기법의 도입 여부는 측정으로 결정한다. 검색 단계는 골든셋 IR 지표(recall@k, MRR, NDCG)로, 생성 단계는 근거 충실도·정답 정확도로, 5주차부터는 **추출 단계**(트리플 Precision/Recall)까지 **따로** 잰다. 2026-10-02 기준 정답 라벨을 만들고 Recall@k를 계산한 멤버는 아홉 명(dldusgh318, lys0611, e0ng, heebindev, kdyann, sunghyun, Yeongeunn, yujeong430, do-dop)이지만 **라벨을 누가 붙였는지가 다섯 갈래**(사람 단독 pooling / 검색 전 수동 지정 / LLM 후보 + 사람 확정 / LLM-as-a-Judge / AI 보조 초안)로 벌어져 멤버 간 수치를 나란히 읽을 수 없다. 평가셋의 **엄격도**가 수치를 지배하고(e0ng: 정답 수를 늘리자 r@1 0.775 → 0.357), 비공개 데이터는 평가셋을 공유할 수 없다. 평가의 층위·심판·편향은 [[챗봇-평가-층위와-심판]], 도구는 [[RAGAS]].

## 지표

| 층 | 지표 | 정의 | 누가 씀 |
|---|---|---|---|
| 검색 | Recall@k | 정답 청크(또는 evidence group) 중 top-k에 든 비율. **분모는 검색 결과 수가 아니라 정답 수** — 분모를 5로 잡으면 Precision@5다 (sunghyun). 같은 질문에서 R@1 ≤ R@3 ≤ R@5 | dldusgh318, lys0611, e0ng, heebindev, kdyann, sunghyun, Yeongeunn, yujeong430, do-dop |
| 검색 | Hit@k | 정답이 top-k 안에 있으면 1. **근거가 여러 개 필요한 질문에서 1개만 찾아도 1점이라 과대평가** (do-dop) | jjinthung, ur2e, do-dop |
| 검색 | MRR | 첫 정답 순위의 역수 평균. 여러 필수 근거를 모두 찾았는지는 설명 못 함 (Yeongeunn) | lys0611, ur2e |
| 검색 | Precision@k | top-k 중 관련 결과 비율 | e0ng(02) |
| 검색 | **nDCG@k** | 좋은 근거일수록 상위에 있을 때 높은 점수. LLM judge 0~3 등급 필요 | **e0ng(03) 실측** — recall은 벡터가 높은데 nDCG는 하이브리드가 최고 |
| 검색 | AllEvidence@k | 다중 홉의 evidence group **전부**가 top-k에 있는가 | lys0611 |
| 검색 | 지정 근거 Recall | "모든 관련 문서"가 아니라 사람이 지정한 근거의 회수율 — 겸손한 이름 | Yeongeunn |
| 생성 | faithfulness, answer relevancy | 근거 충실도. **RAGAS 카탈로그의 절반 이상은 `reference`(정답 문장)나 `reference_context_ids`가 필요하다** — "정답 레이블 없이"는 논문 원형 3지표에만 해당 (sese2204 자기 보정) | sese2204 정리 |
| 생성 | FactualCorrectness, AnswerCorrectness, NoiseSensitivity | 정답 정확도·틀린 claim 비율 | sese2204 정리 → [[RAGAS]] |
| 생성 | 인용 precision / recall, 거절 성공률 | ALCE 방식. 답 없는 질문을 지어내지 않은 비율 | lys0611 |
| 생성 | 수작업 채점 | 정답성 / 근거성 / 인용 지지 / 보류·충돌 표시를 따로 | Yeongeunn, sunghyun, heebindev |
| **추출** | 트리플 Precision / Recall | 사람이 확인한 소규모 평가셋에서 ID·술어·방향·조건·근거까지. 엄격 일치 = 시작·끝 위치와 타입 모두 (Yeongeunn 06). gold-pair RE와 end-to-end 구분 | Yeongeunn 계획, heebindev 눈 검수(8건 중 3건 오류) → [[LLM-트리플-추출]] |
| 시스템 | p50/p99 지연, 토큰 비용, 호출 수 | 단회 관측으로 우열을 주장하지 않는다 (Yeongeunn) | lys0611, e0ng, sunghyun |

- 골든셋 IR 지표와 RAGAS는 대체재가 아니라 다른 층을 재는 도구다. 기법을 하나씩 **누적**해 붙이고 매번 **같은 골든셋**으로 잰다 (sese2204 로드맵). [[리랭커]] 도입 판단에는 recall@100과 recall@5를 함께, RRF 효과 판단에는 recall과 nDCG를 함께 (e0ng).
- 실패를 검색 실패 vs 생성 실패로 분해한다 → [[RAG-실패-유형]]. 거기에 "검색 성공 + 융합 탈락"(do-dop)과 "연결 실패"(세 멤버)가 더해졌다.
- Retrieval 단독 평가 구조 = **corpus / queries / qrels** (BEIR 유래, do-dop): `chunks.jsonl` = corpus, 질문 파일 = queries, `relevant_chunk_ids` = qrels → [[BEIR]].

## 정답을 먼저 정해야 Recall을 잴 수 있다

- 2주차의 질문 비교표는 사람이 top-1만 보고 판정한 정성 평가라 Recall@k로 읽을 수 없었다 (lys0611, e0ng). "Recall@k는 검색 결과만 보고 자동 계산할 수 없다. 사람이 먼저 정한 관련성 판단이 필요하다" (yujeong430). "정답 근거는 특정 단어가 들어 있는 청크가 아니라 질문에 대한 답을 실제로 뒷받침하는 본문을 읽고 정한 청크다. 단어 검색은 후보를 찾는 준비 단계일 뿐" (sunghyun).
- **라벨링은 TREC pooling**: 세 방식의 후보 풀에서 사람이 판정한다. 풀에 없던 정답은 라벨되지 않아 절대 수치는 낙관적이지만 상대 비교에는 공평하다 (lys0611). BEIR 자체도 기존 검색기 top-100 풀에서 판정하므로 그 검색기가 못 올린 문서는 평가 기회가 없다 — TREC-COVID에서 빠진 문서를 추가 annotation하자 non-lexical 방법 점수가 올랐다 (do-dop) → [[BEIR]].
- 정답 문서가 정의되지 않는 질문("점심 메뉴 추천해 줘")은 Recall을 계산할 수 없다 → 다시 쓴다. **질문을 바꾼 기록이 세 멤버에서 반복됐다**: lys0611은 질문 절반을 다시 썼고, sunghyun은 근거를 못 찾은 질문에 "관련 자료를 억지로 정답으로 넣지 않고" 질문을 바꿨고, heebindev는 질문이 넓어 정답 청크가 많아지자 범위를 좁혔다. "라벨링에 걸린 시간이 RRF 구현의 몇 배"(lys0611).
- 관련성 단위는 물리 청크가 아니라 대체 가능한 **evidence group** (lys0611, Yeongeunn). 라벨은 `chunk_id`가 아니라 `content_hash`로 저장하고, 실행 전 gold hash가 코퍼스에 있는지 확인해 라벨이 조용히 0점이 되는 걸 막는다. Yeongeunn은 `corpus_sha256`이 다르면 빌드를 **중단**한다. 반복 전송된 공지는 모두 관련 문서로 표시한다 (yujeong430).
- **정답셋은 초기 기준이다** (sunghyun): "정답셋에 없는 유효 근거를 찾았을 수도 있다. 추가했다면 모든 방식을 같은 기준으로 다시 평가해야 한다." Yeongeunn q05가 그 사례 — 지정 근거를 놓치고 **대체 문서로 맞게 답해** 점수 0. 라벨의 대체 근거 누락은 평가셋의 실패다.
- **평가셋의 엄격도가 수치를 지배한다** (e0ng): 같은 코퍼스·같은 검색기에서 질문당 정답 1~4개(10문항)일 때 하이브리드 r@1 0.775, 질문당 정답 최대 17개(36문항)일 때 0.357. **다른 멤버의 Recall 절댓값을 비교하면 안 되는 가장 직접적인 증거.**
- **쿼리 타입 구성이 승자를 바꾼다** (e0ng): 자연어 질문만 있을 때는 벡터가 유리했고 단일·복합 키워드를 섞자 BM25와 동률. yujeong430은 6유형(정확 키워드 / 형태 변형 / 의미 바꿔 말하기 / 세부 조건 / **시점 구분** / 다중 근거)으로 나눠 유형별 R@3을 따로 냈다 — 시점 구분 7문항은 세 방식 모두 71.4로 동률이라 검색기가 아니라 데이터 표현의 문제. Yeongeunn은 5유형(정확 용어 / 다른 표현 / 조건·부정·예외 / 다중 홉 / 문서에 없는 질문). 평균만 보지 말고 유형별로 쪼갠다 (ur2e, lys0611).
- **LLM이 정답을 정하면 편향이 생긴다** (e0ng): LLM이 전체 청크에서 후보를 직접 고르면 특정 검색 방식에 유리할 수 있어 pooling으로 바꿨다. 10문항 결론을 스스로 약화시켰다. LLM-as-a-Judge의 편향·보정은 [[챗봇-평가-층위와-심판]].
- **Recall ≠ Answerability** (dldusgh318 A01, sunghyun Q6, Yeongeunn q05·q10): Gold ID를 놓쳐도 중복 기록된 다른 청크가 답을 줄 수 있고(A01, q05), 같은 절차를 설명하는 두 청크 중 하나만 찾아도 답할 수 있지만 R@1은 0.5(Q6), 반대로 근거를 다 찾고도 대상의 종류를 잘못 답할 수 있다(q10). 검색 지표는 검색기 비교용이고 실제 RAG는 최종 Context에 정보가 있는지와 LLM이 그걸로 답했는지까지 봐야 한다.
- **비교 공정 4조건** (yujeong430): 같은 질문 목록 / 같은 판정 목록 / 같은 k / 같은 청크 집합. Yeongeunn은 "검색 결과를 본 뒤 설정을 바꾸지 않고 첫 설정의 결과와 실패 사례를 남겼다"고 명시했고, **튜닝 질문과 최종 확인용 질문을 분리**하라고 처음 요구했다. 대표 질문을 검색 결과를 보고 고른 진단은 독립 평가가 아니다.
- **평가셋 설계가 측정하려는 현상을 실제로 유도하는가** (dldusgh318, do-dop, yujeong430): 멀티홉이라고 라벨한 문항이 실제로는 같은 문서 안에 답이 있어 검색 한 번으로 풀리는 경우가 세 멤버에서 나왔다. 브릿지를 질문에서 숨겨야 멀티홉 테스트가 성립한다 → [[멀티홉-질문과-Bridge-Entity]].
- 개방형 집계 질문("요즘 주목하는 기술은?")은 정답 청크 수를 미리 정할 수 없어 Hit/Recall로 채점이 안 된다 — 체크리스트나 LLM-as-judge로 (do-dop). 답 없는 질문은 분모 0이라 따로 분류한다 (Yeongeunn, yujeong430의 `answerability_challenges` 5문항은 평균에서 제외).

## 멤버별 평가셋 현황

| 멤버 | 데이터 | 질문 수·유형 | 정답 라벨 — 누가 | 지표 | 결과 |
|---|---|---|---|---|---|
| dldusgh318 | Notion 1,562청크 | R01–R10 10개 (exact-term, code-symbol, semantic, spelling, typo) + 브릿지 숨김 X01–X03 | 사람 판정 Gold Set(qrels) | Recall@5/10, Oracle 대조 | Hybrid 0.534 / 0.734 → [[하이브리드-검색과-RRF]] |
| lys0611 | 카카오톡 1,922청크 | 34문항 (exact 12 / semantic 12 / hard 10), 검색 평가 27 | 사람 pooling, evidence group, content_hash | R@1/3/5/10, AllEvidence@k, MRR@10, 인용 P/R, 거절 성공률 | RRF R@5 0.907, 생성 정확도 0.583 |
| e0ng (03) | Notion 111청크 | ① 10문항 자연어 ② **36문항** (층화 샘플링 청크 12개 × 단일 키워드/복합 키워드/자연어) | ① LLM 생성 + LLM 후보 + **사람 확정**(`reference` vs `context` 분리) ② **TREC pooling + LLM-as-a-Judge 0~3점, 2점 이상 정답** | Recall@1/3/5/10, **nDCG@1/3/5/10** | ① 하이브리드 r@1 0.775 ② r@1 0.357, n@1 0.926 |
| e0ng (02) | 채팅 9,491건 | `수강 신청` 1개 | 없음 | Precision@5 | grep 0.0 / BM25 0.6 / pgvector 1.0 |
| heebindev (02) | Notion 운영체제 454청크 | 5문항 개념 질문 | 사람이 원문 보고 청크 ID 지정 — **"최종 검토하지 않은 초안"** | Recall@5 | BM25 0.50 / 벡터 0.80 / 하이브리드 0.80 |
| kdyann (03) | Instagram 248문서 | 15문항 (내 글 9 / 참고 글 4 / 전체 2) | **검색 순위를 보기 전에** 캡션 읽고 지정 | Recall@1/3/5 | BM25 0.733 / 0.889 / 0.889, RRF 0.600 / 0.800 / 0.956 |
| sunghyun (03) | 회사 기술 문서 2,685청크 | Q1~Q6 (기능명 vs 자연어 표현 쌍, 회의록, 절차) | 원문 선독 후 chunk_id 고정, **비공개** | Recall@1/3/5/10, 정답 실제 순위 | Q1~Q4 R@5 0.625 / 0.750 / 0.750, Q5 BM25 R@10 1.00 vs RRF 0.75 |
| Yeongeunn (04) | 팀 Notion 1,369청크 | 10문항 (정확 용어 3 / 다른 표현 3 / 조건 2 / 다중 홉 2) | evidence group + corpus_sha256, **AI 보조 초안·작성자 검토 중** | 지정 근거 Recall@5, HNSW 일치율, 생성 12답변 + oracle 1 | BM25 0.60 / 벡터 0.70 / RRF 0.55 |
| yujeong430 (PR #19 미머지) | 카카오톡 공지방 814청크 | **40문항**, 6유형 + 답 가능성 5문항 별도 | 손 라벨, 반복 공지는 모두 관련 | Recall@1/3/5, 유형별 R@3 | BM25 0.5875 / 0.8875 / **0.95**, RRF 0.575 / 0.8625 / 0.8875 |
| do-dop (03) | 기업 뉴스룸·공시 69청크 | 10질문 (keyword / semantic / multi_hop) + 실패 4사례 | `relevant_chunk_ids` qrels | Hit@5, Recall@5, 6방식 | 벡터·RRF R@5 100%, BM25 96.7%, 정규화 96.7% |
| ur2e (PR #11 미머지) | 합성 옵시디언 vault | 19문항 9유형, `expected_primary`·`answer_points` | vault 상대 경로 | Hit@3, MRR | BM25 0.84/0.82 ~ pgvector 0.68/0.53 |
| jjinthung | 카카오톡 753청크 | 정답 40개 | 있음(방식 불명) | Hit@1, Hit@5 | grep 0 / BM25 45% / 벡터 2.5% |
| sdunge | 판례 2,443청크 | 동의어 3개 | 없음 | 히트 건수 | grep 0줄 vs BM25 9청크 |
| do-dop (02), kdyann (01), heebindev (01) | 2주차 실습 | 3~13개 | 없음 | 히트 건수 | 정성 → [[검색의-세-세대]] |

- 데이터도 지표도 라벨러도 제각각이라 멤버 간 수치를 직접 비교할 수 없다. 비교할 수 있는 것은 **같은 멤버 안에서의 상대 변화**뿐이다.
- **지연 측정** (질문당 p50): lys0611 BM25 5.5ms · 임베딩 26.4ms · pgvector 8.1ms · RRF 0.1ms · 합계 40.1ms. e0ng(02) BM25 116.8ms · pgvector 204.4ms(임베딩 32.4). 벡터 검색 지연은 질의 임베딩이 지배한다. sunghyun의 exact 65ms vs HNSW 6.4ms는 검색 지연이다 → [[HNSW와-pgvector-인덱스]]. Yeongeunn: "워밍업·반복·동시 부하 없는 단회 관측으로 속도 우열을 주장하지 않는다."

## 열린 질문

- **공용 골든셋**: 데이터가 멤버마다 다르고 넷(sunghyun·lys0611·yujeong430·Yeongeunn)은 비공개라 질문·정답을 공유할 수 없다. 공용은 질문 **유형**(exact / variant / semantic / constraint / temporal / multi-evidence / unanswerable)과 라벨링 **절차**(pooling, evidence group, content_hash, 검색 전 지정, 개발/테스트 분리) 수준에서만 가능하다. sese2204가 [[RAGAS]] 합성기 기준 **200개 배분안**(single-hop specific 40% / multi-hop specific 20% / multi-hop abstract 10% / unanswerable 15% / multi-turn 15%)을 냈다 → [[챗봇-평가-층위와-심판]].
- 정답 라벨을 두 사람이 따로 붙였을 때의 일치도 (lys0611 TODO). 기준선: 사람끼리도 약 80%, LLM judge와 사람 일치 80%+ (sese2204 정리). RAGAS 문서의 심판 정렬은 160개 라벨에서 75.6% → 86.9%.
- 인용 precision/recall을 NLI 모델로 근사 (lys0611 TODO) — 후보는 RAGAS `FaithfulnesswithHHEM`(Vectara HHEM-2.1, 로컬) 또는 RAGChecker의 claim 단위 entailment.
- **후보 수가 RRF 손익을 가르는가** — 어느 멤버도 후보 수를 변수로 실험하지 않았다 → [[하이브리드-검색과-RRF]].
- 추출 단계의 의미 정확도를 체계적으로 재는 방법 → [[LLM-트리플-추출]].

## 관련

- [[RAG-실패-유형]] · [[하이브리드-검색과-RRF]] · [[리랭커]] · [[임베딩-모델-선택]] · [[청킹-전략]] · [[검색의-세-세대]] · [[RAG-루프와-근거-인용]] · [[챗봇-평가-층위와-심판]] · [[RAGAS]] · [[BEIR]] · [[멀티홉-질문과-Bridge-Entity]] · [[LLM-트리플-추출]] · [[개인-데이터-가명화와-공개-범위]]

## 출처

- sese2204 · RAG 평가와 실습 로드맵 (2026-09-16 보정 포함) — [members/sese2204/notes/07-rag-evaluation.md](../../members/sese2204/notes/07-rag-evaluation.md); 챗봇 평가, RAGAS — [09-chatbot-evaluation.md](../../members/sese2204/notes/09-chatbot-evaluation.md), [10-ragas.md](../../members/sese2204/notes/10-ragas.md)
- dldusgh318 · 하이브리드 검색 (§Recall@k), 실습 §2, RAG Agent §11–12 — [members/dldusgh318/notes/week3/04-hybridSearch-rrf.md](../../members/dldusgh318/notes/week3/04-hybridSearch-rrf.md), [labs/01-three-generations/WEEK3_hybrid_search_rrf.md](../../members/dldusgh318/labs/01-three-generations/WEEK3_hybrid_search_rrf.md), [WEEK3_rag_agent.md](../../members/dldusgh318/labs/01-three-generations/WEEK3_rag_agent.md)
- lys0611 · 하이브리드 검색과 RRF (§정답을 먼저 정해야), 실습 결과 — [members/lys0611/notes/04-hybrid-search-rrf-recall.md](../../members/lys0611/notes/04-hybrid-search-rrf-recall.md), [labs/02-hybrid-rag-agent/README.md](../../members/lys0611/labs/02-hybrid-rag-agent/README.md), [results/retrieval-summary.md](../../members/lys0611/labs/02-hybrid-rag-agent/results/retrieval-summary.md)
- e0ng · 개인 데이터 검색 에이전트 (10·36문항, 골든셋 구축법) — [members/e0ng/labs/03-personal-data-agent/README.md](../../members/e0ng/labs/03-personal-data-agent/README.md); RRF와 RAG 루프, 2주차 실습 — [notes/03-rrf.md](../../members/e0ng/notes/03-rrf.md), [labs/02-search-generations/README.md](../../members/e0ng/labs/02-search-generations/README.md)
- heebindev · 하이브리드 검색과 개인 데이터 에이전트 (§골드셋) — [members/heebindev/labs/02-hybrid-search-rag/README.md](../../members/heebindev/labs/02-hybrid-search-rag/README.md)
- kdyann · 하이브리드 검색과 RAG 실습 (§평가) — [members/kdyann/labs/03-hybrid-search/README.md](../../members/kdyann/labs/03-hybrid-search/README.md)
- sunghyun · 3주차 하이브리드 검색, RAG와 Recall 평가 (§Recall 정의, §정답셋) — [members/sunghyun/notes/03-hybrid-rag-and-evaluation.md](../../members/sunghyun/notes/03-hybrid-rag-and-evaluation.md); 실습 (§재현 불가) — [labs/03-hybrid-rag/README.md](../../members/sunghyun/labs/03-hybrid-rag/README.md)
- Yeongeunn · 평가 계획 노트, 평가 실습, 엔티티 추출 모델 (§평가), 임베딩 모델 (§지표) — [members/Yeongeunn/notes/04-evaluation-plan.md](../../members/Yeongeunn/notes/04-evaluation-plan.md), [labs/04-hybrid-evaluation/README.md](../../members/Yeongeunn/labs/04-hybrid-evaluation/README.md), [notes/06-entity-extraction-models.md](../../members/Yeongeunn/notes/06-entity-extraction-models.md), [notes/07-embedding-models.md](../../members/Yeongeunn/notes/07-embedding-models.md)
- yujeong430 · Recall@k 노트, 평가 결과 — [members/yujeong430/notes/07-recall-at-k.md](../../members/yujeong430/notes/07-recall-at-k.md), [labs/01-kakaotalk-search/data/evaluation/README.md](../../members/yujeong430/labs/01-kakaotalk-search/data/evaluation/README.md) (PR #19 미머지)
- do-dop · RAG 루프 (§corpus/queries/qrels, §Hit@k 한계), BEIR, 못 답한 질문 (§집계 채점) — [members/do-dop/notes/03-rag-loop.md](../../members/do-dop/notes/03-rag-loop.md), [03-beir-benchmark.md](../../members/do-dop/notes/03-beir-benchmark.md), [labs/03-company-analysis-kg/failed_questions.md](../../members/do-dop/labs/03-company-analysis-kg/failed_questions.md)
- ur2e · 검색 방식 비교 실험, 데이터셋 설계 — [members/ur2e/notes/01-search-methods-comparison.md](../../members/ur2e/notes/01-search-methods-comparison.md), [labs/01-worklog-search/dataset/README.md](../../members/ur2e/labs/01-worklog-search/dataset/README.md) (PR #11 미머지)
- jjinthung · 결과 — [members/jjinthung/notes/01_results.md](../../members/jjinthung/notes/01_results.md); sdunge · 판례 검색 — [members/sdunge/labs/readme.md](../../members/sdunge/labs/readme.md)
- 외부: Elasticsearch Ranking evaluation API https://www.elastic.co/docs/reference/elasticsearch/rest-apis/search-rank-eval · Judgment lists (Elastic Search Labs) https://www.elastic.co/search-labs/blog/judgment-lists-search-query-relevance-elasticsearch · Gao et al., ALCE (2023) https://aclanthology.org/2023.emnlp-main.398/ · BEIR metrics https://github.com/beir-cellar/beir/wiki/Metrics-available · Pinecone, Offline evaluation https://www.pinecone.io/learn/offline-evaluation/ · dmoritle, 검색 평가용 Ground Truth 구축 https://dmoritle.tistory.com/199 (e0ng) · IR-book, Evaluation of unranked retrieval sets https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-unranked-retrieval-sets-1.html (Yeongeunn)
