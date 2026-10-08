"""Generate only: review output before executing against Neo4j."""
import argparse,json
from retriever import chat,BASE
p=argparse.ArgumentParser();p.add_argument('question');args=p.parse_args()
text,usage=chat([{'role':'system','content':'Generate JSON {"answerable":true,"query":"...","reason":"..."}. Read-only Neo4j query, never writes or CALL. All nodes :StudyW5. Task-[:HAS_ISSUE]->Issue-[:HAS_VERIFICATION]->TestCase(kind=test_case)-[:HAS_EXECUTION]->CaseRun(kind=test_case_run)-[:PART_OF_RUN]->TestRun. File-[:HAS_TEST_RUN]->TestRun and File-[:FOR_RELEASE]->Release. Properties: id,label,kind,result,release_version,run_attempt. If asked whether a related commit proves issue completion, answerable=false and empty query. Use LIMIT100 unless aggregation.'},{'role':'user','content':args.question}])
(BASE/'outputs').mkdir(exist_ok=True);(BASE/'outputs'/'generated-cypher.json').write_text(json.dumps({'model_output':text,'usage':usage},ensure_ascii=False,indent=2));print(text)
