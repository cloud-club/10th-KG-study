# Text2Cypher — 20개 청크 표본 Neo4j

7문항 × 3회 = 21회. 모델이 생성한 Cypher를 수정하지 않고 읽기 실행했다. 실패 시 자동 재생성·수정은 하지 않았다.
실행 에러: 0건. 판정: {'correct': 17, 'partial': 1, 'wrong': 3}. 주 실패 유형: {'semantic_wrong': 1, 'wrong_value': 3}.
wrong_value 3건은 모두 zero_rows를 함께 기록한다. 유형은 중복 집계하지 않고 주 원인과 결과를 분리한다.

## 실제 스키마

- Project 3개: id, label. Technology 25개: id, label. TechnologyUse 41개: id, purpose, status.
- 실제 추가 속성(entity_id/label/ingested_from 등)은 실행 메타데이터에 기록했다.
- (TechnologyUse)-[:PART_OF]->(Project) 48개, (TechnologyUse)-[:USES_TECHNOLOGY]->(Technology) 48개. REPLACES는 현재 0개라 프롬프트의 실제 관계에 추가하지 않았다.
- status: implemented 22, proposed 3, 미기재 16. not_implemented는 허용값이지만 실제 저장값은 0개.
- 같은 노드 사이에 청크별 근거 관계가 여러 개 있으므로 기술·프로젝트·사용례 집계는 DISTINCT 식별자가 필요하다.

## 질문별 3회 결과

| 질문 | 1회 | 2회 | 3회 |
|---|---|---|---|
| 가장 많은 프로젝트에서 쓴 기술은? | correct | correct | correct |
| 제안만 하고 구현 안 한 기술은? | partial | correct | correct |
| SeCause에서 분석 작업 큐에 사용한 기술을 TEAMFICIAL에서는 어떤 용도로 사용했나? | wrong | wrong | wrong |
| 직행 프로젝트에서 통근 시간 API 비용을 줄이기 위해 제안한 방법 중, TEAMFICIAL 지원자 수 집계에 실제 적용한 방법은 무엇이며 두 프로젝트에서 각각 어떻게 쓰였나? | correct | correct | correct |
| TEAMFICIAL과 SeCause가 둘 다 쓴 기술은? | correct | correct | correct |
| Redis를 제안만 한 프로젝트는? | correct | correct | correct |
| 목적이 기록되지 않은 기술 사용례는 몇 개인가? | correct | correct | correct |

## 의미 오류 — 핵심

### A2 1회: 실행 성공, 질문 범위는 틀림

사용례의 proposed를 찾은 뒤 같은 기술에 implemented 사용례가 하나라도 존재하면 기술 전체를 제외하는 NOT EXISTS를 추가했다. 결과는 메시지 큐와 outbox 패턴 2개뿐이다.
Redis는 TEAMFICIAL/SeCause뿐 아니라 직행의 다른 목적에도 implemented 사용례가 있다. 이것이 직행의 통근시간 캐시 proposed를 없애지는 않는다. 기술 단위와 사용례 단위를 혼동한 semantic_wrong이다.
현재 expected는 proposed 사용례 기준이므로 partial로 판정했다. 모든 프로젝트에서 한 번도 구현하지 않은 기술만 찾는 다른 질문이라면 결과 해석이 달라진다.

### X01 3회: 데이터가 없는 것이 아니라 조건 값이 맞지 않음

생성 조건은 purpose CONTAINS "분석 작업 큐" 또는 "분석" AND "큐"였다. 실제 SeCause Redis purpose는 "큐 기반 비동기 처리", "분석 작업을 백그라운드로 분리", NULL이다. 한 노드의 문자열에 질문의 모든 단어가 함께 들어 있지 않아 0건이 됐다.
진단용으로 purpose CONTAINS "큐"를 조회하면 공통 Redis와 TEAMFICIAL의 "지원자 수 집계 성능 개선"(implemented), "Redis 캐싱 인프라"(상태 미기재), 목적 NULL(상태 미기재) 3개가 나온다. 이 진단 결과로 원래 생성 쿼리를 고치거나 성공 처리하지 않았다.

