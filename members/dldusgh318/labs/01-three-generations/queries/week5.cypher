// Neo4j Browser용 파라미터
:param projectId => 'kg:secause';
:param technologyId => 'kg:tech-redis';

// 6-1-a. 특정 프로젝트가 쓴 기술 전부
MATCH (project:Project {entity_id: $projectId})
      <-[:PART_OF]-(use:TechnologyUse)
      -[:USES_TECHNOLOGY]->(technology:Technology)
RETURN DISTINCT
       technology.entity_id AS technology_id,
       technology.label AS technology,
       use.entity_id AS use_id,
       use.purpose AS purpose,
       use.status AS status
ORDER BY technology, purpose;

// 6-1-b. 특정 기술을 쓴 프로젝트 전부
MATCH (technology:Technology {entity_id: $technologyId})
      <-[:USES_TECHNOLOGY]-(use:TechnologyUse)
      -[:PART_OF]->(project:Project)
RETURN DISTINCT
       project.entity_id AS project_id,
       project.label AS project,
       use.entity_id AS use_id,
       use.purpose AS purpose,
       use.status AS status
ORDER BY project, purpose;

// 6-2. X01: SeCause에서 큐 목적으로 쓴 기술을 공유하는 다른 프로젝트
MATCH (secause:Project {entity_id: 'kg:secause'})
      <-[:PART_OF]-(source_use:TechnologyUse)
      -[:USES_TECHNOLOGY]->(technology:Technology)
      <-[:USES_TECHNOLOGY]-(other_use:TechnologyUse)
      -[:PART_OF]->(other_project:Project)
WHERE coalesce(source_use.purpose, '') CONTAINS '큐'
  AND other_project.entity_id <> secause.entity_id
RETURN DISTINCT
       technology.entity_id AS technology_id,
       technology.label AS technology,
       source_use.purpose AS secause_purpose,
       source_use.status AS secause_status,
       other_project.entity_id AS other_project_id,
       other_project.label AS other_project,
       other_use.purpose AS other_purpose,
       other_use.status AS other_status
ORDER BY technology, other_project, other_purpose;

// 6-3. X03: 한 프로젝트에서는 proposed, 다른 프로젝트에서는 implemented인 기술
MATCH (proposed_project:Project)
      <-[:PART_OF]-(proposed_use:TechnologyUse {status: 'proposed'})
      -[:USES_TECHNOLOGY]->(technology:Technology)
      <-[:USES_TECHNOLOGY]-(implemented_use:TechnologyUse {status: 'implemented'})
      -[:PART_OF]->(implemented_project:Project)
WHERE proposed_project.entity_id <> implemented_project.entity_id
RETURN DISTINCT
       technology.entity_id AS technology_id,
       technology.label AS technology,
       proposed_project.entity_id AS proposed_project_id,
       proposed_project.label AS proposed_project,
       proposed_use.purpose AS proposed_purpose,
       implemented_project.entity_id AS implemented_project_id,
       implemented_project.label AS implemented_project,
       implemented_use.purpose AS implemented_purpose
ORDER BY technology, proposed_project, implemented_project;

// 6-4-a. REPLACES 연쇄를 최대 3단계까지 추적
MATCH path = (new_use:TechnologyUse)-[:REPLACES*1..3]->(old_use:TechnologyUse)
RETURN DISTINCT
       new_use.entity_id AS start_use,
       old_use.entity_id AS replaced_use,
       length(path) AS hops,
       [node IN nodes(path) | node.entity_id] AS use_chain
ORDER BY hops, start_use, replaced_use;

// 6-4-b. REPLACES가 적을 때: 공유 기술로 연결된 프로젝트를 1~2단계 추적
// 프로젝트 한 단계는 Project-Use-Technology-Use-Project의 관계 4개다.
MATCH path = (start:Project {entity_id: $projectId})
             -[:PART_OF|USES_TECHNOLOGY*4..8]-(connected:Project)
