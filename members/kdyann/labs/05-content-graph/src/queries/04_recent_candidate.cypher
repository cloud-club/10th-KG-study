// 최근 참고 글과 내 글이 동일 Topic 노드로 실제 연결된 후보만 반환한다.
// :param as_of => '2026-09-30T23:59:59Z';  // 실행 시점 UTC
MATCH candidate_path = (own:W5Entity {entity_type: 'Post', corpus: 'own'})-[own_rel:W5_FACT]->
      (topic:W5Entity {entity_type: 'Topic'})<-[ref_rel:W5_FACT]-
      (ref:W5Entity {entity_type: 'Post', corpus: 'reference'})
WHERE own_rel.predicate = 'coversTopic' AND ref_rel.predicate = 'coversTopic'
  AND ref.published_at IS NOT NULL
  AND datetime(ref.published_at) >= datetime($as_of) - duration({days: 7})
  AND datetime(ref.published_at) <= datetime($as_of)
OPTIONAL MATCH (own_ev:W5Evidence)-[:SUPPORTS]->(:W5Assertion {id: own_rel.id})
OPTIONAL MATCH (ref_ev:W5Evidence)-[:SUPPORTS]->(:W5Assertion {id: ref_rel.id})
RETURN candidate_path, own.name AS own_post_id, topic.name AS shared_topic,
       ref.name AS reference_post_id, ref.permalink AS reference_url,
       ref.published_at AS published_at, ref.collected_at AS collected_at,
       ref.selection_score AS selection_score, ref.observed_likes AS observed_likes,
       ref.observed_comments AS observed_comments,
       collect(DISTINCT own_ev.quote) AS own_evidence,
       collect(DISTINCT ref_ev.quote) AS reference_evidence
ORDER BY selection_score DESC, published_at DESC LIMIT 20;
