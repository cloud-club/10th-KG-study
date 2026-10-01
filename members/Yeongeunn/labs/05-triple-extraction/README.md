# Notion 관계 추출과 지식 그래프 적재

회원탈퇴 관련 문서에서 관계와 근거를 추출하고, 원문 대조로 보완한 작은 그래프를 Postgres·Turtle·Neo4j에 같은 내용으로 저장했다.

## 실행 흐름

```text
기존 청크 → Gemini 관계 후보 JSON → 근거·조건 대조 → 검토한 그래프 초안
                                                     ├─ PostgreSQL 엔티티·관계·근거
                                                     ├─ Turtle / JSON-LD
                                                     └─ Neo4j → Cypher → 브라우저
```

## 추출과 검토

| 실행 | 입력 | 예시·문맥 | 결과 |
|---|---:|---|---:|
| 첫 추출 | 청크 4개 | 긍정 예시 1개, 본문 | 후보 7개 |
| 문맥 보강 추출 | 청크 5개 | 제공 서비스 분류, 긍정·부정 예시 | 후보 5개 |

두 실행 모두 클래스·술어·근거 문자열 검사에서는 탈락 후보가 없었다. 첫 실행은 API 경로만 인용한 채 제공 서비스를 단정한 관계가 있었다. 문맥을 보강한 실행에서는 제공 서비스와 엔드포인트가 함께 인용됐지만 정책 관계가 누락됐다. 후보 수가 줄었다고 정확도가 높아진 것은 아니다. 입력과 예시도 함께 바뀌었으므로 단일 요인의 개선 효과로 해석하지 않는다.

그래프는 첫 추출의 후보를 출발점으로 원문 대조·문맥 보완·정책 분리·관계 추가를 거친 **AI 보조 검토 초안**이다. LLM이 20개를 자동으로 정확히 추출했다고 주장하지 않는다. 작성자의 최종 검토는 남아 있다.

- API 제공 주체는 본문 경로만으로 판단하지 않고 문서의 서비스 소속과 함께 확인.
- 포괄적인 차단 정책을 서로 다른 상태 조건 3개로 분리.
- API·업무 기능·정책·거래 유형을 분리해 조건과 관계 방향 보존.
- 미결제 조회 API가 확인 정책에 연결된다는 해석과, 세부 상태값을 모두 구현했다는 주장은 구분.
- 제공 API 목록으로 실제 호출 엔드포인트를 단정하지 않음.

## 저장 결과

| 저장소·형식 | 확인 결과 |
|---|---|
| PostgreSQL | 엔티티 15개, 관계 20개, 근거 29건 |
| Neo4j | 노드 15개, 관계 20개 |
| Turtle / JSON-LD | 사실·타입·라벨·근거 메타데이터를 포함한 RDF 트리플 373개 |
| 재적재 | 동일 스냅샷을 두 번 적재해도 건수 유지 |
| 직렬화 검증 | 두 파일을 다시 파싱한 그래프가 원래 RDF 그래프와 동형 |

관계 20개와 RDF 트리플 373개는 다른 단위다. RDF에는 관계뿐 아니라 클래스, 이름, 근거, 조건, 검토 상태도 트리플로 들어간다. 기존 `schemas/erumpay-ontology-v0.ttl`은 **정의**, 이번 `facts.ttl`은 **그 정의를 사용한 사실과 근거**다.

관계마다 근거 필드·청크 ID·인용 구간·문자 위치·해시를 저장한다. 제공 주체의 근거처럼 문서 분류가 필요한 경우는 본문 인용과 분류 경로를 구분해 보관한다. Neo4j는 실습 전용 라벨과 스냅샷 ID를 사용해 다른 멤버의 노드와 섞이지 않게 했다.

## Cypher 조회

| 질의 | 결과 건수 |
|---|---:|
| 탈퇴 API의 서비스 호출 1-hop | 2 |
| 탈퇴 API에서 `1..3` 경로 | 19 |
| 결제 서비스와 확인 정책에 연결된 API 후보 | 1 |
| 카드 서비스가 제공하는 API와 업무 기능 | 1 |
| 탈퇴 차단 정책의 조건 | 3 |

카드 관련 3-hop 질의는 Postgres JOIN으로도 실행해 같은 행이 나오는지 확인했다. 재귀 CTE나 Fuseki는 이번 실습 범위에 포함하지 않았다.

Neo4j Browser에서 현재 그래프를 볼 때:

```cypher
MATCH p=(n:KGStudyYeongeunn)-[r]->(m:KGStudyYeongeunn)
WHERE n.run = $run AND m.run = $run
RETURN p;
```

`$run`은 로컬 `graph-run.json`의 `run` 값이다. Browser에서 `:param run => '해당 값'`으로 설정한다.

1-hop과 가변 길이 경로:

```cypher
MATCH (a:KGStudyYeongeunn {run:$run,id:'withdraw-api'})
      -[r:CALLS_SERVICE]->(s:KGStudyYeongeunn {run:$run})
RETURN a, r, s;

MATCH p=(a:KGStudyYeongeunn {run:$run,id:'withdraw-api'})-[*1..3]->(b)
WHERE all(n IN nodes(p) WHERE n.run=$run)
RETURN p;
```

