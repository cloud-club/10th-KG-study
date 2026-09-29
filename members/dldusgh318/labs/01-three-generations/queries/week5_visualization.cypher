// 발표 메인: SeCause의 큐 기술이 다른 프로젝트로 이어지는 경로
MATCH (secause:Project {entity_id: 'kg:secause'})
      <-[source_part:PART_OF]-(source_use:TechnologyUse)
      -[source_tech:USES_TECHNOLOGY]->(redis:Technology {entity_id: 'kg:tech-redis'})
      <-[other_tech:USES_TECHNOLOGY]-(other_use:TechnologyUse)
      -[other_part:PART_OF]->(other_project:Project)
WHERE coalesce(source_use.purpose, '') CONTAINS '큐'
  AND other_project.entity_id <> secause.entity_id
RETURN secause,
       source_part,
       source_use,
       source_tech,
       redis,
       other_tech,
       other_use,
       other_part,
       other_project;

// 예비 화면: Redis 전체 사용례 서브그래프
MATCH (redis:Technology {entity_id: 'kg:tech-redis'})
      <-[uses:USES_TECHNOLOGY]-(use:TechnologyUse)
      -[part:PART_OF]->(project:Project)
RETURN redis, uses, use, part, project
LIMIT 40;

// 너무 복잡할 때: 프로젝트당 Redis 사용례를 최대 2개만 표시
MATCH (redis:Technology {entity_id: 'kg:tech-redis'})
      <-[uses:USES_TECHNOLOGY]-(use:TechnologyUse)
      -[part:PART_OF]->(project:Project)
WITH redis, project, use, uses, part
ORDER BY project.label, use.status, use.purpose
WITH redis, project, collect({use: use, uses: uses, part: part})[0..2] AS examples
UNWIND examples AS example
RETURN redis, project, example.use, example.uses, example.part;

// 시각화 전 중복 노드 진단: 결과가 있으면 적재 MERGE 키부터 수정
MATCH (node)
WHERE node.entity_id IS NOT NULL
WITH node.entity_id AS entity_id, labels(node) AS node_labels, count(*) AS count
WHERE count > 1
RETURN entity_id, node_labels, count
ORDER BY count DESC, entity_id;
