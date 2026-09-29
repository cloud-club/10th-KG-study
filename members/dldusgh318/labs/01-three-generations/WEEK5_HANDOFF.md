# 지식 그래프 스터디 5주차 결과 및 인수인계

> 기준 디렉터리: `members/dldusgh318/labs/01-three-generations`  
> 통계 기준: `extracted.review20.jsonl`의 청크 20개 표본  
> 주의: 이 문서의 추출 품질 수치는 전체 1,562개 청크 결과가 아니다.

## 1. 파이프라인 현황

### 1-1. 실행 여부

| 단계 | 상태 | 실제로 실행한 범위 | 핵심 결과 |
|---|---|---|---|
| 미니 온톨로지 | 완료 | 클래스 3종, 술어 5종 | RDFS 스키마와 추출 기준 작성 |
| LLM 트리플 추출기 | 완료 | OpenAI 구조화 출력, 검증·재시도·재개 구현 | 단위 테스트 통과 |
| 소수 추출 | 완료 | 선별 청크 20개 | 18개 성공, 2개 JSON 파싱 실패 |
| 전체 추출 | **미실행** | 전체 1,562개 청크를 돌리지 않음 | 비용·오류 양상을 먼저 확인하기 위해 보류 |
| 엔티티 정규화 | 완료 | 20개 표본 결과 | 원본 엔티티 113개 → 정규화 엔티티 75개 |
| PostgreSQL 적재 | 완료 | 20개 표본 결과 | 엔티티 75개, 엣지 157개 |
| Turtle·JSON-LD 출력 | 완료 | PostgreSQL 적재 결과 | RDF 트리플 295개 |
| Neo4j 적재 | 완료 | PostgreSQL의 노드 75개·그래프 관계 96개 | 2회 재적재 후 개수 불변 |
| X01 Cypher | 완료·실행 검증 | Neo4j 실제 실행 | Redis가 직행·TEAMFICIAL로 연결됨 |
| X03 Cypher | 완료·실행 검증 | Neo4j 실제 실행 | 직행 `proposed`와 타 프로젝트 `implemented` 구분 |
| Browser 시각화 쿼리 | 완료·실행 검증 | Redis 서브그래프 경로 8개 반환 | 실제 발표용 화면 캡처는 아직 안 함 |
| 추출 통계 | 완료 | 20개 표본 + 현재 DB | Markdown·JSON 생성 |

`extracted.jsonl`은 전체 결과가 아니다. 현재 이 파일에는 처음 시험한 알고리즘 청크
5개만 있고 모두 빈 추출 결과다. 현재 DB와 이 문서의 통계에 사용한 실질적인 입력은
`extracted.review20.jsonl`이다.

### 1-2. 산출물

| 산출물 | 위치 | 역할 |
|---|---|---|
| 온톨로지 | `schema.ttl` | 클래스·술어의 RDFS 정의 |
| 스키마 설명 | `SCHEMA.md` | 판정 기준, IRI 규칙, X01/X03 커버리지 |
| 추출기 | `src/extract_triples.py` | LLM 호출, 구조화 출력, 검증, 재시도·재개 |
| 20개 표본 입력 | `data/processed/chunks.review20.jsonl` | 표본 추출 대상 청크 |
| 20개 표본 결과 | `extracted.review20.jsonl` | 통계와 DB 적재에 사용한 결과 |
| PostgreSQL·RDF 적재기 | `src/store_kg.py` | 정규화, Postgres 적재, RDF 출력 |
| PostgreSQL DDL | `sql/kg_schema.sql` | `entities`, `edges`와 인덱스 |
| 정규화 로그 | `output/entity-normalization.jsonl` | LLM ID와 정규화 ID 매핑 |
| 정규화 요약 | `output/entity-normalization-summary.json` | 병합·변경·제외 건수 |
| Turtle | `output/my-kg.ttl` | 근거 메타데이터를 제외한 의미 그래프 |
| JSON-LD | `output/my-kg.jsonld` | 같은 그래프의 JSON-LD 직렬화 |
| Neo4j 적재기 | `src/load_neo4j.py` | 제약조건, `UNWIND` 배치, 멱등 적재 |
| Neo4j 검증 | `queries/neo4j_validation.cypher` | 라벨·관계 수, 중복·방향 검증 |
| 핵심 Cypher | `queries/week5.cypher` | X01, X03, 가변 경로, 근거 포함 질의 |
| 동등 SQL | `queries/week5.sql` | 같은 질문의 self-join·재귀 CTE 구현 |
| 시각화 Cypher | `queries/week5_visualization.cypher` | Redis 중심 발표용 서브그래프 |
| Browser 스타일 | `neo4j/browser-style.grass` | 노드 색상·크기·캡션 |
| 통계기 | `src/extraction_stats.py` | JSONL·DB 통계 생성 |
| 통계표 | `output/extraction-stats.md` | 발표용 통계 Markdown |
| 통계 원본 | `output/extraction-stats.json` | 후속 자동화용 JSON |

