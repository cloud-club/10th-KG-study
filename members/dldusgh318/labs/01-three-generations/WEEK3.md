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

검색 평가 후보는 정확한 용어·심볼·프로젝트 3개, 의미 검색 3개, 표기 비교 2쌍으로 총 10개다. W2 질문과 구분하기 위해 R01~R10을 사용한다. 모두 원문 확인 전 후보(`revise`)이며 정답 청크는 지정하지 않았다.

R07/R08은 Elasticsearch 표기 비교, R09/R10은 Kubernetes 오타 비교다. 각 쌍은 동일한 골드셋을 사용한다. 10개 질문은 8개 정보 요구를 포함하므로 전체 평균 외에 쌍별 차이도 확인한다. `gold_group`은 설계 메타데이터이며 현재 평가 코드가 동일 골드셋을 강제하거나 쌍별 차이를 자동 계산하지는 않는다.

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

위 표는 합의한 설계다. 현재 qrels 코드는 관련 ID 목록과 질문별 완료 상태를 지원하며, 청크별 무관·보류 판정 저장과 검증은 라벨링 단계에서 정리한다. 템플릿의 후보 ID 목록은 실제 판정 완료를 의미하지 않는다.

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
- `data/week3/candidate_pool.json`: 검색기별 순위가 보존된 후보
- `data/week3/qrels.json`: 골드셋 템플릿

qrels에서 질문마다 다음 원칙을 적용한다.

- `status`가 `complete`인 질문만 평가한다.
- `relevant`에는 `{ "id": "...", "note": "판정 근거" }`를 기록한다.
- 후보 풀 밖에서 찾은 정답도 추가한다. pooled judging은 검색기 셋이 모두 놓친 정답을 보여주지 못하기 때문이다.
- 단순 단어 포함이 아니라 질문의 `labeling_rule`을 만족하는지를 판정한다.
- 관련 청크가 하나도 없는 질문은 검색 Recall에서 제외하고 Agent의 `no_data` 실험으로 분리한다.
- 청크 파일의 SHA-256이 달라지면 평가는 중단한다. 재청킹 뒤 오래된 ID로 평가하는 일을 막기 위해서다.

라벨링 후 측정한다.

```bash
./.venv/bin/python src/evaluate.py run
```

BM25, Vector, Hybrid의 Recall@5/10과 질문별 macro average만 실제 결과로 출력한다. 미완료 질문은 0점으로 간주하지 않고 제외 개수를 표시한다.

## 3. RAG Agent

OpenAI API 키와 사용할 모델을 환경변수로 전달한다. 키를 코드나 `.env` 파일에 저장하지 않는다.

```bash
export OPENAI_API_KEY="발급받은 키"
export OPENAI_MODEL="사용할 모델 ID"
./.venv/bin/python src/agent.py "내가 Redis를 공부하면서 중요하게 생각했던 내용은?"
```

이 명령을 실행하면 질문과 Hybrid top-5 청크의 `title`, `source`, `text`가 OpenAI API로 전송된다. API 요청에는 `store=false`를 설정한다.

LLM에는 `[1]`부터 `[5]`까지만 보여주고 프로그램 내부에서 실제 chunk ID를 보존한다. 답변은 JSON Schema로 받고, 모든 snippet에 대해 `snippet in chunk.text`를 검사한다. 이 검사는 인용문이 원문에 존재하는지만 보장하며 답변 전체의 의미적 정확성을 대신하지 않는다.

## 4. Multi-hop와 Oracle 실험

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
