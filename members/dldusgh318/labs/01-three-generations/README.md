# 01-three-generations

## 추출 결과 저장

의존성을 설치한 뒤 `extracted.jsonl`을 정규화하고 Postgres에 적재한다. 기본 DSN은
`postgresql://study:study@localhost:5433/study`이며 `POSTGRES_DSN`으로 덮어쓸 수 있다.

```bash
python3 -m pip install -r requirements.txt
python3 src/store_kg.py
```

기본 실행은 다음 파일을 생성한다.

- `output/entity-normalization.jsonl`: LLM 엔티티 ID/라벨과 정규화 결과의 매핑
- `output/entity-normalization-summary.json`: 병합·변경·제외 건수 요약
- `output/my-kg.ttl`: Turtle 직렬화
- `output/my-kg.jsonld`: JSON-LD 직렬화

적재와 내보내기를 따로 실행할 수도 있다.

```bash
python3 src/store_kg.py --mode load --extraction-run v0-2026-09-28
python3 src/store_kg.py --mode export
```

RDF에는 evidence와 chunk_id를 넣지 않으며, RDF reification에 따른 파일 팽창을 피하기 위해 근거는 Postgres와 Neo4j에만 보관한다.
