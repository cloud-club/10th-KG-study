// Neo4j Browser: :param start_id => 'https://example.org/kdyann/content-graph/v0/post/…';
MATCH path = (start:W5Entity {id: $start_id})-[:W5_FACT*1..3]-(other:W5Entity)
WHERE all(rel IN relationships(path) WHERE rel.predicate IN
      ['expressesConcept', 'coversTopic', 'describesProject', 'describesFeature', 'hasFeature'])
RETURN path LIMIT 50;
