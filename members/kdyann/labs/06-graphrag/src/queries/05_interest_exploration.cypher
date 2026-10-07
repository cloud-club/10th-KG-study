// Neo4j Browser에서 관심 분야 → 아직 내 글에 없는 주제 → 참고 글을 Graph로 본다.
// :param as_of => '2026-10-06T23:59:59Z';  // 조회 시점 UTC
// :param profile_id => 'junyounge';
MATCH path = (profile:Profile {id: $profile_id})-[:INTERESTED_IN]->
  (area:InterestArea)<-[:IN_AREA {profile_id: $profile_id}]-(topic:Topic)
  <-[ref_rel:COVERS_TOPIC]-(ref:ReferencePost)
WHERE NOT EXISTS {
    MATCH (own:OwnPost)-[:COVERS_TOPIC]->(topic)
  }
  AND ref.published_at IS NOT NULL
  AND datetime(ref.published_at) >= datetime($as_of) - duration({days: 7})
  AND datetime(ref.published_at) <= datetime($as_of)
MATCH (ev:Evidence)-[:SUPPORTS]->(:Assertion {id: ref_rel.source_fact_id})
WHERE ev.source_id = ref.source_id
RETURN path, area.name AS interest_area, topic.name AS new_topic,
       ref.source_id AS reference_post_id, ev.quote AS source_evidence
ORDER BY ref.published_at DESC LIMIT 20;