### 1-3. 재실행 방법

```bash
cd members/dldusgh318/labs/01-three-generations
source .venv/bin/activate
python3 -m pip install -r requirements.txt
docker compose up -d pg neo4j
```

표본을 새 출력 파일로 다시 추출한다. 기존 결과의 재개 로직과 섞이지 않게 출력명을
바꾸는 편이 안전하다.

```bash
export OPENAI_API_KEY='발급받은 키'
python3 src/extract_triples.py \
  --input data/processed/chunks.review20.jsonl \
  --output extracted.review20.rerun.jsonl
```

전체 추출은 아직 실행하지 않았다. 실행할 때는 표본 결과와 파일을 분리한다.

```bash
python3 src/extract_triples.py \
  --input data/processed/chunks.jsonl \
  --output extracted.full.jsonl
```

PostgreSQL 적재와 RDF 출력:

```bash
python3 src/store_kg.py --input extracted.review20.jsonl
```

Neo4j 적재 및 멱등성 검증:

```bash
python3 src/load_neo4j.py --verify-idempotency
```

통계 갱신:

```bash
python3 src/extraction_stats.py \
  --input extracted.review20.jsonl \
  --extraction-run v0-2026-09-28
```

테스트:

```bash
python3 -m unittest \
  tests.test_extract_triples \
  tests.test_store_kg \
  tests.test_load_neo4j \
  tests.test_extraction_stats
```

Neo4j Browser는 `http://localhost:7474`에서 접속한다.

```text
사용자: neo4j
비밀번호: study-password
```

## 2. 추출 통계

### 2-1. 범위

아래 수치는 **선별한 청크 20개 표본** 기준이다. 전체 `chunks.jsonl` 1,562개를
추출한 결과가 아니므로 전체 문서에 대한 정확도·재현율로 일반화하면 안 된다.

| 항목 | 20개 표본 결과 |
|---|---:|
| 처리 청크 | 20 |
| 정상 결과 청크 | 18 |
| 오류 청크 | 2 |
| 오류 청크 비율 | 10.00% |
| LLM 트리플 후보 | 161 |
| JSONL 검증 통과 | 160 |
| JSONL 검증 탈락 | 1 |
| 통과율 | 99.38% |
| `evidence_not_found` | 0 |
| 표본 환각률 | 0.00% |
| PostgreSQL 엔티티 | 75 |
| PostgreSQL 엣지 | 157 |
| Neo4j 노드 | 75 |
| Neo4j 관계 | 96 |

`0.00%`는 20개 표본에서 `evidence_not_found`가 없었다는 뜻일 뿐이다. 전체 데이터의
환각률이 0이라는 뜻이 아니다.

### 2-2. 오류 청크 2건

| chunk_id | 직접 원인 |
|---|---|
| `KUSITMS_X_직행_기업과제#162` | JSON 문자열이 닫히기 전에 응답이 끝나 `Unterminated string` 발생. JSON 재시도 2회를 모두 소진함 |
| `NHN_지원자_테스트_엔지니어_이연호_포트폴리오#218` | 동일하게 `Unterminated string` 발생. JSON 재시도 2회를 모두 소진함 |

두 오류 모두 인증·HTTP 오류가 아니라 **모델 응답이 중간에서 잘린 형태의 잘못된
JSON**이다. 저장된 오류만으로 종료 원인을 확정할 수는 없지만, 응답 문자열 길이가 각각
8,782자와 12,383자 지점까지 생성된 뒤 끊겼으므로 출력 토큰 한도 또는 장문 응답이
가장 유력하다. 후속 작업에서는 API 응답의 종료 사유를 함께 저장하고, 청크당 출력량을
줄이거나 최대 출력 토큰을 조정해야 한다.

### 2-3. JSONL 160건과 DB 157건의 차이

결론부터 말하면 **UNIQUE 충돌도 아니고 FK 위반도 아니다.** 정규화 단계에서 불완전한
`TechnologyUse` 하나를 통째로 제외하면서 정확히 3건이 줄었다.

