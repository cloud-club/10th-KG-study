// Neo4j Browser에서 실행: 작업 공간·계정·앱 프로젝트와 분석 설계 전체.
// 실측 수치·실제 도구 권한·예약 실행은 이 설계에 포함되지 않는다.
MATCH (n:AnalyticsDesign)
WHERE n.id STARTS WITH 'analytics-design:'
OPTIONAL MATCH (n)-[r]-(m)
RETURN n, r, m;
