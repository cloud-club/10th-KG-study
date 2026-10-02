---
title: LLM 트리플 추출 — 출력은 정답이 아니라 후보다
type: concept
tags: [concept, methodology]
status: maintained
created: 2026-10-02
updated: 2026-10-02
members: [dldusgh318, heebindev, e0ng, do-dop, kdyann, Yeongeunn, yujeong430]
weeks: [5]
---

> 문장은 표현이 다양해 규칙만으로 트리플을 뽑기 어렵고(heebindev), 그래서 LLM을 쓰지만 LLM이 뽑았다고 사실은 아니다. 형식은 JSON Schema로 강제하고, 내용은 **원문 evidence 완전일치**로 검증하고, ID는 코드가 정규화하고, 탈락한 것도 저장한다. 5주차 세 멤버의 실측: 20청크 표본에서 형식·근거 검증 통과율 99.38%(dldusgh318), 그러나 같은 접근에서 **의미 정확도는 8건 중 3건 오류**(heebindev), LLM에 맡기는 면적을 Topic 하나로 줄이면 오류 면적 자체가 준다(e0ng). "LLM은 구축 비용을 낮췄지만 정규화와 신원해소 문제까지 없애주지는 않았다. 오히려 대량 생성이 가능하기 때문에 잘못된 기준을 두면 문제도 대량 생성된다" (dldusgh318).

## 설계 원칙 (dldusgh318, heebindev, e0ng)

- **Closed-schema Relation Extraction**: 미리 허용한 개체·관계 안에서만 뽑는다 → [[폐쇄-스키마-설계]]. 프롬프트로 "다섯 개 중 하나만"이라고 **부탁**하는 것과 JSON Schema `enum`으로 **강제**하는 것은 다르다. Structured Outputs는 JSON mode가 아니라 정의한 스키마를 따르게 하는 기능이지만 **형식만 보장하고 사실성은 보장하지 않는다.** 두 문제를 분리: 구조 → Schema, 내용 → Evidence + 후처리.
- **빈 배열 게이트**: "추출할 사실이 없다"도 정상 답이다. 회의록·요구사항 청크에 추출을 강요하면 없는 관계를 만든다. `{"triples": []}`를 허용하고 few-shot에 **추출할 것이 없는 예시**를 반드시 넣는다.
- **Evidence는 LLM이 요약한 문장이 아니라 입력 청크에 실제로 존재하는 원문 구간**이어야 한다. 그래야 `evidence not in chunk_text → reject`가 성립한다. 근거는 3주차 A01의 citation 실패(답은 맞았지만 인용이 원문과 불일치) → [[RAG-실패-유형]]. 한 세트는 **Triple + Evidence + Source Chunk**. e0ng은 트리플 단위가 아니라 **필드(값) 단위**로 evidence를 붙이고 원문 위치까지 저장 가능하게 했다.
- **Entity ID는 LLM에 맡기지 않는다.** 모델이 `Redis`/`redis`/`tech_redis`를 섞으면 같은 기술이 세 노드가 된다. LLM은 사람이 읽는 개체명만, 내부 ID는 코드가 규칙으로 재생성 → [[엔티티-신원해소]].
- **LLM 출력은 후보다.** Chunk → LLM → Validation(Schema / Predicate / Evidence / Status / Required field / Entity ID 6항목) → 통과한 것만 저장. 역할 분담: LLM은 무슨 개체·관계가 명시됐는지 판단, 코드는 형식·evidence·ID·중복·저장. "추출과 검증은 별개 단계가 아니라 하나의 파이프라인."
- **탈락한 것도 저장한다.** "트리플 412개를 만들었다"보다 "어떤 오류가 얼마나 났는지"가 결과다. `evidence_not_found = 환각`이라 단정하지 말고 "검증을 통과하지 못한 비율"로 기록하고 실제 환각률은 샘플 눈 검사로 따로 센다.
- Few-shot은 성공 예시보다 **경계 사례**: "실제 적용했다" → implemented / "검토했다" → proposed / "쓰지 않기로 했다" → not_implemented / "고려할 수도 있다" → 추출 X / "다음 회의 일정" → `[]`. e0ng은 "문서에 범위가 없으면 `null`, 진행 상태를 추측하지 않고 `null`, 여러 주제는 분리"를 예시 하나로 가르쳤다.
- **전체를 바로 돌리지 않는다.** 20~50개 청크를 눈으로 먼저 본다(누락 / 허위 생성 / 상태 구분 / evidence 원문성 / 빈 배열 / 개체 일관성). heebindev의 `--dry-run`은 API를 호출하지 않아 비용 0.

