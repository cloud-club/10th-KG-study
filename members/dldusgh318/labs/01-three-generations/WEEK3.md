# W3 — Hybrid Search와 Personal Data Agent

W2에서 확인한 BM25와 Vector의 서로 다른 실패 패턴을 RRF로 결합하고, 검색 결과를 근거가 검증되는 RAG에 연결한다. 마지막에는 Normal Context와 사람이 지정한 Oracle Context를 비교해 retrieval과 generation 실패를 구분한다.

```text
BM25 top-50 ─┐
              ├─ RRF top-k ─ Context ─ LLM ─ citation 검증
Vector top-50 ┘                 │
                                └─ Oracle chunk로 교체해 실패 원인 비교
```

## 1. Hybrid Search

```bash
./.venv/bin/python src/hybrid_search.py "캐시 전략"
```

BM25와 cosine similarity를 서로 더하지 않는다. 각 검색기의 순위에 대해서만 `1 / (60 + rank)`를 더하며, 한 검색기에만 등장한 청크도 유지한다. RRF 점수는 relevance confidence로 사용하지 않는다.

## 2. 질문 검토와 골드셋

기존 W2 질문은 검색 방식의 특성을 관찰하기 위한 probe였다. Recall 평가 질문은 정답 청크의 범위를 일관되게 판정할 수 있어야 하므로 먼저 검토한다.

### 합의한 질문 구성

검색 평가 후보는 정확한 용어·심볼·프로젝트 3개, 의미 검색 3개, 표기 비교 2쌍으로 총 10개다. W2 질문과 구분하기 위해 R01~R10을 사용한다. 원문에서 질문 대상 기록의 존재를 확인하여 `ready`로 변경했다. 이는 후보 풀 생성 가능 상태이며, 정답 청크나 relevance를 확정했다는 뜻은 아니다.

R07/R08은 Elasticsearch 표기 비교, R09/R10은 Kubernetes 오타 비교다. 각 쌍은 양쪽 질문의 후보를 합친 하나의 판정 묶음을 공유하므로 한 번만 라벨링한다. 10개 질문은 8개 정보 요구를 포함한다. 공유 골드셋의 Recall 및 쌍별 차이 계산은 라벨링 후 5번 단계에서 연결한다.

원문을 확인하면서 정보 요구와 포함·제외 기준을 확정한다. 상위 검색 결과에 답이 없다는 이유만으로 제외하지 않는다. 학습 문서도 유효한 근거다. 기존 면접 피드백 질문은 실제 기록 존재 여부를 확인할 수 있는 교체 후보로 남긴다.

### 골드셋 평가표 설계

| 항목 | 기록할 내용 |
|---|---|
| 질문·유형 | 검색어, 평가 목적, 표기 비교 그룹 |
| 정보 요구 | 무엇을 찾으면 성공인지 한 문장으로 정의 |
| 포함·제외 기준 | 직접적인 설명과 단순 언급을 구분하는 규칙 |
| 청크별 판정 | 관련 / 무관 / 판단 보류와 판정 이유 |
| 정답 청크 집합 | 사용자가 관련으로 확정한 ID 목록 |
| 검토 상태 | 미완료 / 완료 |

세 검색 방식의 top-10 합집합을 판정하고 후보 밖 정답도 추가한다. 측정값은 라벨링한 정답 집합 기준 Recall이며 전체 코퍼스의 정답을 모두 찾았다고 가정하지 않는다. 반복되는 내용에도 동일한 포함 기준을 적용하고 중복 청크가 분모에 미치는 영향을 기록한다.

qrels v2는 `queries`에서 질문과 `judgment_group`을 연결하고, `judgment_groups`에서 청크별 판정을 한 번만 저장한다. 각 묶음에는 `status`, `labeling_rule`, `judgments`가 있다. `judgments`의 `label`은 모두 `null`로 시작하며 후보 ID 목록은 판정 완료를 의미하지 않는다.

RAG 실험은 별도로 single-hop 2개, 2-hop 2개, aggregation 1개, 가능하면 3-hop 1개를 구성한다. 실제 정답과 필요한 청크를 확인한 뒤 질문을 확정한다.

```bash
./.venv/bin/python src/evaluate.py review
```

[질문 정의](queries/questions.json)에서 `revise` 질문을 수정하거나 `exclude`로 결정한다. 평가할 질문은 `ready`로 바꾼다. `revise`가 남아 있으면 후보 풀 생성은 중단된다.

검토가 끝나면 세 검색 방식의 top-10 합집합을 만든다.