### X03: 결과는 맞지만 과소제약 위험이 남음

현재 표본은 직행 proposed Redis와 TEAMFICIAL implemented 지원자 수 캐시를 반환하므로 correct다. 그러나 질문의 통근시간/지원자 수 목적은 WHERE에 없다. 다른 목적의 사용례가 추가되면 무관한 행도 나올 수 있다. 현재 관측 semantic_wrong과 향후 위험을 혼동해 집계하지 않는다.

### T02: "제안만"의 범위

proposed Redis 사용례가 있는 프로젝트는 직행이다. 직행의 테스트 결과 저장 Redis는 implemented다. 따라서 "직행은 Redis를 어떤 용도로도 구현하지 않았다"라고 답하면 틀린다. 이번 판정은 해당 proposed 사용례가 있는 프로젝트를 묻는 것으로 해석한다.

### T03: 목적 결측

목적 미기재 TechnologyUse는 18개다. 관계 수가 아니라 노드 식별자 기준이다. 현재 데이터에서는 빈 문자열이 없으므로 IS NULL과 빈 문자열까지 포함한 조건의 결과가 같다.

## 전체 기록

| 질문 / 회차 | 생성된 Cypher | 실행 결과 행 | 에러 | 판정 | 실패 유형 |
|---|---|---|---|---|---|
| A1 1회: 가장 많은 프로젝트에서 쓴 기술은? | `MATCH (u:TechnologyUse)-[:USES_TECHNOLOGY]->(t:Technology), (u)-[:PART_OF]->(p:Project) RETURN t.id AS technology_id, t.label AS technology, count(DISTINCT p.id) AS project_count ORDER BY project_count DESC, technology_id LIMIT 1` | [{"technology_id": "kg:tech-redis", "technology": "redis", "project_count": 3}] | null | correct | 없음 |
| A2 1회: 제안만 하고 구현 안 한 기술은? | `MATCH (u:TechnologyUse)-[:USES_TECHNOLOGY]->(t:Technology) WHERE u.status = 'proposed' AND NOT EXISTS { MATCH (u2:TechnologyUse)-[:USES_TECHNOLOGY]->(t) WHERE u2.status = 'implemented' } RETURN DISTINCT t.id AS technology_id, t.label AS technology ORDER BY technology_id` | [{"technology_id": "kg:tech-mesiji-kyu", "technology": "메시지 큐"}, {"technology_id": "kg:tech-outbox-paeteon", "technology": "outbox 패턴"}] | null | partial | semantic_wrong |
| X01 1회: SeCause에서 분석 작업 큐에 사용한 기술을 TEAMFICIAL에서는 어떤 용도로 사용했나? | `MATCH (u1:TechnologyUse)-[:PART_OF]->(:Project {id:'kg:secause'}), (u1)-[:USES_TECHNOLOGY]->(t:Technology), (u2:TechnologyUse)-[:PART_OF]->(p2:Project {id:'kg:teamficial'}), (u2)-[:USES_TECHNOLOGY]->(t) WHERE (toLower(coalesce(u1.purpose,'')) CONTAINS 'analysis' AND toLower(coalesce(u1.purpose,'')) CONTAINS 'queue') OR (u1.purpose CONTAINS '분석' AND u1.purpose CONTAINS '큐') RETURN DISTINCT t.id AS technology_id, t.label AS technology, p2.id AS project_id, p2.label AS project, u2.purpose AS purpose, u2.status AS status ORDER BY technology_id` | [] | null | wrong | wrong_value, zero_rows |
| X03 1회: 직행 프로젝트에서 통근 시간 API 비용을 줄이기 위해 제안한 방법 중, TEAMFICIAL 지원자 수 집계에 실제 적용한 방법은 무엇이며 두 프로젝트에서 각각 어떻게 쓰였나? | `MATCH (uJ:TechnologyUse)-[:PART_OF]->(pJ:Project {id:'kg:jikhaeng'}), (uJ)-[:USES_TECHNOLOGY]->(t:Technology), (uT:TechnologyUse)-[:PART_OF]->(pT:Project {id:'kg:teamficial'}), (uT)-[:USES_TECHNOLOGY]->(t) WHERE uJ.status='proposed' AND uT.status='implemented' RETURN DISTINCT t.id AS technology_id, t.label AS technology, pJ.id AS jikhaeng_project_id, uJ.purpose AS jikhaeng_purpose, uJ.status AS jikhaeng_status, pT.id AS teamficial_project_id, uT.purpose AS teamficial_purpose, uT.status AS teamficial_status ORDER BY technology_id` | [{"technology_id": "kg:tech-redis", "technology": "redis", "jikhaeng_project_id": "kg:jikhaeng", "jikhaeng_purpose": "동일한 출발지 - 도착지의 통근 시간 저장", "jikhaeng_status": "proposed", "teamficial_project_id": "kg:teamficial", "teamficial_purpose": "지원자 수 집계 성능 개선", "teamficial_status": "implemented"}] | null | correct | 없음 |
| T01 1회: TEAMFICIAL과 SeCause가 둘 다 쓴 기술은? | `MATCH (t:Technology)<-[:USES_TECHNOLOGY]-(u1:TechnologyUse)-[:PART_OF]->(p1:Project {id:'kg:teamficial'}), (t)<-[:USES_TECHNOLOGY]-(u2:TechnologyUse)-[:PART_OF]->(p2:Project {id:'kg:secause'}) RETURN DISTINCT t.id AS technology_id, t.label AS technology ORDER BY technology_id` | [{"technology_id": "kg:tech-docker", "technology": "docker"}, {"technology_id": "kg:tech-github-actions", "technology": "github actions"}, {"technology_id": "kg:tech-redis", "technology": "redis"}, {"technology_id": "kg:tech-spring-boot", "technology": "spring boot"}] | null | correct | 없음 |
| T02 1회: Redis를 제안만 한 프로젝트는? | `MATCH (t:Technology {id:'kg:tech-redis'})<-[:USES_TECHNOLOGY]-(u:TechnologyUse)-[:PART_OF]->(p:Project) WHERE u.status='proposed' RETURN DISTINCT p.id AS project_id, p.label AS project ORDER BY project_id` | [{"project_id": "kg:jikhaeng", "project": "jikhaeng"}] | null | correct | 없음 |
| T03 1회: 목적이 기록되지 않은 기술 사용례는 몇 개인가? | `MATCH (u:TechnologyUse) WHERE u.purpose IS NULL RETURN count(DISTINCT u.id) AS technology_use_count` | [{"technology_use_count": 18}] | null | correct | 없음 |
| A1 2회: 가장 많은 프로젝트에서 쓴 기술은? | `MATCH (u:TechnologyUse)-[:USES_TECHNOLOGY]->(t:Technology), (u)-[:PART_OF]->(p:Project) RETURN t.id AS technology_id, t.label AS technology, count(DISTINCT p.id) AS project_count ORDER BY project_count DESC, technology_id LIMIT 1` | [{"technology_id": "kg:tech-redis", "technology": "redis", "project_count": 3}] | null | correct | 없음 |
| A2 2회: 제안만 하고 구현 안 한 기술은? | `MATCH (u:TechnologyUse)-[:USES_TECHNOLOGY]->(t:Technology) WHERE u.status='proposed' RETURN DISTINCT t.id AS technology_id, t.label AS technology ORDER BY technology_id` | [{"technology_id": "kg:tech-mesiji-kyu", "technology": "메시지 큐"}, {"technology_id": "kg:tech-outbox-paeteon", "technology": "outbox 패턴"}, {"technology_id": "kg:tech-redis", "technology": "redis"}] | null | correct | 없음 |
| X01 2회: SeCause에서 분석 작업 큐에 사용한 기술을 TEAMFICIAL에서는 어떤 용도로 사용했나? | `MATCH (u1:TechnologyUse)-[:PART_OF]->(:Project {id:'kg:secause'}), (u1)-[:USES_TECHNOLOGY]->(t:Technology), (u2:TechnologyUse)-[:USES_TECHNOLOGY]->(t), (u2)-[:PART_OF]->(p:Project {id:'kg:teamficial'}) WHERE u1.purpose CONTAINS '분석 작업 큐' RETURN DISTINCT t.id AS technology_id, t.label AS technology, p.id AS project_id, p.label AS project, u2.purpose AS purpose ORDER BY technology_id, purpose` | [] | null | wrong | wrong_value, zero_rows |
| X03 2회: 직행 프로젝트에서 통근 시간 API 비용을 줄이기 위해 제안한 방법 중, TEAMFICIAL 지원자 수 집계에 실제 적용한 방법은 무엇이며 두 프로젝트에서 각각 어떻게 쓰였나? | `MATCH (u1:TechnologyUse)-[:PART_OF]->(p1:Project {id:'kg:jikhaeng'}), (u1)-[:USES_TECHNOLOGY]->(t:Technology), (u2:TechnologyUse)-[:PART_OF]->(p2:Project {id:'kg:teamficial'}), (u2)-[:USES_TECHNOLOGY]->(t) WHERE u1.status='proposed' AND u2.status='implemented' RETURN DISTINCT t.id AS technology_id, t.label AS technology, p1.id AS jikhaeng_project_id, u1.purpose AS jikhaeng_purpose, u1.status AS jikhaeng_status, p2.id AS teamficial_project_id, u2.purpose AS teamficial_purpose, u2.status AS teamficial_status ORDER BY technology_id` | [{"technology_id": "kg:tech-redis", "technology": "redis", "jikhaeng_project_id": "kg:jikhaeng", "jikhaeng_purpose": "동일한 출발지 - 도착지의 통근 시간 저장", "jikhaeng_status": "proposed", "teamficial_project_id": "kg:teamficial", "teamficial_purpose": "지원자 수 집계 성능 개선", "teamficial_status": "implemented"}] | null | correct | 없음 |
| T01 2회: TEAMFICIAL과 SeCause가 둘 다 쓴 기술은? | `MATCH (u1:TechnologyUse)-[:PART_OF]->(:Project {id:'kg:teamficial'}), (u1)-[:USES_TECHNOLOGY]->(t:Technology), (u2:TechnologyUse)-[:PART_OF]->(:Project {id:'kg:secause'}), (u2)-[:USES_TECHNOLOGY]->(t) RETURN DISTINCT t.id AS technology_id, t.label AS technology ORDER BY technology_id` | [{"technology_id": "kg:tech-docker", "technology": "docker"}, {"technology_id": "kg:tech-github-actions", "technology": "github actions"}, {"technology_id": "kg:tech-redis", "technology": "redis"}, {"technology_id": "kg:tech-spring-boot", "technology": "spring boot"}] | null | correct | 없음 |
| T02 2회: Redis를 제안만 한 프로젝트는? | `MATCH (t:Technology {id:'kg:tech-redis'})<-[:USES_TECHNOLOGY]-(u:TechnologyUse)-[:PART_OF]->(p:Project) WHERE u.status='proposed' RETURN DISTINCT p.id AS project_id, p.label AS project ORDER BY project_id` | [{"project_id": "kg:jikhaeng", "project": "jikhaeng"}] | null | correct | 없음 |
| T03 2회: 목적이 기록되지 않은 기술 사용례는 몇 개인가? | `MATCH (u:TechnologyUse) WHERE u.purpose IS NULL RETURN count(DISTINCT u.id) AS technology_use_count` | [{"technology_use_count": 18}] | null | correct | 없음 |
| A1 3회: 가장 많은 프로젝트에서 쓴 기술은? | `MATCH (u:TechnologyUse)-[:PART_OF]->(p:Project), (u)-[:USES_TECHNOLOGY]->(t:Technology) RETURN t.id AS technology_id, t.label AS technology, count(DISTINCT p.id) AS project_count ORDER BY project_count DESC, technology_id LIMIT 1` | [{"technology_id": "kg:tech-redis", "technology": "redis", "project_count": 3}] | null | correct | 없음 |
| A2 3회: 제안만 하고 구현 안 한 기술은? | `MATCH (u:TechnologyUse {status:'proposed'})-[:USES_TECHNOLOGY]->(t:Technology) RETURN DISTINCT t.id AS technology_id, t.label AS technology ORDER BY technology_id` | [{"technology_id": "kg:tech-mesiji-kyu", "technology": "메시지 큐"}, {"technology_id": "kg:tech-outbox-paeteon", "technology": "outbox 패턴"}, {"technology_id": "kg:tech-redis", "technology": "redis"}] | null | correct | 없음 |
| X01 3회: SeCause에서 분석 작업 큐에 사용한 기술을 TEAMFICIAL에서는 어떤 용도로 사용했나? | `MATCH (u1:TechnologyUse)-[:PART_OF]->(:Project {id:'kg:secause'}), (u1)-[:USES_TECHNOLOGY]->(t:Technology), (u2:TechnologyUse)-[:PART_OF]->(p2:Project {id:'kg:teamficial'}), (u2)-[:USES_TECHNOLOGY]->(t) WHERE u1.purpose CONTAINS '분석 작업 큐' RETURN DISTINCT t.id AS technology_id, t.label AS technology, p2.id AS project_id, p2.label AS project, u2.purpose AS purpose, u2.status AS status ORDER BY technology_id` | [] | null | wrong | wrong_value, zero_rows |
| X03 3회: 직행 프로젝트에서 통근 시간 API 비용을 줄이기 위해 제안한 방법 중, TEAMFICIAL 지원자 수 집계에 실제 적용한 방법은 무엇이며 두 프로젝트에서 각각 어떻게 쓰였나? | `MATCH (u1:TechnologyUse)-[:PART_OF]->(p1:Project {id:'kg:jikhaeng'}), (u1)-[:USES_TECHNOLOGY]->(t:Technology), (u2:TechnologyUse)-[:PART_OF]->(p2:Project {id:'kg:teamficial'}), (u2)-[:USES_TECHNOLOGY]->(t) WHERE u1.status='proposed' AND u2.status='implemented' RETURN DISTINCT t.id AS technology_id, t.label AS technology, p1.id AS jikhaeng_project_id, u1.purpose AS jikhaeng_purpose, u1.status AS jikhaeng_status, p2.id AS teamficial_project_id, u2.purpose AS teamficial_purpose, u2.status AS teamficial_status ORDER BY technology_id` | [{"technology_id": "kg:tech-redis", "technology": "redis", "jikhaeng_project_id": "kg:jikhaeng", "jikhaeng_purpose": "동일한 출발지 - 도착지의 통근 시간 저장", "jikhaeng_status": "proposed", "teamficial_project_id": "kg:teamficial", "teamficial_purpose": "지원자 수 집계 성능 개선", "teamficial_status": "implemented"}] | null | correct | 없음 |
| T01 3회: TEAMFICIAL과 SeCause가 둘 다 쓴 기술은? | `MATCH (t:Technology)<-[:USES_TECHNOLOGY]-(u1:TechnologyUse)-[:PART_OF]->(p1:Project {id:'kg:teamficial'}), (t)<-[:USES_TECHNOLOGY]-(u2:TechnologyUse)-[:PART_OF]->(p2:Project {id:'kg:secause'}) RETURN DISTINCT t.id AS technology_id, t.label AS technology ORDER BY technology_id` | [{"technology_id": "kg:tech-docker", "technology": "docker"}, {"technology_id": "kg:tech-github-actions", "technology": "github actions"}, {"technology_id": "kg:tech-redis", "technology": "redis"}, {"technology_id": "kg:tech-spring-boot", "technology": "spring boot"}] | null | correct | 없음 |
| T02 3회: Redis를 제안만 한 프로젝트는? | `MATCH (t:Technology {id:'kg:tech-redis'})<-[:USES_TECHNOLOGY]-(u:TechnologyUse)-[:PART_OF]->(p:Project) WHERE u.status='proposed' RETURN DISTINCT p.id AS project_id, p.label AS project ORDER BY project_id` | [{"project_id": "kg:jikhaeng", "project": "jikhaeng"}] | null | correct | 없음 |
| T03 3회: 목적이 기록되지 않은 기술 사용례는 몇 개인가? | `MATCH (u:TechnologyUse) WHERE u.purpose IS NULL RETURN count(DISTINCT u.id) AS technology_use_count` | [{"technology_use_count": 18}] | null | correct | 없음 |

