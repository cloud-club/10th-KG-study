// 1. 1-hop: 졸전 활동에 속한 문서는?
MATCH (a:Activity {name: "졸전"})-[:HAS_DOCUMENT]->(d:Document)
RETURN d.name AS document
LIMIT 10;

// 2. 가변 길이 경로(1..3): KB 국민은행과 1~3홉 이내로 연결된 모든 노드
MATCH (org:Organization {name: "KB 국민은행"})<-[*1..3]-(n)
RETURN DISTINCT labels(n) AS types, n.name AS name;

// 3. "아하" — W3 RAG가 놓쳤던 다중 홉을 그래프로 답하기
//    (원래 질문: "역량검사에서 일정 지연 대응을 언급한 이 회사는 어떤 인재상을 갖고 있나?"
//     RAG는 "역량검사" 청크와 "KB 국민은행" 청크를 각각 검색해서 하나로 못 이었다.
//     그래프에서는 Organization -[RELATED_TO_ORGANIZATION]- Activity -[HAS_DOCUMENT]- Document
//     경로 하나로 바로 연결된다 — 검색이 아니라 순회라서 놓칠 수가 없다.)
MATCH (org:Organization {name: "KB 국민은행"})<-[:RELATED_TO_ORGANIZATION]-(a:Activity)-[:HAS_DOCUMENT]->(d:Document)
RETURN a.name AS activity, d.name AS document, d.about AS topic, a.status AS status;

// 4. 같은 질문을 조직 이름을 몰라도 풀 수 있는지: "이 활동과 관련된 조직은?" (역방향 1-hop)
MATCH (a:Activity {name: "Naver 지원 준비"})-[:RELATED_TO_ORGANIZATION]->(org:Organization)
RETURN org.name AS organization;

// 5. 진행 상태(status)가 "In progress"인 활동과, 그 활동이 속한 기간
MATCH (a:Activity {status: "In progress"})
OPTIONAL MATCH (a)-[:OCCURS_IN_PERIOD]->(p:Period)
RETURN a.name AS activity, collect(p.name) AS periods;
