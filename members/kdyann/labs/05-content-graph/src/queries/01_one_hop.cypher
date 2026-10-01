// Neo4j Browser: :param post_id => 'https://example.org/kdyann/content-graph/v0/post/…';
MATCH (post:W5Entity {id: $post_id})-[r:W5_FACT]->(object:W5Entity)
OPTIONAL MATCH (e:W5Evidence)-[:SUPPORTS]->(a:W5Assertion {id: r.id})
RETURN post.name AS post_id, r.predicate AS predicate, object.entity_type AS object_type,
       object.name AS object_name, collect(DISTINCT {source_id: e.source_id, quote: e.quote}) AS evidence
ORDER BY predicate, object_name;