## 0건 응답 — 생성 조건을 숨기지 않음

### X01 / 1회

이 결과는 전체 문서가 아니라 20개 청크 표본 그래프 기준입니다. 이 조건으로 찾았는데 없다. 전체 데이터에 없다는 뜻은 아닙니다.
MATCH (u1:TechnologyUse)-[:PART_OF]->(:Project {id:'kg:secause'}), (u1)-[:USES_TECHNOLOGY]->(t:Technology), (u2:TechnologyUse)-[:PART_OF]->(p2:Project {id:'kg:teamficial'}), (u2)-[:USES_TECHNOLOGY]->(t) WHERE (toLower(coalesce(u1.purpose,'')) CONTAINS 'analysis' AND toLower(coalesce(u1.purpose,'')) CONTAINS 'queue') OR (u1.purpose CONTAINS '분석' AND u1.purpose CONTAINS '큐') RETURN DISTINCT t.id AS technology_id, t.label AS technology, p2.id AS project_id, p2.label AS project, u2.purpose AS purpose, u2.status AS status ORDER BY technology_id

### X01 / 2회

이 결과는 전체 문서가 아니라 20개 청크 표본 그래프 기준입니다. 이 조건으로 찾았는데 없다. 전체 데이터에 없다는 뜻은 아닙니다.
MATCH (u1:TechnologyUse)-[:PART_OF]->(:Project {id:'kg:secause'}), (u1)-[:USES_TECHNOLOGY]->(t:Technology), (u2:TechnologyUse)-[:USES_TECHNOLOGY]->(t), (u2)-[:PART_OF]->(p:Project {id:'kg:teamficial'}) WHERE u1.purpose CONTAINS '분석 작업 큐' RETURN DISTINCT t.id AS technology_id, t.label AS technology, p.id AS project_id, p.label AS project, u2.purpose AS purpose ORDER BY technology_id, purpose