## 추출 과제의 분해와 평가 (Yeongeunn, yujeong430)

- 한 문장에 세 작업이 있다: **NER**(`주문서비스[Service]`) / **개체 연결**(→ `service:order`) / **관계 추출**(`service:order –calls→ service:shipping`). "문장에 둘 다 등장한다고 `calls` 관계가 있는 것도 아니다" (Yeongeunn 06). `중복 주문`처럼 도메인 개념까지 뽑는 과제는 전통 NER보다 넓어 타입·라벨링 기준을 직접 정해야 한다.
- 접근 계보(규칙 → CRF → 신경망 → BERT 미세조정 → 타입 입력형 LLM)는 연표가 아니다 — "CRF도 이미 기계학습이었다". LLM의 이득은 새 타입(`Decision` = "팀이 채택하기로 명시한 설계 선택")을 재학습 없이 시험하는 것, 위험은 **제안을 확정으로 바꾸고 원문에 없는 대상을 만드는 것** — "'호출하지 않는다'를 긍정 `calls`로 저장하면 구간 인식이 정확해도 그래프는 틀린다".
- **평가**: 엄격 일치 = 시작·끝 위치와 타입 모두. "배송서비스팀" vs "배송서비스"는 경계 오류. micro vs macro — 희소 타입이 평균에 묻힌다. **gold-pair RE와 end-to-end 구분**: 정답 개체쌍을 준 실험에서 관계를 잘 맞혀도 파이프라인이 개체를 놓치면 최종 관계는 사라진다. 참고 평가셋 CoNLL-2003, KLUE-NER(entity·character-level macro F1), KLUE-RE(`no_relation` 제외 micro F1·AUPRC) — 멤버 실측 0건.
- 스키마 강제의 5층 (yujeong430): 추출 스키마 / JSON Schema / RDFS / SHACL / 근거 확인. few-shot에 넣을 부정 유형: 부정문·단순 언급·수정·불분명 지시. Yeongeunn의 3층 검증: ① 형식(파싱·필수 필드·허용 목록·타입) ② 근거(인용 구간이 청크에 실제 존재, 오프셋 기준) ③ 의미(호출 방향, 정책 조건, 부정·제안·과거 설계 여부). 두 문서를 연결해 만든 관계는 한 문장 안의 관계와 구분하고 근거 둘 다 보관.
- kdyann의 2단계 검토: 코드가 `원문[start:end] == evidence`와 리터럴 값의 근거 포함을 검사 → 그래도 "그 문구가 내 Project의 기능을 말하는지, 다른 회사 소식 소개인지는 판단하지 못한다". 실제로 뉴스 요약을 자기 Project/Feature로 잘못 분류한 후보가 나와 의미 검토에서 제외했다.

## 멤버들이 확인한 것

