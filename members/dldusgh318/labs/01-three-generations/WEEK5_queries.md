# 5주차 그래프 질의: Cypher와 PostgreSQL 비교

실행 가능한 전체 쿼리는 다음 두 파일에 있다.

- `queries/week5.cypher`: Neo4j Browser에서 실행
- `queries/week5.sql`: PostgreSQL에서 실행

## Neo4j 데이터 모델 전제

```text
(TechnologyUse)-[:PART_OF]->(Project)
(TechnologyUse)-[:USES_TECHNOLOGY]->(Technology)
(TechnologyUse)-[:REPLACES]->(TechnologyUse)
```

`TechnologyUse` 노드는 `entity_id`, `label`, `purpose`, `status` 속성을 가진다.
관계는 `evidence`, `chunk_id`, `confidence`, `extraction_run` 속성을 가진다.
같은 두 노드 사이에도 근거 청크가 다르면 관계를 별도로 보존해야 한다.

## 발표에서 볼 차이

| 질문 | Cypher의 핵심 | PostgreSQL의 핵심 |
|---|---|---|
| 프로젝트 → 기술 | 경로 한 줄 | `entities`와 `edges`를 네 번 조인 |
| X01 공유 기술 | 그래프 모양 그대로 4개 관계를 연결 | `edges` 별칭을 네 개 두고 self-join |
| X03 상태 비교 | 두 `TechnologyUse`의 속성 조건 | 제안/구현 사용례를 각각 조인 |
| REPLACES 연쇄 | `[:REPLACES*1..3]` | 순환 방지 배열을 둔 재귀 CTE |
| 근거 포함 X01 | 경로 관계를 변수로 받아 속성 반환 | 근거 집계 CTE와 본 질의를 다시 조인 |

주석과 빈 줄을 제외한 현재 쿼리 줄 수는 다음과 같다.

| 쿼리 | Cypher | PostgreSQL |
|---|---:|---:|
| 6-1-a 프로젝트 → 기술 | 10 | 17 |
| 6-1-b 기술 → 프로젝트 | 10 | 17 |
| 6-2 X01 | 17 | 33 |
| 6-3 X03 | 16 | 35 |
| 6-4-a REPLACES 연쇄 | 7 | 26 |
| 6-4-b 공유 기술 경로 | 11 | 41 |
| 6-5 X01 + 근거 | 35 | 51 |

X01의 “작업 큐”는 현재 적재 데이터의 목적 문자열 `큐 기반 비동기 처리`와 맞추기
위해 `purpose CONTAINS '큐'`로 찾는다. `CONTAINS '작업 큐'`로 제한하면 실제 표현이
달라 0건이 될 수 있다.

## 0건일 때 확인 순서

1. 관계 타입별 건수를 확인한다.
2. `TechnologyUse → Project`, `TechnologyUse → Technology` 방향인지 확인한다.
3. SeCause 사용례의 실제 `purpose`와 `status`를 확인한다.
4. `entity_id` 중복을 확인한다.
5. X01 중간 기술이 다른 프로젝트까지 연결되는지 확인한다.

각 단계의 Cypher와 PostgreSQL 진단 쿼리는 두 실행 파일 마지막에 들어 있다.

현재 샘플에 `REPLACES`가 적다면 발표에서는 공유 기술 기반 프로젝트 네트워크를
가변 길이 예제로 쓰는 편이 낫다. 프로젝트 간 한 단계는
`Project-TechnologyUse-Technology-TechnologyUse-Project`의 관계 4개이며,
Cypher는 `*4..8`, PostgreSQL은 최대 2단계 재귀 CTE로 같은 범위를 탐색한다.

## 현재 PostgreSQL 데이터에서의 검증 결과

- X01: 공유 기술은 Redis이며 다른 프로젝트는 `jikhaeng`, `teamficial`이다.
- X01: 다른 프로젝트의 개별 사용례까지 펼치면 8행이다.
- X03: proposed/implemented 조건을 만족하는 서로 다른 사용례 조합이 6개다.
- `replaces` 엣지는 0개이므로 6-4-a는 정상적으로 0행을 반환한다.
- `queries/week5.sql` 전체를 `ON_ERROR_STOP`으로 실행해 모든 SQL의 문법과 실행을 확인했다.
