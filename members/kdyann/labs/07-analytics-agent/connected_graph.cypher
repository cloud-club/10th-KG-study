// 화면에서만 연결 없는 Post를 숨긴다. 원본 노드와 자료는 유지한다.
MATCH (n)
WHERE NOT (n:Post AND NOT EXISTS { MATCH (n)--() })
OPTIONAL MATCH (n)-[r]->(m)
RETURN n, r, m;
