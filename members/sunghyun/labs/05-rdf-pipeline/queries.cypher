// 1-hop
MATCH (t:StudyW5:Task)-[:HAS_ISSUE]->(i) RETURN t.id,i.id;
// 1..3-hop; the full build/test/release flow can require more hops.
MATCH p=(t:StudyW5:Task)-[:HAS_ISSUE|HAS_VERIFICATION|HAS_EXECUTION*1..3]->(n) RETURN p;
// One selected build, grouped by Test Run attempt and case result.
MATCH (f:StudyW5 {id:'file:1'})-[:HAS_TEST_RUN]->(run)<-[:PART_OF_RUN]-(cr)
MATCH (tc)-[:HAS_EXECUTION]->(cr)
RETURN run.id,run.run_attempt,tc.label,cr.result ORDER BY run.run_attempt;
// A task without a test definition must be checked via Issue.
MATCH (t:StudyW5:Task)
WHERE NOT EXISTS {(t)-[:HAS_ISSUE]->()-[:HAS_VERIFICATION]->(:StudyW5 {kind:'test_case'})}
RETURN t.id;