문제 청크는 `KUSITMS_X_직행_기업과제#179`다. LLM이 `usesTechnology` 트리플의
subject에 공백을 하나 삽입했다.

```text
정상 엔티티 ID:
kg:use-kusitms-x-jikhaeng-gieopgwaje-tmap-api-1

usesTechnology subject:
kg:use-kusitms-x-jikhaeng-gieopgwaje- tmap-api-1
                                      ^ 불필요한 공백
```

이 `usesTechnology`는 `dangling_subject`로 탈락했다. 하지만 같은 사용례의 아래 세
트리플은 JSONL 검증을 통과했다.

| 제외된 통과 트리플 | 값 |
|---|---|
| `partOf` | 직행 프로젝트 |
| `hasPurpose` | 통근 시간 계산 로직 |
| `hasStatus` | implemented |

`store_kg.py`는 `partOf`와 `usesTechnology`를 모두 가진 사용례만 적재한다. 따라서
`usesTechnology`가 없는 이 사용례를 버리면서 위 3건도 DB에 들어가지 않았다.

```text
JSONL 검증 통과        160
정규화 후 적재 후보    157
PostgreSQL 실제 삽입    157
```

초기 적재 로그에서 157건이 모두 삽입됐고 FK 오류 없이 트랜잭션이 완료됐다. 동일 입력을
다시 실행했을 때는 157건 모두 UNIQUE 인덱스에 의해 `ON CONFLICT DO NOTHING` 처리되어
추가 행이 0개였다. 즉 최초의 3건 감소와 재실행 시 중복 방지는 서로 다른 현상이다.

### 2-4. 술어 분포

| 술어 | JSONL 통과 | PostgreSQL |
|---|---:|---:|
| `partOf` | 49 | 48 |
| `usesTechnology` | 48 | 48 |
| `hasPurpose` | 30 | 29 |
| `hasStatus` | 33 | 32 |
| `replaces` | 0 | 0 |
| 합계 | 160 | 157 |

## 3. X01 / X03 검증 결과

### 3-1. 여러 프로젝트를 잇는 기술

```sql
SELECT e.label AS tech,
       COUNT(DISTINCT p.label) AS n_projects,
       array_agg(DISTINCT p.label) AS projects
FROM edges u
JOIN entities e
  ON e.entity_id = u.object AND u.predicate = 'usesTechnology'
JOIN edges pt
  ON pt.subject = u.subject AND pt.predicate = 'partOf'
JOIN entities p
  ON p.entity_id = pt.object
GROUP BY e.label
HAVING COUNT(DISTINCT p.label) >= 2
ORDER BY n_projects DESC;
```

| tech | n_projects | projects |
|---|---:|---|
| redis | 3 | `{jikhaeng,secause,teamficial}` |
| docker | 2 | `{secause,teamficial}` |
| github actions | 2 | `{secause,teamficial}` |
| spring boot | 2 | `{secause,teamficial}` |

이 결과는 Redis가 프로젝트 문서 사이의 브리지 노드로 작동한다는 것을 증명한다.
4주차 RAG는 질문에 `Redis`라는 단어가 없어서 관련 청크를 연결하지 못했지만, 그래프는
SeCause의 작업 큐 사용례에서 Redis로 이동한 뒤 같은 Redis에 연결된 직행과
TEAMFICIAL을 찾는다. X01의 답은 “그렇다. Redis를 세 프로젝트가 공유한다”이다.

`docker`, `github actions`, `spring boot`도 두 프로젝트를 잇지만, X01의 “작업 큐”
목적 필터를 통과하는 SeCause 사용례가 가리키는 기술은 Redis다.

### 3-2. Redis 사용 목적과 상태

```sql
SELECT p.label AS project,
       u.props->>'purpose' AS purpose,
       u.props->>'status'  AS status
FROM edges ut
JOIN entities t
  ON t.entity_id = ut.object AND t.label = 'redis'
JOIN entities u
  ON u.entity_id = ut.subject
JOIN edges pt
  ON pt.subject = ut.subject AND pt.predicate = 'partOf'
JOIN entities p
  ON p.entity_id = pt.object
WHERE ut.predicate = 'usesTechnology'
ORDER BY 1;
```