```bash
./.venv/bin/python src/evaluate.py pool
```

개인 원문과 청크 ID가 포함된 다음 파일은 `data/` 아래에 생성되므로 gitignore 대상이다.

- `data/week3/candidate_pool.md`: 사람이 읽는 라벨링 화면
- `data/week3/candidate_pool.json`: 질문별 후보와 원래 검색 top-50 ID·순위·점수, 합쳐진 판정 묶음
- `data/week3/qrels.json`: 골드셋 템플릿

후보 목록에는 `R01 C001`처럼 묶음과 후보 번호가 있다. 이 번호로 대화에서 판정을 전달하거나 qrels의 해당 항목을 직접 편집할 수 있다. 각 청크에는 제목·경로·헤딩·전체 text와 질문별 검색 순위가 표시된다. 원문은 코드 블록으로 보여주므로 포함된 링크·이미지·HTML이 실행되지 않는다. 순위의 `—`는 그 질문과 검색기의 top-10에 없다는 뜻이다.

qrels에서 묶음마다 다음 원칙을 적용한다.

- `label`은 `null`(미판정), `relevant`(관련), `irrelevant`(무관), `unsure`(판단 보류) 중 하나로 기록하고 `note`에 이유를 적는다.
- 보류·미판정이 남아 있는 동안 `status`는 `unlabeled`로 유지한다. 모든 판정을 검토한 뒤 `complete`로 바꾼다.
- 후보 풀 밖에서 찾은 정답도 추가한다. pooled judging은 검색기 셋이 모두 놓친 정답을 보여주지 못하기 때문이다.
- 단순 단어 포함이 아니라 질문의 `labeling_rule`을 만족하는지를 판정한다.
- 후보 중 관련 청크가 없으면 후보 밖 원문도 확인한다. 골드가 비어 있으면 Recall은 정의하지 않으며, 검색 실패만으로 코퍼스에 답이 없는 `no_data`라고 단정하지 않는다.
- 청크 파일의 SHA-256이 달라지면 평가는 중단한다. 재청킹 뒤 오래된 ID로 평가하는 일을 막기 위해서다.

현재 산출물이 있으면 재실행으로 덮어쓰지 않는다. 후보를 만들 때 DB가 반환한 text와 메타데이터를 로컬 JSONL과 대조하고, 생성 전후 코퍼스 해시도 확인한다.

### 4번 라벨링 결과

실제 로컬 검색으로 질문별 top-10 합집합을 생성했다. R01~R10 순서로 후보 수는 17, 21, 14, 16, 17, 21, 18, 20, 17, 16개다. 표기 비교 쌍을 합친 최종 판정 작업은 8개 묶음, 150개 항목이다. 58개를 관련, 92개를 무관으로 판정했으며 보류 항목은 없다. R01은 사용자가 판정했고 나머지는 사용자 위임에 따라 AI가 판정했다. 판정 주체와 이유는 qrels에 기록했다.

### 5번 Recall 평가 결과

공유 판정 묶음을 질문별 정답 집합에 연결하고 아래 명령으로 같은 qrels에 대한 Recall을 계산한다. 미완료 묶음의 질문은 0점으로 넣지 않고 제외 수와 ID를 표시한다.

```bash
./.venv/bin/python src/evaluate.py run
```

10개 질문이 모두 평가에 포함됐고 제외된 질문은 없다. Macro Recall은 다음과 같다.

| 방식 | Recall@5 | Recall@10 |
|---|---:|---:|
| BM25 | 0.469 | 0.610 |
| Vector | 0.407 | 0.682 |
| Hybrid | **0.534** | **0.734** |

세부 질문별 결과와 표기 비교 차이는 `data/week3/evaluation.md`, 재현 가능한 검색 ID와 계산값은 `data/week3/evaluation.json`에 저장한다. 이 수치는 pooled judgments에 포함된 라벨링 정답 집합 기준이며 전체 코퍼스의 모든 정답을 포함한다고 보장하지 않는다.

## 3. RAG Agent

### 6번 Context 조립

Hybrid 검색의 상위 5개 청크에 `[1]`부터 `[5]`까지 짧은 번호를 붙인다. LLM에 전달하는 내용은 `title`, `source`, `text`이며, 프로그램 내부의 번호 매핑에는 실제 chunk ID를 유지한다. 입력 청크, 포함 청크, top-5 밖의 제외 청크, 8,000자 제한으로 잘린 청크를 `context_trace`에 기록한다. 잘린 청크의 매핑에는 실제로 Context에 들어간 text만 보존하므로 이후 인용 검사가 포함되지 않은 문장을 통과시키지 않는다.

