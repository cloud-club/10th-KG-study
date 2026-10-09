// W6 관심 분야 중심 개요: 다섯 분야와 각 주제의 게시물 경로를 표시한다.
// :param as_of => '2026-10-06T23:59:59Z';  // 조회 기준 UTC
// :param profile_id => 'junyounge';
MATCH (profile:Profile {id: $profile_id})
OPTIONAL MATCH area_path = (profile)-[:INTERESTED_IN]->(:InterestArea)
WITH profile, collect(DISTINCT area_path) AS area_paths
OPTIONAL MATCH curated_path = (profile)-[:INTERESTED_IN]->(:InterestArea)
  <-[:IN_AREA {profile_id: $profile_id}]-(:Topic)
WITH profile, area_paths, collect(DISTINCT curated_path) AS curated_paths
OPTIONAL MATCH own_path = (profile)-[:INTERESTED_IN]->(:InterestArea)
  <-[:IN_AREA {profile_id: $profile_id}]-(own_topic:Topic)<-[:COVERS_TOPIC]-(:OwnPost)
WHERE own_topic.name <> '야구'
WITH profile, area_paths, curated_paths, collect(DISTINCT own_path) AS own_paths
OPTIONAL MATCH baseball_path = (profile)-[:INTERESTED_IN]->(:InterestArea {name: '야구'})
  <-[:IN_AREA {profile_id: $profile_id}]-(:Topic {name: '야구'})
  <-[:COVERS_TOPIC]-(baseball_post:OwnPost)
WITH profile, area_paths, curated_paths, own_paths, baseball_path, baseball_post
ORDER BY baseball_post.published_at DESC, baseball_post.source_id
WITH profile, area_paths, curated_paths, own_paths,
     collect(DISTINCT baseball_path)[0..3] AS baseball_paths
OPTIONAL MATCH reference_path = (profile)-[:INTERESTED_IN]->(:InterestArea)
  <-[:IN_AREA {profile_id: $profile_id}]-(:Topic)<-[:COVERS_TOPIC]-(ref:ReferencePost)
WHERE ref.published_at IS NOT NULL
  AND datetime(ref.published_at) >= datetime($as_of) - duration({days: 7})
  AND datetime(ref.published_at) <= datetime($as_of)
WITH area_paths, curated_paths, own_paths, baseball_paths,
     collect(DISTINCT reference_path) AS reference_paths
WITH area_paths + curated_paths + own_paths + baseball_paths + reference_paths AS paths
UNWIND paths AS path
RETURN path LIMIT 120;