| project | purpose | status |
|---|---|---|
| jikhaeng | 테스트 결과 저장 | implemented |
| jikhaeng | 동일한 출발지 - 도착지의 통근 시간 저장 | proposed |
| secause | 큐 기반 비동기 처리 | implemented |
| secause | NULL | implemented |
| teamficial | Redis 캐싱 인프라 | NULL |
| teamficial | 지원자 수 집계 성능 개선 | implemented |
| teamficial | 지원자 수 조회 캐시 | implemented |
| teamficial | NULL | NULL |
| teamficial | NULL | implemented |
| teamficial | 지원자 수 집계 쿼리의 반복 조회 비용 절감 | implemented |

직행의 “통근 시간 저장” Redis는 `proposed`이고, 직행의 “테스트 결과 저장” Redis는
`implemented`다. Redis라는 기술명이 같아도 목적과 상태가 다른 사실을 구분할 수 있다.

X03의 직접 답은 다음과 같다.

- 직행에서 통근 시간 캐시는 `proposed`다.
- SeCause에서는 Redis 작업 큐가 `implemented`다.
- TEAMFICIAL에서는 Redis 지원자 수 캐시가 `implemented`다.

실제 Neo4j X03 Cypher도 직행의 제안 사용례에서 Redis를 거쳐 SeCause와 TEAMFICIAL의
구현 사용례로 연결됐다. 즉 4주차 RAG가 놓친 “한 프로젝트의 제안이 다른 프로젝트에서
구현됐는가”를 그래프에서는 상태 조건과 조인으로 답할 수 있다.

## 4. ⚠️ 발견된 문제

이 절이 현재 결과에서 가장 중요하다. 표본 규모가 작아도 엔티티 분해와 품질 문제가
이미 나타났으며, 이를 고치지 않고 전체 추출을 실행하면 문제도 함께 확대된다.

### 4-1. TechnologyUse 과잉 생성

요청 초안에는 TEAMFICIAL Redis 사용례가 5개라고 되어 있었지만, 현재 DB를 다시
집계한 결과는 **6개**다. 대부분 같은 PR #81의 “지원자 수 집계 캐시”를 서로 다른
표현과 청크에서 반복 추출한 것이다.

현재 정규화 ID는 `(project, technology, purpose, status)`에 가깝게 생성된다. 같은
사실이라도 청크마다 목적 표현이 조금씩 달라지면 별도 사용례가 된다.

#### 집계 SQL

```sql
SELECT p.label AS project,
       t.label AS technology,
       COUNT(DISTINCT u.entity_id) AS technology_use_count,
       array_agg(DISTINCT u.entity_id ORDER BY u.entity_id) AS use_ids
FROM entities u
JOIN edges pt
  ON pt.subject = u.entity_id AND pt.predicate = 'partOf'
JOIN entities p
  ON p.entity_id = pt.object
JOIN edges ut
  ON ut.subject = u.entity_id AND ut.predicate = 'usesTechnology'
JOIN entities t
  ON t.entity_id = ut.object
WHERE u.type = 'TechnologyUse'
GROUP BY p.label, t.label
HAVING COUNT(DISTINCT u.entity_id) > 1
ORDER BY technology_use_count DESC, p.label, t.label;
```

#### 현재 20개 표본 DB 결과

| project | technology | TechnologyUse 수 |
|---|---|---:|
| teamficial | redis | 6 |
| secause | fastapi | 3 |
| secause | github api | 3 |
| jikhaeng | redis | 2 |
| jikhaeng | tmap api | 2 |
| secause | redis | 2 |
| secause | spring boot | 2 |

45개 `TechnologyUse`는 32개 `(project, technology)` 쌍에 매핑된다. 단순히 쌍마다
하나만 남긴다고 가정하면 초과 노드는 13개다. 그러나 이 13개가 전부 잘못된 중복은
아니다. 직행 Redis 2개처럼 목적과 상태가 실제로 다른 경우도 섞여 있다.

영향은 명확하다.

- `COUNT(*)`로 X01을 계산하면 “3개 프로젝트”가 아니라 사용례 행 수가 나와 답이
  부풀려진다.
- 현재 Redis 사용례 SQL도 프로젝트는 3개지만 행은 10개다.
- 발표 화면에서 같은 프로젝트와 기술 사이에 유사한 중간 노드가 반복되어 지저분하다.
- 반드시 `COUNT(DISTINCT project)`를 사용해야 현재 X01 답이 안정적이다.

### 4-2. purpose/status 결측과 통계 해석 오류

