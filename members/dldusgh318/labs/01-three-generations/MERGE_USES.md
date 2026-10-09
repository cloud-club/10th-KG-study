# TechnologyUse 병합 운영

작업 위치: `members/dldusgh318/labs/01-three-generations`.

## 후보 및 계획

```bash
source .venv/bin/activate
python3 src/merge_uses.py candidates
export OPENAI_API_KEY='발급받은 키'
python3 src/merge_uses.py plan
```

`candidates`는 DB를 읽기만 하고 후보와 호출 수를 저장한다. `plan`도 DB를 수정하지
않는다. LLM 쌍별 판정은 `(project, technology, status)` 블록 안에서만 수행한다.
status NULL은 독립 블록이다. 크기 1인 그룹은 제외한다.

출력 디렉터리는 기본 `output/merge-v1`이다.

| 파일 | 내용 |
|---|---|
| `candidates.jsonl` | 후보 블록, 노드, purpose, 청크별 evidence 원문 전체 |
| `judgments.jsonl` | pair, same/different/unsure, 이유, LLM/규칙 구분 |
| `merge_plan.json` | 병합 집합, canonical, 대표 purpose, needs_review, DB 원본 해시 |
| `purpose_choices.json` | 대표 purpose 선택 캐시 및 선택 이유 |

purpose가 하나라도 NULL인 쌍에는 LLM을 호출하지 않는다. 동일 chunk_id의 공백
정규화 evidence 교집합이 있을 때만 same이다. 나머지는 different다.

same 연결 요소 내부 모든 쌍이 same이어야 병합한다. 연결 요소 안에 different/unsure가
하나라도 있으면 그 요소 전체를 needs_review로 남긴다. 부분 집합을 임의로 병합하지 않는다.

canonical은 사전순 최소 ID다. 대표 purpose가 여러 개라면 LLM이 원본 enum 중 하나를
선택한다. 원본 값 하나 또는 전부 NULL이면 별도 LLM 선택이 불필요하다.
판정·purpose 선택 캐시는 입력 해시로 재사용한다. 프롬프트/모델/근거가 달라지면
쌍별 판정을 다시 한다. API 실패 시 apply하지 않고 plan을 다시 실행한다.

## 검토와 적용

`merge_plan.json`과 `judgments.jsonl`을 사람이 읽어 확인한다. 계획을 만든 뒤 DB가
바뀌면 apply는 실패한다. 후보 파일에 evidence 원문이 있으므로 레포에 커밋하지 않는다.

```bash
python3 src/merge_uses.py apply \
  --plan output/merge-v1/merge_plan.json \
  --merge-run merge-v1-2026-10-06
```

Postgres 적용은 테이블 잠금과 단일 트랜잭션으로 실행한다. 적용 전에 파일과 DB 양쪽에
entities/edges 전체 스냅샷을 저장한다. 실패하면 트랜잭션을 롤백한다.

- 병합 노드에서 나가거나 들어오는 IRI 엣지를 canonical로 재지정한다.
- `(subject, predicate, object, chunk_id)`가 같은 행만 중복 제거한다.
- 다른 청크의 evidence 행은 유지한다.
- 같은 청크에서도 evidence가 서로 다르면 충돌 원문을 `kg_merge_evidence`에 보존한다.
- `hasPurpose` 엣지의 원본 literal은 대표 purpose로 덮어쓰지 않는다.
- 대표값은 `entities.props.purpose`, 원본 배열은 `props.original_purposes`에 저장한다.
- 이력은 `kg_merge_runs`, canonical의 `props.merge_run`에 기록한다.

동일 plan과 merge_run 재적용은 DB를 바꾸지 않는다. 동일 merge_run에 다른 plan은
허용하지 않는다. 후속 merge_run은 현재 DB가 이전 적용 결과의 해시와 일치할 때만
추가할 수 있다. 역적용은 마지막 적용부터 역순으로 진행한다.

## 사람 판정과 v2 적용

`decided_by: "human"`과 `reason`이 있는 병합 항목은 LLM 쌍별 판정 및 NULL purpose
규칙을 명시적으로 재정의한다. 같은 project/technology/status, canonical 최소 ID,
원본 purpose 선택 규칙은 여전히 검증한다. 과거 LLM 판정은 삭제하지 않는다.

v2는 `merge_plan.json`, 기존 v1은 `merge_plan.v1.json`에 보존한다.
`dropped_edges`는 원본 행 ID와 내용 및 사유가 정확히 맞는 행만 삭제한다.
`technology_aliases`는 기술 ID 매핑을 기록하고 연결 엣지를 재지정한다.
둘 다 적용 보고서 및 적용 전 스냅샷에 남는다.

```bash
.venv/bin/python src/merge_uses.py apply --merge-run merge-v2-2026-10-07
# 같은 명령 재실행은 변경 없음
.venv/bin/python src/merge_uses.py unmerge --merge-run merge-v2-2026-10-07
# v1까지 되돌릴 때는 v2 역적용 후 아래 실행
.venv/bin/python src/merge_uses.py unmerge --merge-run merge-v1-2026-10-07 --plan output/merge-v1/merge_plan.v1.json
```

메시지 큐, 아웃박스 패턴, ai, db 노드 정리는 재추출이 필요한 별도 작업으로 남긴다.

apply 뒤에는 Neo4j를 재적재하고 Postgres에서 사라진 노드·관계를 정리한다.
Neo4j는 분산 트랜잭션이 아니므로 동기화 실패 시 Postgres는 적용 완료 상태일 수 있다.
다음 명령으로 동기화를 재시도한다.

```bash
python3 src/merge_uses.py sync
```

Neo4j 관계의 `evidence_originals` 배열에는 UNIQUE 충돌로 합쳐진 원문도 들어간다.
외부 관계가 연결된 오래된 노드는 삭제하지 않고 동기화 오류를 출력한다.

## 적용 후 검증

보고서는 `output/merge-v1/{merge_run}.report.json`에 저장한다.

- TechnologyUse 병합 전/후 개수
- 병합 집합 수와 needs_review 수
- UNIQUE 중복 제거 행 수
- `(project, technology)`별 남은 사용례 수
- 직행 Redis: proposed 1개 / implemented 1개

직행 Redis 검사에 실패하면 적용 전체를 롤백한다.

## 역적용

```bash
python3 src/merge_uses.py unmerge \
  --plan output/merge-v1/merge_plan.json \
  --merge-run merge-v1-2026-10-06
```

같은 계획과 merge_run으로 병합 전 entities/edges를 정확히 복원하고 Neo4j를 동기화한다.
병합 후 DB가 달라졌다면 새 작업을 덮어쓰지 않도록 역적용을 거부한다.
unmerge도 같은 명령을 재실행할 수 있다.

병합 후 원본 `store_kg.py`를 재실행하면 과거 사용례 ID가 재생성될 수 있다.
원본 재적재나 전체 추출은 unmerge 후 수행하고 병합 계획을 새로 생성한다.
