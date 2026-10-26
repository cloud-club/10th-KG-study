// 기존 그래프와 분석 설계 전체: 고립된 노드도 포함한다.
MATCH (n)
OPTIONAL MATCH (n)-[r]->(m)
RETURN n, r, m;