JSONL 술어 행 수는 `hasPurpose` 30건, `hasStatus` 33건이다. 하지만 이 숫자를 DB의
`TechnologyUse` 45개에서 바로 빼서 “목적 결측 15개, 상태 결측 12개”라고 계산하면
안 된다. 같은 정규화 사용례가 여러 청크에서 같은 속성 근거를 가질 수 있어 관계 행이
중복되기 때문이다.

DB 노드를 직접 센 정확한 결과는 다음과 같다.

```sql
SELECT count(*) AS uses,
       count(props->>'purpose') AS purpose_present,
       count(*) - count(props->>'purpose') AS purpose_missing,
       count(props->>'status') AS status_present,
       count(*) - count(props->>'status') AS status_missing
FROM entities
WHERE type = 'TechnologyUse';
```

| 항목 | 개수 |
|---|---:|
| TechnologyUse | 45 |
| purpose 보유 노드 | 26 |
| purpose 결측 노드 | **19** |
| status 보유 노드 | 29 |
| status 결측 노드 | **16** |

이 결측은 “명시되지 않으면 뽑지 않는다”는 프롬프트가 의도대로 작동한 결과이므로
버그로 취급하면 안 된다. 근거 없는 목적이나 상태를 채우는 것보다 NULL이 낫다.

대신 트레이드오프가 있다.

- 목적 필터를 사용하는 X01에서 `purpose IS NULL` 사용례는 후보가 될 수 없다.
- 상태 조건을 사용하는 X03에서 `status IS NULL` 사용례는 비교 대상에서 빠진다.
- 목적과 상태가 모두 없는 중간 노드는 그래프 탐색에는 참여하지만 설명력이 낮다.

전체 추출 전에 “불완전하지만 근거 있는 노드를 유지할지” 또는 “필수 속성이 없는
사용례를 제외할지”를 명시적으로 결정해야 한다. 현재 구현은 유지하는 쪽이다.

### 4-3. replaces 술어 0건

20개 표본에서 `replaces`는 JSONL과 DB 모두 0건이며 Neo4j에도 `REPLACES` 관계가 없다.

현재 표본에는 “새로운 명명 가능한 기술 사용례 A가 기존의 명명 가능한 기술 사용례
B를 대체했다”는 사례가 없다. “전체 컬렉션 로딩을 count 쿼리로 교체했다” 같은 서술은
있지만, 기존 방식이 현재 온톨로지의 `Technology`로 식별되지 않아 양쪽
`TechnologyUse`를 만들 수 없다. 따라서 **현재 0건의 주원인은 표본 데이터 부족**이다.

다만 추출 프롬프트에도 약점이 있다. `replaces`는 방향만 정의돼 있고 전용 판정 절과
few-shot이 없다. 실제 사례가 들어와도 다른 술어보다 재현율이 낮을 가능성을 배제할 수
없다.

권고안:

1. 전체 추출 전에 명시적인 기술 교체 문장 1개를 테스트 fixture와 few-shot으로 추가한다.
2. 전체 청크 추출 후 `replaces` 빈도를 다시 센다.
3. 전체 추출 후에도 0건이면 5종 술어에서 제외한다. 사용되지 않는 술어를 유지하면
   스키마와 발표만 복잡해진다.

## 5. 다음 단계

요청 초안의 체크리스트는 현재 실행 상태에 맞게 갱신했다.

- [x] 5단계 Neo4j 적재
- [x] 6단계 Cypher 질의 및 X01/X03 실제 실행
- [ ] 7단계 최종 Browser 캡처 및 **전체 추출 후** 통계 갱신
  - Redis 시각화 쿼리와 스타일은 작성·실행 검증 완료
  - 발표 슬라이드에 넣을 실제 캡처는 아직 없음
- [ ] TechnologyUse 병합(B안)
- [ ] 전체 1,562개 청크 추출

실제 작업 우선순위는 다음과 같다.

### 우선순위 1. TechnologyUse 병합 키 확정

전체 추출 전에 해결해야 한다. 지금 상태로 전체 추출을 먼저 하면 중복 사용례가 더
많이 쌓이고, 나중에 ID와 엣지를 다시 마이그레이션해야 한다.

권장 병합 키:

```text
(project_id, technology_id, normalized_purpose_cluster, status)
```

규칙:

1. `project_id + technology_id`로 1차 그룹화한다.
2. `status`가 다르면 절대 자동 병합하지 않는다.
3. purpose의 단순 문자열 일치뿐 아니라 동의 표현을 같은 목적 클러스터로 묶는다.
4. purpose가 NULL이라고 해서 다른 NULL 사용례와 자동 병합하지 않는다. “모름”은
   “같음”이 아니다.
