// Public synthetic example only: StudyW5 nodes from W5 pipeline.py.
// Run each query separately. The sample contains one file/run/case result.
// Explicit file-to-run links; not all historical runs for the release.
MATCH (f:StudyW5 {kind:'installation_artifact'})-[:FOR_RELEASE]->
      (release:StudyW5 {label:'v0.1.0'})
MATCH (f)-[:HAS_TEST_RUN]->(run:StudyW5 {kind:'test_run'})
OPTIONAL MATCH (cr:StudyW5 {kind:'test_case_run'})-[:PART_OF_RUN]->(run)
RETURN count(DISTINCT f) AS files,
       count(DISTINCT run) AS test_runs,
       count(DISTINCT CASE WHEN cr.result='Passed' THEN cr END) AS passed,
       count(DISTINCT CASE WHEN cr.result='Failed' THEN cr END) AS failed;

// Per-run details; missing case definitions stay visible as null.
MATCH (f:StudyW5)-[:FOR_RELEASE]->(:StudyW5 {label:'v0.1.0'})
MATCH (f)-[:HAS_TEST_RUN]->(run:StudyW5 {kind:'test_run'})
MATCH (cr:StudyW5 {kind:'test_case_run'})-[:PART_OF_RUN]->(run)
OPTIONAL MATCH (tc:StudyW5 {kind:'test_case'})-[:HAS_EXECUTION]->(cr)
RETURN DISTINCT f.id AS file_id,run.id AS test_run_id,
       run.run_attempt AS attempt,tc.label AS case_name,
       cr.id AS case_run_id,cr.result AS result
ORDER BY attempt,case_run_id;
