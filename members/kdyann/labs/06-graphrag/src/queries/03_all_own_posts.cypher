// W6 전체 내 게시물: 관심 분야 밖의 야구 주제도 포함한다.
// :param profile_id => 'junyounge';
MATCH (profile:Profile {id: $profile_id})
OPTIONAL MATCH published_path = (profile)-[:PUBLISHED]->(:OwnPost)
WITH profile, collect(DISTINCT published_path) AS published_paths
OPTIONAL MATCH topic_path = (profile)-[:PUBLISHED]->(:OwnPost)-[:COVERS_TOPIC]->(:Topic)
WITH published_paths, collect(DISTINCT topic_path) AS topic_paths
WITH published_paths + topic_paths AS paths
UNWIND paths AS path
RETURN path LIMIT 200;