### X01 / 3회

이 결과는 전체 문서가 아니라 20개 청크 표본 그래프 기준입니다. 이 조건으로 찾았는데 없다. 전체 데이터에 없다는 뜻은 아닙니다.
MATCH (u1:TechnologyUse)-[:PART_OF]->(:Project {id:'kg:secause'}), (u1)-[:USES_TECHNOLOGY]->(t:Technology), (u2:TechnologyUse)-[:PART_OF]->(p2:Project {id:'kg:teamficial'}), (u2)-[:USES_TECHNOLOGY]->(t) WHERE u1.purpose CONTAINS '분석 작업 큐' RETURN DISTINCT t.id AS technology_id, t.label AS technology, p2.id AS project_id, p2.label AS project, u2.purpose AS purpose, u2.status AS status ORDER BY technology_id

## 실행 및 보안

```bash
.venv/bin/python src/text2cypher.py
.venv/bin/python src/report_text2cypher.py
```

- 키는 .env에서 읽고 출력·기록하지 않는다. 질문과 스키마/예시만 OpenAI로 보내며 실행 결과를 다시 LLM에 보내지는 않는다.
- 정적 단일 쿼리 검사, EXPLAIN의 읽기 query_type, execute_read, 트랜잭션 10초 제한을 적용했다. CALL/APOC/LOAD CSV/쓰기/다중 문장은 차단한다.
- 현재 로컬 계정은 관리자이므로 운영 환경에서는 별도 읽기 전용 권한 계정을 추가해야 한다. 정규식 가드를 일반 Cypher 보안 샌드박스로 주장하지 않는다.
- 실행 전후 그래프 전체 스냅샷 해시가 같음을 확인했다.
- 원본: text2cypher.jsonl. 판정 결합본: text2cypher_scored.jsonl. 원본의 null 판정은 결합본에서 채운다.
- 실제 DB 스냅샷: text2cypher_schema.json. 모델·reasoning_effort·verbosity·프롬프트·few-shot·스키마는 JSONL 첫 줄에 저장했다.

