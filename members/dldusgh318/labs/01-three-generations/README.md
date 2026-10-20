# 01-three-generations

문서 청크에서 LLM으로 트리플을 추출하고, Postgres와 Neo4j에 지식 그래프로 저장해
RAG가 놓친 다중 홉 질문을 질의하는 실습이다.

발표와 후속 작업을 위한 실행 현황·검증 결과·문제점은 `WEEK5_HANDOFF.md`에 정리했다.
TechnologyUse 병합 계획 생성·검토·적용·역적용 절차는 `MERGE_USES.md`에 정리했다.

## 실행 순서

모든 명령은 이 디렉터리에서 실행한다.

```bash
cd members/dldusgh318/labs/01-three-generations
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
docker compose up -d pg neo4j
```

### 1. 소수 청크로 추출 확인

```bash
export OPENAI_API_KEY='발급받은 키'
python3 src/extract_triples.py --limit 5
```

`extracted.jsonl`에 이미 성공한 `chunk_id`가 있으면 건너뛴다. 실패 행은 다음 실행에서
제거하고 재시도한다. 전체 추출 전에 반드시 `--limit`으로 빈 결과와 오추출 여부를
먼저 본다.

### 2. 전체 추출

```bash
python3 src/extract_triples.py
```

### 3. 정규화, Postgres 적재, RDF 내보내기

```bash
python3 src/store_kg.py
```

다른 추출 파일을 쓰려면 입력을 명시한다.

```bash
python3 src/store_kg.py --input extracted.review20.jsonl
```

기본 DSN은 `postgresql://study:study@localhost:5433/study`이며 `POSTGRES_DSN`으로
덮어쓸 수 있다. 적재와 RDF 내보내기를 분리할 수도 있다.

```bash
python3 src/store_kg.py --mode load --extraction-run v0-2026-09-28
python3 src/store_kg.py --mode export
```

생성 파일:

- `output/entity-normalization.jsonl`
- `output/entity-normalization-summary.json`
- `output/my-kg.ttl`
- `output/my-kg.jsonld`

### 4. Neo4j 적재

Postgres에 정규화된 그래프를 먼저 적재한 뒤 실행한다.

```bash
python3 src/load_neo4j.py --verify-idempotency
```

기본 접속 정보는 다음과 같다.

- Browser: `http://localhost:7474`
- Bolt: `bolt://localhost:7687`
- 사용자: `neo4j`
- 비밀번호: `study-password`

노드는 `id`만으로 `MERGE`하고 `label`, `purpose`, `status`는 `SET`한다. 관계는
청크별 근거를 따로 보존하기 위해 `(subject, predicate, object, chunk_id)`의 SHA-256인
`edge_key`로 `MERGE`한다. `--verify-idempotency`는 같은 배치를 두 번 실행해 두 번째
실행 후에도 노드와 관계 개수가 변하지 않는지 확인한다.

### 5. Neo4j 질의와 시각화

Neo4j 적재가 끝난 뒤 Browser에서 다음 파일의 쿼리를 실행한다.

- `queries/week5.cypher`: X01, X03, 가변 길이 경로, 진단 쿼리
- `queries/week5_visualization.cypher`: Redis 중심 발표용 서브그래프
- `queries/neo4j_validation.cypher`: 라벨·관계별 개수와 중복 의심 노드 검사
- `neo4j/browser-style.grass`: 발표용 노드·관계 스타일

PostgreSQL에서 같은 질문을 실행하는 비교 쿼리는 `queries/week5.sql`에 있다.

### 6. 추출 통계 생성

```bash
python3 src/extraction_stats.py --input extracted.jsonl
```

현재 20개 검수 데이터를 다시 집계하려면 다음과 같이 실행한다.

```bash
python3 src/extraction_stats.py \
  --input extracted.review20.jsonl \
  --extraction-run v0-2026-09-28
```

결과는 `output/extraction-stats.md`와 `output/extraction-stats.json`에 저장된다.

## 스크립트 역할