5. 병합된 canonical 사용례에 원래 use ID와 모든 `chunk_id/evidence`를 보존한다.

직행 Redis는 아래 두 사용례를 반드시 분리해야 한다.

| purpose | status | 병합 여부 |
|---|---|---|
| 테스트 결과 저장 | implemented | 별도 유지 |
| 통근 시간 저장 | proposed | 별도 유지 |

`(project, technology)`만으로 무조건 합치면 X03의 proposed/implemented 구분이 깨진다.

### 우선순위 2. 전체 추출

병합 규칙과 `replaces` 테스트를 확정한 다음 `extracted.full.jsonl`로 실행한다. 표본과
전체 결과를 같은 파일에 섞지 않는다.

### 우선순위 3. 재적재·통계·발표 캡처

전체 결과로 PostgreSQL과 Neo4j를 갱신하고 통계를 다시 생성한다. 마지막으로 Redis
서브그래프를 Browser에서 캡처한다.

## 6. 설계 판단과 근거

### 6-1. 술어를 5종으로 제한한 이유

LLM에 술어 생성을 맡기면 `uses`, `adopts`, `builtWith`처럼 같은 의미가 여러 이름으로
갈라진다. 허용 술어를 5개로 고정하면 enum 검증, domain/range 검사, SQL·Cypher 경로를
작게 유지할 수 있다. X01과 X03에 필요한 관계를 표현하는 데도 충분했다.

단, `replaces`처럼 실제 사용 빈도가 0인 술어를 영구적으로 유지하겠다는 뜻은 아니다.
전체 추출 결과에 따라 줄이는 것이 맞다.

### 6-2. TechnologyUse 중간 노드를 만든 이유

`Project-USES-Technology`만으로는 프로젝트·기술 쌍에 목적과 상태를 붙일 수 없다.
특히 직행은 Redis를 테스트 결과 저장에는 실제 적용했고, 통근 시간 캐시에는 제안만
했다. `TechnologyUse`가 없으면 두 사실이 하나로 합쳐져 X03에 답할 수 없다.

중간 노드는 필요한 설계지만 현재 과잉 생성 문제도 만들었다. 결론은 중간 노드를
없애는 것이 아니라, 의미가 같은 사용례를 병합하는 식별 전략을 개선하는 것이다.

### 6-3. Turtle에서 evidence를 제외한 이유

RDF 트리플에는 `evidence`와 `chunk_id`를 직접 붙일 위치가 없다. 이를 RDF reification으로
표현하면 하나의 사실이 여러 보조 트리플로 증가하고 파일·질의가 급격히 복잡해진다.
따라서 Turtle과 JSON-LD는 의미 그래프만 담고, 근거는 PostgreSQL 엣지와 Neo4j 관계
속성에 보관했다.

현재 Neo4j 관계 96개 모두 `evidence`, `chunk_id`, 고유 `edge_key`를 가진다.

### 6-4. 20개 표본으로 먼저 완주한 이유

전체 1,562개 청크를 먼저 호출하면 비용을 쓴 뒤에야 스키마·프롬프트·정규화 문제를
발견하게 된다. 20개에는 X01과 X03에 필요한 직행, SeCause, TEAMFICIAL 사례를 의도적으로
포함해 다음을 먼저 확인했다.

- 구조화 출력과 검증이 실제로 동작하는가
- PostgreSQL과 Neo4j까지 끝까지 적재되는가
- RAG 실패 질문이 그래프 조인으로 풀리는가
- purpose/status가 X03을 구분하는가
- 같은 사실이 여러 청크에서 과잉 생성되는가

이 판단 덕분에 전체 추출 전에 JSON 절단 오류 10%, 불완전 사용례 1개,
`TechnologyUse` 과잉 생성, `replaces` 0건을 발견했다. 지금 전체 추출을 미룬 것은
진행이 덜 된 것이 아니라, 잘못된 구조를 1,562개 청크에 확대하지 않기 위한 결정이다.

## 인수인계 결론

파이프라인은 표본 20개 기준으로 LLM 추출부터 PostgreSQL, RDF, Neo4j, X01/X03 질의까지
완주했다. 다음 작업자는 전체 추출부터 시작하면 안 된다. 먼저 `TechnologyUse` 병합 키와
`replaces` 테스트 사례를 확정해야 한다. 그렇지 않으면 현재 20개 표본에서 이미 보인
중복과 결측 해석 문제가 전체 그래프에서 더 커진다.