노드 ID는 실습에서 부여한 식별자다. 서비스→제공 API라는 경로는 API의 **소속**을 보여준다. 호출 서비스가 제공하는 후보 API를 찾을 수 있지만 실제 호출 엔드포인트의 확정에는 추가 근거가 필요하다.

## 기존 RAG와 연결

[검색 비교 실험](../04-hybrid-evaluation/README.md)의 다중 홉 질문 두 개를 그래프 질의로도 확인했다. 텍스트 RAG가 일부만 답한 질문에 대해 구조화된 관계와 엔드포인트를 연결할 수 있었다. 반대로 RRF가 잘 답한 질문도 있으므로 ‘다중 홉은 RAG로 불가능하다’고 해석하지 않는다.

그래프는 해당 질문에 맞춰 소수 문서를 검토해 만든 반면, 검색은 전체 청크를 대상으로 한다. 이는 동작 비교이며 GraphRAG의 일반적인 우월성을 입증하는 공정한 대규모 벤치마크는 아니다. 그래프 리트리버를 LLM 답변 루프에 연결하는 작업은 W6 범위다.

## 실행

저장소 루트에서 [검색 실험의 환경 설치](../04-hybrid-evaluation/README.md)를 마친 뒤 실행한다.

```bash
docker compose up -d postgres elasticsearch neo4j
```

### 저장된 결과 확인

```bash
python -m json.tool data/Yeongeunn/kg-v0/run.json
python -m json.tool data/Yeongeunn/kg-v0/context-v2/run.json
python -m json.tool data/Yeongeunn/kg-v0/graph-run.json
```

### 새 추출

```bash
python members/Yeongeunn/labs/05-triple-extraction/src/triples.py prepare --run-name context-v2
python members/Yeongeunn/labs/05-triple-extraction/src/triples.py extract --run-name context-v2
```

`prepare`는 제목 기준으로 문서를 선택하고 분류 문맥을 추가한다. `extract`는 준비한 텍스트를 Gemini로 보내므로 새 호출이 발생한다. `--run-name`으로 실행별 폴더를 나누며 같은 이름을 재사용하면 해당 폴더의 입력·후보를 덮어쓴다. 기존 첫 실행은 `kg-v0/` 바로 아래에 보존했다.

첫 실행과 현재 코드의 입력 구성이 다르다. 현재 코드는 문맥 보강 실행을 재현하며 첫 실행과 동일한 7개 출력을 보장하지 않는다. 숫자·키의 기본 마스킹은 완전한 개인정보 검출기가 아니다.

### 검토 결과 적재와 조회

```bash
python members/Yeongeunn/labs/05-triple-extraction/src/graph_lab.py load
python members/Yeongeunn/labs/05-triple-extraction/src/graph_lab.py query
python members/Yeongeunn/labs/05-triple-extraction/src/graph_lab.py browser
```

`load`는 로컬 `graph-reviewed.json`을 읽고 근거 해시·문자 구간·클래스 조합을 검증한다. 조건·방향의 의미를 자동 판정하는 것은 아니다. 해당 검토 파일은 원문 근거를 포함해 Git에서 제외한다. 새 데이터에서는 후보를 검토해 같은 구조의 파일을 작성해야 한다.

Postgres는 `yeongeunn_kg.entities/edges/evidence`, Neo4j는 `KGStudyYeongeunn` 라벨과 클래스 라벨을 사용한다. 동일 스냅샷은 upsert·MERGE로 재실행해도 중복을 만들지 않고, 다른 검토 내용은 다른 스냅샷 ID로 보존한다.

### 브라우저에서 보기

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory data/Yeongeunn/kg-v0
```

[로컬 그래프](http://127.0.0.1:8765/graph.html)에서 노드를 드래그하고 화살표를 클릭해 조건과 근거를 확인한다. 이 화면은 Neo4j에서 조회한 데이터를 표시한다. 재적재 후 `browser`를 실행하고 화면을 새로고침하면 갱신된다. [Neo4j Browser](http://localhost:7474/browser/)에서도 직접 Cypher를 실행할 수 있다.

## 주요 로컬 파일

- `candidates.json`, `reviewed.json`: 첫 실행 후보와 초기 검토 기록
- `context-v2/`: 문맥·예시를 추가한 별도 추출 실행
- `graph-reviewed.json`: 적재한 엔티티·관계·근거와 검토 이력
- `facts.ttl`, `facts.jsonld`: 실제 그래프 내보내기
- `graph-run.json`: 적재·재실행·파싱·질의 검증 집계
- `queries.json`: 실행한 Cypher와 결과
- `graph.html`: Neo4j 조회 결과를 표시하는 로컬 화면

## 참고

- [미니 온톨로지](../../schemas/erumpay-ontology-v0.ttl)
- [Gemini 구조화 출력](https://ai.google.dev/gemini-api/docs/structured-output)
- [Neo4j MERGE](https://neo4j.com/docs/cypher-manual/5/clauses/merge/)