| 파일 | 역할 |
|---|---|
| `src/extract_triples.py` | 청크별 LLM 호출, 구조화 출력, 트리플 검증, 재시도와 중단 재개 |
| `src/store_kg.py` | 엔티티 정규화, IRI 재생성, Postgres 적재, Turtle·JSON-LD 출력 |
| `src/load_neo4j.py` | 제약조건 생성, `UNWIND` 배치 처리, Postgres → Neo4j 멱등 적재 |
| `src/extraction_stats.py` | JSONL 검증 통계와 DB 엔티티·엣지 통계를 Markdown·JSON으로 출력 |
| `sql/kg_schema.sql` | `entities`, `edges` 테이블과 중복 방지 인덱스 정의 |
| `queries/week5.cypher` | Neo4j용 1-hop, X01, X03, 가변 경로, 근거와 진단 질의 |
| `queries/week5.sql` | 동일 질문의 PostgreSQL self-join·재귀 CTE 구현 |
| `queries/week5_visualization.cypher` | Neo4j Browser 발표 화면용 Redis 서브그래프 |
| `queries/neo4j_validation.cypher` | 노드·관계 수, ID 중복, 유사 라벨, 관계 방향 검증 |

## Neo4j Browser 발표 화면

`queries/week5_visualization.cypher`의 첫 쿼리를 실행한다. 이 쿼리는 SeCause의 큐 사용례,
Redis, Redis를 공유하는 다른 프로젝트만 반환한다.

Browser 결과 상단의 노드 라벨을 클릭하면 라벨별 색상, 크기, 캡션을 바꿀 수 있다.
다음 설정을 권장한다.

| 라벨 | 색상 | 크기 | 캡션 |
|---|---|---:|---|
| `Project` | 파랑 | 55px | `label` |
| `Technology` | 주황 | 70px | `label` |
| `TechnologyUse` | 초록 | 38px | `purpose` |

관계는 `USES_TECHNOLOGY`를 빨강·3px, `PART_OF`를 회색·2px로 둔다. 동일한 설정을
파일로 적용하려면 Browser에서 `:style`을 실행하고
`neo4j/browser-style.grass`를 업로드한다. 초기화는 `:style reset`이다.

캡처할 때는 Redis를 중앙에 고정하고 SeCause를 왼쪽, 직행과 TEAMFICIAL을 오른쪽에
배치한다. `TechnologyUse`는 프로젝트와 Redis 사이에 남겨 목적 캡션이 보이게 한다.
사이드바와 테이블 결과를 접고, 관계 화살표와 모든 캡션이 보이는 수준까지만 확대한다.
전체 그래프나 노드 확장 기능은 사용하지 않는다. 16:9 슬라이드에서는 가로 방향으로
경로가 흐르게 놓는 구도가 가장 읽기 쉽다.

## 설계 판단

### 1. 술어를 5종으로 제한한 이유

작은 문서 집합에서 술어를 자유 생성하면 `uses`, `adopts`, `builtWith`처럼 의미가 같은
관계가 분산되고 LLM의 환각도 늘어난다. X01과 X03에 필요한 관계만 5종으로 고정하면
검증 규칙과 질의 경로를 단순하게 유지하면서 두 역량 질문을 모두 답할 수 있다.

### 2. TechnologyUse 중간 노드를 만든 이유

`Project-uses-Technology`만으로는 같은 기술을 서로 다른 목적이나 상태로 사용한 사실을
구분할 수 없다. `TechnologyUse`를 두면 직행의 Redis 테스트 결과 저장은
`implemented`, 통근 시간 캐시는 `proposed`처럼 프로젝트·기술 조합에 목적과 상태를
독립적으로 붙일 수 있다.

### 3. Turtle에서 evidence를 제외한 이유

RDF 트리플 자체에는 `evidence`와 `chunk_id`를 바로 붙일 자리가 없다. 이를 RDF
reification으로 표현하면 한 사실이 여러 보조 트리플로 늘어 파일과 질의가 불필요하게
커진다. 따라서 Turtle과 JSON-LD는 의미 그래프만 담고, 검증 근거는 Postgres와
Neo4j 관계 속성에 보관한다.

## 통계 해석

- 총 추출 트리플 수: 검증 통과 트리플과 rejected를 합친 LLM 후보 수
- 통과율: `검증 통과 / 총 추출 후보`
- evidence_not_found 비율(환각률): `evidence_not_found / 총 추출 후보`
- DB 술어 수가 JSONL 통과 수보다 작을 수 있다. 정규화 병합, 같은 청크 중복 제거,
  관계가 부족한 `TechnologyUse` 제외가 적재 전에 추가로 일어나기 때문이다.