API를 호출하지 않고 조립 결과만 확인할 수 있다.

```bash
./.venv/bin/python src/agent.py "Write-Behind의 동작 방식과 데이터 유실 위험은?" --context-only
```

이 질문의 실제 실행에서는 5개 청크가 모두 포함됐고 Context는 2,929자였다. 제외되거나 잘린 청크는 없었으며 `[1]`~`[5]`와 실제 chunk ID의 매핑을 확인했다.

### 다음 단계: LLM 연결

OpenAI API 키를 환경변수로 전달한다. 키를 코드나 `.env` 파일에 저장하지 않는다. 기본 모델은 비용을 고려해 `gpt-5.6-luna`를 사용하며 `OPENAI_MODEL`이나 `--model`로 바꿀 수 있다.

```bash
export OPENAI_API_KEY="발급받은 키"
# 선택 사항
export OPENAI_MODEL="사용할 모델 ID"
./.venv/bin/python src/agent.py "내가 Redis를 공부하면서 중요하게 생각했던 내용은?"
```

이 명령을 실행하면 질문과 Hybrid top-5 청크의 `title`, `source`, `text`가 OpenAI Responses API로 전송된다. API 요청에는 `store=false`를 설정하고 JSON Schema 구조화 출력을 사용한다.

LLM에는 `[1]`부터 `[5]`까지만 보여주고 프로그램 내부에서 실제 chunk ID를 보존한다. 답변은 JSON Schema로 받고, 인용 번호가 Context에 있는지, snippet이 비어 있지 않은지, `snippet in chunk.text`인지 검사한다. `citation_verified`는 이 기계적 검사를 통과했다는 뜻이다. 답변 전체가 질문에 정확히 답했는지는 별도로 판단해야 한다.

### 7번 LLM·인용 검증 결과

`Write-Behind의 동작 방식과 데이터 유실 위험은?` 질문을 실제 API로 실행했다. 모델은 캐시에 먼저 저장한 뒤 DB에 비동기로 반영하며, 반영 전에 캐시가 사라지면 데이터가 유실될 수 있다고 답했다. 두 개의 인용이 실제 Context 청크의 원문 부분 문자열로 확인되어 `citation_verified=true`가 됐다. 모델의 자기 보고인 `grounded=true`도 별도로 표시한다.

프로그램은 인용의 형식과 원문 존재 여부만 자동 판정한다. 의미 정확성은 자동 판정하지 않고 `semantic_correctness=not_evaluated`로 남긴다.

## 4. Multi-hop와 Oracle 실험

### 8번 Normal·Oracle 동일 경로 확인

Normal은 Hybrid top-5를, Oracle은 사람이 지정한 청크를 사용한다. Context 입력을 고르는 부분만 다르고 두 방식 모두 `answer_from_chunks()`에서 Context 조립, LLM 생성, 인용 검증을 수행한다.

```bash
./.venv/bin/python src/agent.py "질문" --compare --oracle <chunk_id> <chunk_id>
```

R01의 라벨링된 relevant 청크 5개를 Oracle로 지정해 실제 비교했다. Normal 검색도 같은 5개를 모두 찾았기 때문에 `missing_oracle_from_normal`은 없었다. 청크 순서는 달랐지만 두 답변은 Write-Behind의 비동기 DB 반영 방식과 캐시 장애 시 유실 위험을 동일하게 설명했다. Normal과 Oracle 모두 `grounded=true`, `citation_verified=true`였고 의미 정확성은 `not_evaluated`로 남겼다.

이 결과는 두 경로의 생성·검증 절차가 같다는 정상 동작 확인이다. Normal도 정답 청크를 모두 찾은 사례이므로 retrieval 실패를 보여주는 실험은 아니다.

실제 데이터에서 답을 확인한 질문만 사례 파일에 넣는다.

```bash
./.venv/bin/python src/failure_experiment.py template
# data/week3/cases.json을 사람이 작성
./.venv/bin/python src/failure_experiment.py run
```

Oracle Context를 한 건 직접 실행할 수도 있다.

```bash
./.venv/bin/python src/agent.py "질문" --oracle <chunk_id> <chunk_id>
```

실험기는 Normal·Oracle 답변, top-5, 누락된 gold chunks, citation 검증 결과를 `data/week3/failure_runs.jsonl`에 남긴다. 답변의 정답 여부와 `retrieval / assembly / composition / citation / no_data` 판정은 사람이 기록한다. 측정 전에는 실패 원인을 자동으로 단정하지 않는다.
