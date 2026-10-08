# 05. RDF 파이프라인 — 추출 후보·근거·저장·내보내기

관련 노트: [5주차 학습 기록](../../notes/05-rdf-ontology-pipeline.md).

회사 플랫폼에서 실행한 로직을 작은 합성 데이터로 옮겼다. 플랫폼 API 호출·사내 원문·접속 정보는 포함하지 않는다. 예제는 5개 클래스와 8개 관계, 8개 노드·8개 트리플이다. `approved`는 예제의 검토 표시이며 실제 사람 승인 절차를 대신하지 않는다.

## 실행

Python 3.10 이상에서 이 폴더로 이동한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/pipeline.py
```

`outputs/graph.ttl`, `graph.jsonld`, `graph.json`을 생성하고 두 RDF 파일이 동형인지 검사한다. 예상 출력은 `nodes:8`, `edges:8`, `rdf_roundtrip:pass`다.

## LLM 추출 후보 확인

Ollama에 `qwen2.5:7b`가 준비되어 있어야 한다.

```bash
python src/extract.py
```

닫힌 JSON Schema와 few-shot으로 후보를 추출하고 원문 부분 문자열을 검사한다. 후보는 `outputs/pending-triples.json`에 `approved:false`로 저장한다. 자동 적재하지 않는다. 의미·방향을 검토한 뒤 `sample.json`의 검토된 트리플 구조로 반영해야 한다.

## 선택: DB 적재

기존 Postgres와 Neo4j에 접속할 환경 변수를 별도로 설정한다. 비밀번호는 저장소에 넣지 않는다.

- `POSTGRES_DSN`: 접속 DSN.
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`: Neo4j 접속 값.
- `NEO4J_DATABASE`: 선택, 기본 `neo4j`.

```bash
python src/pipeline.py --postgres --neo4j
```

Postgres `kg_study_w5`에 entities·edges·evidence를, Neo4j `StudyW5` 라벨에 노드·관계를 적재한다. 고정 ID와 `ON CONFLICT`/`MERGE`를 사용한다. 같은 입력을 두 번 적재하고 개수가 증가하지 않는지 확인한다. 삭제·변경 동기화는 포함하지 않는다.

`queries.cypher`를 Neo4j Browser에서 실행하면 1-hop, 1..3-hop, 빌드 기준 테스트 결과를 확인할 수 있다. 별도의 제품 UI는 공개 코드 범위에 포함하지 않았다.

## 파일과 검증 범위

- `src/extract.py`: LLM JSON 추출·근거 검사, 후보까지만 저장.
- `src/pipeline.py`: 스키마·근거·승인 검사, RDF 직렬화, 선택적 DB 적재.
- `sample.json`: 합성 노드·트리플·원문.
- `queries.cypher`: 확인용 질의.

게시 전 예제 RDF 생성과 동형 비교를 실행했다. 공개 코드의 DB 접속 경로와 LLM 후보 추출은 실행 환경에 따라 별도로 확인해야 한다. 노트에 적힌 회사 실습 결과와 이 예제의 개수는 다르다.
