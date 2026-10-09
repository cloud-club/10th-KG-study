// 분류표에 없는 세부 Topic이 같은 참고 글의 상위 관심 Topic으로 연결되는 경로.
// :param as_of => '2026-10-06T23:59:59Z';
// :param profile_id => 'junyounge';
MATCH interest_path = (profile:Profile {id: $profile_id})-[:INTERESTED_IN]->(area:InterestArea)
MATCH topic_path = (broad:Topic)<-[broad_rel:COVERS_TOPIC]-(ref:ReferencePost)
  -[detail_rel:COVERS_TOPIC]->(detail:Topic)
WHERE broad.name = area.name AND detail <> broad
  AND NOT EXISTS { MATCH (detail)-[:IN_AREA {profile_id: $profile_id}]->(:InterestArea) }
  AND ref.published_at IS NOT NULL
  AND datetime(ref.published_at) >= datetime($as_of) - duration({days: 7})
  AND datetime(ref.published_at) <= datetime($as_of)
MATCH (broad_ev:Evidence)-[:SUPPORTS]->(:Assertion {id: broad_rel.source_fact_id})
MATCH (detail_ev:Evidence)-[:SUPPORTS]->(:Assertion {id: detail_rel.source_fact_id})
WHERE broad_ev.source_id = ref.source_id AND detail_ev.source_id = ref.source_id
RETURN interest_path, topic_path, broad_ev.quote AS broad_evidence,
       detail_ev.quote AS detail_evidence
ORDER BY ref.published_at DESC LIMIT 20;
