// 07-repo-graphrag 시연용 Cypher — Neo4j Browser (http://localhost:7474, neo4j / kgstudy2026) 에 하나씩 붙여 넣는다.
// 그래프를 크게 보려면 Browser 설정에서 "Initial Node Display" 를 300 이상으로.

// ── 1. 스키마 한눈에 ─────────────────────────────────────────────────
CALL db.schema.visualization();

// ── 2. 우리 스터디 = 멤버 → 문서 → 기법 (구조 층 + MENTIONS) ──────────
// 멤버 한 명이 무엇을 썼고 그 문서들이 어떤 기법을 다뤘나
MATCH (m:Member {id: 'kdyann'})-[:WROTE]->(d:Document)-[:HAS_CHUNK]->(:Chunk)-[:MENTIONS]->(t:Technique)
WITH m, d, t, count(*) AS n WHERE n >= 2
RETURN m, d, t;

// ── 3. 로컬 서치 장면 — RRF 주변의 '측정된' 결과와 함정, 누가 확인했나 ──
MATCH (t:Technique {name: 'RRF'})<-[r:ABOUT|COMPARED_WITH|OCCURS_IN]-(x)<-[:REPORTED|HIT]-(m:Member)
WHERE x:Pitfall OR x.kind = 'measured'
RETURN t, r, x, m;

// RRF 가 단독 검색기에 '졌다'고 추출된 결과 (승패 방향은 추출값 — README 함정 참고)
MATCH (m:Member)-[:REPORTED]->(f:Finding {kind: 'measured'})-[:ABOUT]->(:Technique {name: 'RRF'})
MATCH (f)-[cw:COMPARED_WITH {outcome: 'lose'}]->(o)
RETURN m.id AS 멤버, o.name AS 상대, f.metric AS 지표, f.value AS 값, f.condition AS 조건;

// ── 4. 집계 장면 (Text2Cypher 가 만드는 종류) ─────────────────────────
// 가장 많은 멤버가 '함정'을 기록한 기법
MATCH (m:Member)-[:HIT]->(:Pitfall)-[:OCCURS_IN]->(t)
RETURN t.name AS 기법, count(DISTINCT m) AS 멤버수, collect(DISTINCT m.id) AS 멤버
ORDER BY 멤버수 DESC LIMIT 10;

// 멤버별 직접 측정 결과 수 vs 인용 수 — "정리했다"와 "측정했다"의 구분
MATCH (m:Member)-[:REPORTED]->(f:Finding)
RETURN m.id AS 멤버, sum(CASE f.kind WHEN 'measured' THEN 1 ELSE 0 END) AS 측정,
       sum(CASE f.kind WHEN 'cited' THEN 1 ELSE 0 END) AS 인용
ORDER BY 측정 DESC;

// ── 5. 글로벌 서치 장면 — Leiden 커뮤니티 = 스터디가 스스로 찾은 주제 묶음 ──
MATCH (c:Community) RETURN c.id, c.title, c.size, c.members ORDER BY c.size DESC;

// 커뮤니티 하나를 펼쳐 보기 (기법·도구만)
MATCH (e)-[:IN_COMMUNITY]->(c:Community {id: 'C5'}) WHERE e:Technique OR e:Tool
OPTIONAL MATCH (e)<-[:ABOUT|OCCURS_IN]-(x)-[:IN_COMMUNITY]->(c)
RETURN c, e, x LIMIT 150;

// ── 6. v3 — 위키 층 (v1·v2 는 읽지 않는다) ────────────────────────────
// 모순이 표시된 위키 페이지와 얽힌 멤버
MATCH (x:Contradiction)-[:IN_PAGE]->(w:WikiPage) OPTIONAL MATCH (x)-[:INVOLVES]->(m:Member)
RETURN w, x, m;

// 위키 페이지가 어느 멤버 문서를 출처로 삼았나 (위키 = 소재를 미리 합성한 인덱스)
MATCH (w:WikiPage {name: 'GraphRAG'})-[:CITES]->(d:Document)<-[:WROTE]-(m:Member)
RETURN w, d, m;

// ── 7. 정직성 — 근거로 돌아가기 ───────────────────────────────────────
// 모든 Finding 은 원문 청크로 돌아간다. evidence 는 원문에 실제로 있는 문자열만 채택했다.
MATCH (f:Finding)-[:EVIDENCED_BY]->(c:Chunk)<-[:HAS_CHUNK]-(d:Document)
WHERE f.claim CONTAINS 'Text2Cypher'
RETURN f.claim, f.evidence, d.path LIMIT 10;