| 멤버 | 모델 | 강제 수단 | 범위 | 결과 |
|---|---|---|---|---|
| dldusgh318 | OpenAI 구조화 출력 (문서에 모델명 미기재) | enum + 빈 배열 게이트 + evidence 완전일치 + ID 정규화 + 재시도·재개 | 선별 **20청크** (전체 1,562는 의도적으로 보류) | 청크 18 성공 / 2 오류(10.00%), 후보 161 → 통과 160 (**99.38%**), `evidence_not_found` **0**. "0.00%는 20개 표본에서 없었다는 뜻일 뿐 전체 환각률이 0이라는 뜻이 아니다" |
| heebindev | `gpt-5-mini`, reasoning `minimal`, 출력 4,000토큰 | JSON Schema(type 5값, predicate 8값) + evidence 포함 필터 | `--contains "SJF" --limit 5` → 실제 3청크 | 엔티티 38, 관계 8, 근거 8. **사람이 의미를 검수: 8건 중 3건 오류** → [[폐쇄-스키마-설계]] |
| e0ng (PR #36 미머지) | `gpt-4.1-mini`, **Topic 추출에만** | 폴더 경로 + `Status:`/`type:` 필드로 **결정적 추출**, LLM은 Topic만 | 3~4주차 적재 청크 (건수 미기재) | 엔티티 246, 엣지 304, 근거 237, 자동 테스트 12 통과. 단 Topic 포함 전체 실행은 미완이라 수치에 단서 필요 |
| kdyann | OpenAI (W3 모듈 재사용, 모델명 README 미기재) | JSON Schema + 근거 스팬 **문자 오프셋** + 로컬 검증 + 의미 검토 | Instagram 캡션 39문서 | 채택 사실 38건 → RDF 트리플 589. "38개 사실과 589개 트리플은 같은 단위가 아니다" |
| Yeongeunn | `gemini-3.1-flash-lite` | 허용 목록 + 3층 검증 + 긍정·부정 few-shot | 회원탈퇴 관련 청크 4개(1차) / 5개(2차) | 후보 **7 → 5** (입력·예시가 함께 바뀌어 A/B가 아님 — "후보가 줄었다고 정확도가 높아진 것은 아니다"). 1차는 **API 경로만 보고 제공 서비스를 단정**, 2차는 문맥을 보강하자 **정책 관계가 누락** — 트레이드오프. 검토 후 엔티티 15·관계 20·근거 29. "LLM이 20개를 자동으로 정확히 추출했다고 주장하지 않는다" |
| do-dop | — | — | 추출 미시작 | LLM 호출 모듈·프롬프트를 추출에 재사용 예정 |

- **다섯 명 모두 전체 코퍼스 추출을 완주하지 않았다**(kdyann은 39문서 전체를 돌렸지만 자동화 미완). dldusgh318: "20개 표본은 최종 결과가 아니라 파이프라인을 검증하기 위한 PoC. 잘못된 추출 규칙 × 1,562개 청크 = 훨씬 큰 정리 비용. 다음 작업자는 전체 추출부터 시작하면 안 된다."
- 검색 임베딩은 개인 데이터를 다루는 멤버 전원이 로컬이었는데([[임베딩-모델-선택]]), **추출은 다섯 명 모두 외부 API**(OpenAI 넷, Gemini 하나)를 썼다. e0ng·dldusgh318의 데이터는 개인 활동 기록이다 → [[개인-데이터-가명화와-공개-범위]] 열린 질문.

## 함정 · 주의 (dldusgh318 실측)

- **JSON 응답 절단 10%**: 청크 2개에서 `Unterminated string`. 인증·HTTP 오류가 아니라 모델 응답이 8,782자·12,383자 지점에서 끊긴 잘못된 JSON. 출력 토큰 한도가 유력. 재시도 2회 소진. 처방: API 응답의 **종료 사유를 함께 저장**하고 청크당 출력량·최대 출력 토큰을 조정. heebindev도 `incomplete` + `max_output_tokens`면 8,000으로 늘리라고 적었다.
- **ID 공백 1건**: LLM이 subject IRI 안에 공백 하나를 넣어 `dangling_subject`로 탈락했고, 적재 코드가 `partOf`와 `usesTechnology`를 모두 가진 사용례만 넣으므로 같은 사용례의 통과 트리플 3건도 함께 버려졌다(JSONL 160 → DB 157). 재실행 시 `ON CONFLICT DO NOTHING`으로 추가 0행 — **최초의 3건 감소와 재실행 중복 방지는 다른 현상.** IRI 규칙("`a-z`와 하이픈만")을 명세에 적어도 LLM은 위반한다.
- **같은 사실의 과잉 생성**: 같은 사실이 여러 청크에서 다른 표현으로 등장하는데 LLM은 청크를 독립 처리한다 → `TechnologyUse` 45개가 32개 `(project, technology)` 쌍에 매핑, 한 쌍이 6개 노드. `COUNT(*)`로 세면 답이 부풀려지므로 `COUNT(DISTINCT project)` → [[엔티티-신원해소]].
- **NULL은 실패가 아니다**: `TechnologyUse` 45 중 purpose 결측 19, status 결측 16. "명시되지 않으면 뽑지 않는다"가 의도대로 작동한 결과. "LLM이 임의로 `캐싱`을 만드는 것보다 모른다는 상태를 남기는 것이 낫다." 열린 세계 가정이 실제 데이터의 NULL로 나타났다 → [[온톨로지와-추론]]. 단 JSONL 술어 행 수를 DB 노드 수에서 빼서 결측을 계산하면 안 된다(관계 행 중복).
- **구조화 출력을 써도 데이터 품질은 자동 보장되지 않았다** — 절단 2 + ID 공백 1 + 과잉 생성 + 결측. 그래서 LLM 출력 → 스키마 검증 → evidence 검증 → ID 정규화 → 불완전 사용례 검사 → 적재.
- 남겨야 할 지표 6종: 추출 수 / 빈 배열 비율 / 검증 통과율 / evidence 불일치율 / 술어별 추출 수 / 대표 실패 사례. 가상 예시 수치(통과 78.4% 등)와 실측(99.38%)이 같은 멤버의 노트에 나란히 있으니 인용할 때 섞지 않는다.
- 스키마 진화: 새 술어를 추가해도 기존 데이터에 자동으로 생기지 않는다. v0로 뽑은 300개에 `hasStatus`가 없을 때 "implemented 전부"는 그 300개를 조용히 빠뜨린다. 추출 시점의 `extraction_run`(`v0-4predicates` / `v1-5predicates`)을 함께 기록해 "정보가 없었던 것"과 "도입 전에 추출한 것"을 구분 → [[데이터-수집과-출처-추적]].

## 열린 질문

- 의미 정확도를 체계적으로 재는 방법. heebindev의 8건 눈 검수가 전부다. 샘플 기반 환각률 측정(dldusgh318 계획)은 아직 없다.
- 결정적 추출(e0ng)은 폴더 구조가 이미 온톨로지를 반영한 데이터에서만 가능하다. 카카오톡·회의록처럼 구조가 없는 소재에서는?

## 관련

- [[폐쇄-스키마-설계]] · [[엔티티-신원해소]] · [[그래프-적재-Postgres와-Neo4j]] · [[RDF와-트리플]] · [[RAG-루프와-근거-인용]] · [[RAG-실패-유형]] · [[데이터-수집과-출처-추적]] · [[지식그래프와-온톨로지]]

## 출처

- dldusgh318 · W5-2 LLM 정보 추출 — [members/dldusgh318/notes/week5/02-llm-information-extract.md](../../members/dldusgh318/notes/week5/02-llm-information-extract.md); 인수인계 (§3 추출 품질, §4 문제) — [labs/01-three-generations/WEEK5_HANDOFF.md](../../members/dldusgh318/labs/01-three-generations/WEEK5_HANDOFF.md); 결과 보고 — [WEEK5_result.md](../../members/dldusgh318/labs/01-three-generations/WEEK5_result.md); 실행 절차 (§통계 해석 규칙) — [README.md](../../members/dldusgh318/labs/01-three-generations/README.md); W5-3 RDF 형식 (§스키마 진화) — [notes/week5/03-rdf-format.md](../../members/dldusgh318/notes/week5/03-rdf-format.md)
- heebindev · 문서에서 지식 그래프 만들기 — [members/heebindev/labs/03-triple-extraction-kg/README.md](../../members/heebindev/labs/03-triple-extraction-kg/README.md); 데이터 파이프라인 노트 (§4 보조장치) — [notes/05-rdf-owl-data-pipeline.md](../../members/heebindev/notes/05-rdf-owl-data-pipeline.md)
- e0ng · LLM 정보 추출 — [members/e0ng/notes/05-2-llm-information-extraction.md](../../members/e0ng/notes/05-2-llm-information-extraction.md) (PR #34 미머지); 지식그래프 적재 — [labs/05-graph-store/README.md](../../members/e0ng/labs/05-graph-store/README.md) (PR #36 미머지)
- kdyann · RDF·OWL 데이터 파이프라인, 캡션 지식 그래프 — [members/kdyann/notes/05-rdf-owl-data-pipeline.md](../../members/kdyann/notes/05-rdf-owl-data-pipeline.md), [labs/05-content-graph/README.md](../../members/kdyann/labs/05-content-graph/README.md)
- Yeongeunn · 엔티티 추출 모델, 미니 온톨로지와 트리플 추출 (§5–8), 트리플 추출 실습 — [members/Yeongeunn/notes/06-entity-extraction-models.md](../../members/Yeongeunn/notes/06-entity-extraction-models.md), [notes/10-week5-triple-pipeline.md](../../members/Yeongeunn/notes/10-week5-triple-pipeline.md), [labs/05-triple-extraction/README.md](../../members/Yeongeunn/labs/05-triple-extraction/README.md)
- yujeong430 · RDF 데이터 파이프라인 개념 (§2–7) — [members/yujeong430/notes/11-rdf-data-pipeline-concepts.md](../../members/yujeong430/notes/11-rdf-data-pipeline-concepts.md) (PR #19 미머지)
- 외부: KLUE https://arxiv.org/abs/2105.09680 · CoNLL-2003 https://aclanthology.org/W03-0419/ · Gemini structured output https://ai.google.dev/gemini-api/docs/structured-output (Yeongeunn)
- 외부: OpenAI Structured Outputs https://developers.openai.com/api/docs/guides/structured-outputs (heebindev)