WHERE connected.entity_id <> start.entity_id
  AND all(node IN nodes(path)
          WHERE size([same IN nodes(path) WHERE same = node]) = 1)
RETURN DISTINCT
       connected.entity_id AS project_id,
       connected.label AS project,
       length(path) / 4 AS project_hops,
       [node IN nodes(path) | coalesce(node.label, node.entity_id)] AS path_labels
ORDER BY project_hops, project;

// 6-5. X01 + 경로를 구성한 관계의 근거
MATCH (secause:Project {entity_id: 'kg:secause'})
      <-[source_part:PART_OF]-(source_use:TechnologyUse)
      -[source_tech:USES_TECHNOLOGY]->(technology:Technology)
      <-[other_tech:USES_TECHNOLOGY]-(other_use:TechnologyUse)
      -[other_part:PART_OF]->(other_project:Project)
WHERE coalesce(source_use.purpose, '') CONTAINS '큐'
  AND other_project.entity_id <> secause.entity_id
RETURN
       technology.label AS technology,
       source_use.purpose AS secause_purpose,
       source_use.status AS secause_status,
       other_project.label AS other_project,
       other_use.purpose AS other_purpose,
       other_use.status AS other_status,
       collect(DISTINCT {
           side: 'secause-partOf',
           evidence: source_part.evidence,
           chunk_id: source_part.chunk_id
       }) AS secause_project_evidence,
       collect(DISTINCT {
           side: 'secause-usesTechnology',
           evidence: source_tech.evidence,
           chunk_id: source_tech.chunk_id
       }) AS secause_technology_evidence,
       collect(DISTINCT {
           side: 'other-usesTechnology',
           evidence: other_tech.evidence,
           chunk_id: other_tech.chunk_id
       }) AS other_technology_evidence,
       collect(DISTINCT {
           side: 'other-partOf',
           evidence: other_part.evidence,
           chunk_id: other_part.chunk_id
       }) AS other_project_evidence
ORDER BY technology, other_project;

// 진단 1. 관계 타입과 방향
MATCH (from)-[relation]->(to)
RETURN type(relation) AS relationship,
       labels(from) AS from_labels,
       labels(to) AS to_labels,
       count(*) AS count
ORDER BY relationship, from_labels, to_labels;

// 진단 2. SeCause의 목적·상태·기술이 실제로 들어왔는지
MATCH (project:Project {entity_id: 'kg:secause'})
      <-[:PART_OF]-(use:TechnologyUse)
      -[:USES_TECHNOLOGY]->(technology:Technology)
RETURN technology.entity_id, technology.label, use.entity_id, use.purpose, use.status
ORDER BY use.purpose, technology.label;

// 진단 3. 상태 값 분포
MATCH (use:TechnologyUse)
RETURN use.status AS status, count(*) AS count
ORDER BY count DESC;

// 진단 4. entity_id가 같은 중복 노드
MATCH (node)
WHERE node.entity_id IS NOT NULL
WITH node.entity_id AS entity_id, labels(node) AS node_labels, count(*) AS count
WHERE count > 1
RETURN entity_id, node_labels, count
ORDER BY count DESC, entity_id;

// 진단 5. X01의 중간 기술을 다른 프로젝트도 사용하는지 단계별 확인
MATCH (:Project {entity_id: 'kg:secause'})
      <-[:PART_OF]-(source_use:TechnologyUse)
      -[:USES_TECHNOLOGY]->(technology:Technology)
WHERE coalesce(source_use.purpose, '') CONTAINS '큐'
OPTIONAL MATCH (technology)<-[:USES_TECHNOLOGY]-(other_use:TechnologyUse)
OPTIONAL MATCH (other_use)-[:PART_OF]->(other_project:Project)
RETURN technology.entity_id,
       technology.label,
       collect(DISTINCT other_project.entity_id) AS project_ids;
