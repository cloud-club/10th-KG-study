// W5 다중 홉 시연: 내 게시물 -> 같은 Topic <- 다른 내/참고 게시물.
// Neo4j Browser 예시(그래프에 해당 주제가 있을 때): :param topic_name => '야구';
// 실제 추출 결과의 Topic 이름으로 바꿔 실행한다. 일치하는 관계가 없으면 0건이다.
MATCH path = (own:W5Entity {entity_type: 'Post', corpus: 'own'})
             -[own_rel:W5_FACT]->(topic:W5Entity {entity_type: 'Topic', name: $topic_name})
             <-[other_rel:W5_FACT]-(other:W5Entity {entity_type: 'Post'})
WHERE own_rel.predicate = 'coversTopic'
  AND other_rel.predicate = 'coversTopic'
  AND other.corpus IN ['own', 'reference']
  AND own.id <> other.id
  AND (other.corpus = 'reference' OR own.id < other.id)
OPTIONAL MATCH (own_evidence:W5Evidence)-[:SUPPORTS]->
               (:W5Assertion {id: own_rel.id})
OPTIONAL MATCH (other_evidence:W5Evidence)-[:SUPPORTS]->
               (:W5Assertion {id: other_rel.id})
RETURN path, topic.name AS shared_topic,
       own.name AS own_post_id, other.name AS other_post_id,
       other.corpus AS other_corpus, other.permalink AS other_url,
       collect(DISTINCT own_evidence.quote) AS own_evidence,
       collect(DISTINCT other_evidence.quote) AS other_evidence
ORDER BY other_corpus, other_post_id LIMIT 50;