## 실제 프롬프트

```text
질문을 Neo4j 5 Cypher 읽기 쿼리 1개로 변환하라. JSON의 cypher만 반환한다.
그래프는 전체 문서가 아니라 20개 청크 표본이다. 정답을 추측하거나 데이터를 변경하지 않는다.
주요 스키마:
Project {id,label}; Technology {id,label}; TechnologyUse {id,purpose,status}
(TechnologyUse)-[:PART_OF]->(Project)
(TechnologyUse)-[:USES_TECHNOLOGY]->(Technology)
purpose/status는 TechnologyUse 속성이지 관계나 Technology 속성이 아니다. NULL/미기재일 수 있다.
status 허용값: implemented / proposed / not_implemented. 상태는 해당 사용례의 상태다.
기술 id 예시: kg:tech-redis, kg:tech-docker. label/id는 소문자이며 프로젝트 id는 kg:secause, kg:teamficial, kg:jikhaeng이다.
Neo4j는 대소문자를 구분한다. 없던 라벨·속성·관계·값을 만들지 않는다.
한 사실에 여러 청크 근거가 있어 관계가 중복될 수 있다. 기술/프로젝트/사용례 개수를 셀 때 적절한 DISTINCT 식별자를 사용한다.
질문에 명시된 상태 조건만 사용하며 NULL을 implemented나 proposed로 추정하지 않는다.
용도와 상태를 묻는 질문이면 식별 기술, 프로젝트, 해당 사용례 purpose/status를 반환하라.
CALL, APOC, LOAD CSV, USE, 쓰기 명령은 금지한다. 코드 펜스와 설명 없이 쿼리만 JSON에 넣는다.
실제 DB 스키마 및 값 예시(정답 목록이 아님):
{"schema": {"Project": {"count": 3, "properties": ["entity_id", "id", "ingested_from", "label"]}, "Technology": {"count": 25, "properties": ["entity_id", "id", "ingested_from", "label"]}, "TechnologyUse": {"count": 41, "properties": ["entity_id", "id", "ingested_from", "label", "purpose", "status"]}}, "relationships": [[["TechnologyUse"], "PART_OF", ["Project"]], [["TechnologyUse"], "USES_TECHNOLOGY", ["Technology"]]], "projects": [{"id": "kg:jikhaeng", "label": "jikhaeng", "entity_id": "kg:jikhaeng", "ingested_from": "postgres"}, {"id": "kg:secause", "label": "secause", "entity_id": "kg:secause", "ingested_from": "postgres"}, {"id": "kg:teamficial", "label": "teamficial", "entity_id": "kg:teamficial", "ingested_from": "postgres"}], "status_counts": {"implemented": 22, "NULL": 16, "proposed": 3}}
few-shot (논리적 1-hop은 TechnologyUse 중간 노드 때문에 실제로는 관계 2개):
[{"question": "SeCause가 쓴 기술은?", "cypher": "MATCH (u:TechnologyUse)-[:PART_OF]->(p:Project {id:'kg:secause'}), (u)-[:USES_TECHNOLOGY]->(t:Technology) RETURN DISTINCT t.id AS technology_id, t.label AS technology ORDER BY technology_id"}, {"question": "Docker를 쓴 프로젝트는?", "cypher": "MATCH (t:Technology {id:'kg:tech-docker'})<-[:USES_TECHNOLOGY]-(u:TechnologyUse)-[:PART_OF]->(p:Project) RETURN DISTINCT p.id AS project_id, p.label AS project ORDER BY project_id"}, {"question": "SeCause에서 구현한 기술 수는?", "cypher": "MATCH (u:TechnologyUse)-[:PART_OF]->(p:Project {id:'kg:secause'}), (u)-[:USES_TECHNOLOGY]->(t:Technology) WHERE u.status='implemented' RETURN count(DISTINCT t.id) AS technology_count"}]
```
