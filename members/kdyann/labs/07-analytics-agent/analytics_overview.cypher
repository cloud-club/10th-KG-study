// 핵심 그림: 작업 공간 → 계정 / 앱 운영 프로젝트 → 분석 에이전트.
MATCH (w:AnalyticsDesign:Workspace {id: 'analytics-design:workspace'})
MATCH (w)-[wp:HAS_PROJECT]->(project:AnalyticsDesign:Project)-[pa:PLANS_ANALYTICS_ASSISTANT]->(a:AnalyticsDesign:AnalystAgent)
OPTIONAL MATCH (w)-[pr:HAS_ACCOUNT]->(p:Profile)
OPTIONAL MATCH (a)-[r]->(n)
RETURN w, wp, project, pa, p, pr, a, r, n;
