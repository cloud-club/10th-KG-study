-- 지식그래프를 엔티티/엣지/근거 3개 테이블로 저장한다.
-- 엔티티는 여러 타입(rdf:type)을 가질 수 있어 types를 배열로 둔다(예: git 정리 = Activity + Document).
-- 엣지의 object는 다른 엔티티(object_id)이거나 리터럴 값(object_literal) 둘 중 하나만 채워진다.
-- 근거는 엣지 1개당 0~1개(우리 추출기 기준)지만, 나중에 여러 근거가 붙을 수 있어 별도 테이블로 뺀다.

DROP TABLE IF EXISTS kg_evidence;
DROP TABLE IF EXISTS kg_edges;
DROP TABLE IF EXISTS kg_entities;

CREATE TABLE kg_entities (
    id    text PRIMARY KEY,
    types text[] NOT NULL,
    name  text NOT NULL
);

CREATE TABLE kg_edges (
    id             bigserial PRIMARY KEY,
    subject_id     text NOT NULL REFERENCES kg_entities(id),
    predicate      text NOT NULL,
    object_id      text REFERENCES kg_entities(id),
    object_literal text,
    CHECK ((object_id IS NULL) <> (object_literal IS NULL))
);

CREATE TABLE kg_evidence (
    edge_id bigint NOT NULL REFERENCES kg_edges(id),
    source  text NOT NULL  -- 원본 노션 페이지 상대 경로
);

CREATE INDEX ON kg_edges (subject_id);
CREATE INDEX ON kg_edges (predicate);
CREATE INDEX ON kg_evidence (edge_id);
