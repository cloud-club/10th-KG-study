-- 6-1-a. 특정 프로젝트가 쓴 기술 전부
SELECT DISTINCT
       technology.entity_id AS technology_id,
       technology.label AS technology,
       use_node.entity_id AS use_id,
       use_node.props->>'purpose' AS purpose,
       use_node.props->>'status' AS status
FROM entities AS project
JOIN edges AS part
  ON part.object = project.entity_id AND part.predicate = 'partOf'
JOIN entities AS use_node
  ON use_node.entity_id = part.subject AND use_node.type = 'TechnologyUse'
JOIN edges AS uses
  ON uses.subject = use_node.entity_id AND uses.predicate = 'usesTechnology'
JOIN entities AS technology
  ON technology.entity_id = uses.object AND technology.type = 'Technology'
WHERE project.entity_id = 'kg:secause'
ORDER BY technology, purpose;

-- 6-1-b. 특정 기술을 쓴 프로젝트 전부
SELECT DISTINCT
       project.entity_id AS project_id,
       project.label AS project,
       use_node.entity_id AS use_id,
       use_node.props->>'purpose' AS purpose,
       use_node.props->>'status' AS status
FROM entities AS technology
JOIN edges AS uses
  ON uses.object = technology.entity_id AND uses.predicate = 'usesTechnology'
JOIN entities AS use_node
  ON use_node.entity_id = uses.subject AND use_node.type = 'TechnologyUse'
JOIN edges AS part
  ON part.subject = use_node.entity_id AND part.predicate = 'partOf'
JOIN entities AS project
  ON project.entity_id = part.object AND project.type = 'Project'
WHERE technology.entity_id = 'kg:tech-redis'
ORDER BY project, purpose;

-- 6-2. X01: SeCause에서 큐 목적으로 쓴 기술을 공유하는 다른 프로젝트
SELECT DISTINCT
       technology.entity_id AS technology_id,
       technology.label AS technology,
       source_use.props->>'purpose' AS secause_purpose,
       source_use.props->>'status' AS secause_status,
       other_project.entity_id AS other_project_id,
       other_project.label AS other_project,
       other_use.props->>'purpose' AS other_purpose,
       other_use.props->>'status' AS other_status
FROM entities AS secause
JOIN edges AS source_part
  ON source_part.object = secause.entity_id AND source_part.predicate = 'partOf'
JOIN entities AS source_use
  ON source_use.entity_id = source_part.subject
JOIN edges AS source_uses
  ON source_uses.subject = source_use.entity_id
 AND source_uses.predicate = 'usesTechnology'
JOIN entities AS technology
  ON technology.entity_id = source_uses.object
JOIN edges AS other_uses
  ON other_uses.object = technology.entity_id
 AND other_uses.predicate = 'usesTechnology'
JOIN entities AS other_use
  ON other_use.entity_id = other_uses.subject
JOIN edges AS other_part
  ON other_part.subject = other_use.entity_id
 AND other_part.predicate = 'partOf'
JOIN entities AS other_project
  ON other_project.entity_id = other_part.object
WHERE secause.entity_id = 'kg:secause'
  AND coalesce(source_use.props->>'purpose', '') LIKE '%큐%'
  AND other_project.entity_id <> secause.entity_id
ORDER BY technology, other_project, other_purpose;

-- 6-3. X03: 한 프로젝트에서는 proposed, 다른 프로젝트에서는 implemented인 기술
SELECT DISTINCT
       technology.entity_id AS technology_id,
       technology.label AS technology,
       proposed_project.entity_id AS proposed_project_id,
       proposed_project.label AS proposed_project,
       proposed_use.props->>'purpose' AS proposed_purpose,
       implemented_project.entity_id AS implemented_project_id,
       implemented_project.label AS implemented_project,
       implemented_use.props->>'purpose' AS implemented_purpose
FROM entities AS proposed_use
JOIN edges AS proposed_uses
  ON proposed_uses.subject = proposed_use.entity_id
 AND proposed_uses.predicate = 'usesTechnology'
JOIN entities AS technology
  ON technology.entity_id = proposed_uses.object
JOIN edges AS proposed_part
  ON proposed_part.subject = proposed_use.entity_id
 AND proposed_part.predicate = 'partOf'
JOIN entities AS proposed_project
  ON proposed_project.entity_id = proposed_part.object
JOIN edges AS implemented_uses
  ON implemented_uses.object = technology.entity_id
 AND implemented_uses.predicate = 'usesTechnology'
JOIN entities AS implemented_use
  ON implemented_use.entity_id = implemented_uses.subject
JOIN edges AS implemented_part
  ON implemented_part.subject = implemented_use.entity_id
 AND implemented_part.predicate = 'partOf'
JOIN entities AS implemented_project
  ON implemented_project.entity_id = implemented_part.object
WHERE proposed_use.type = 'TechnologyUse'
  AND proposed_use.props->>'status' = 'proposed'
  AND implemented_use.props->>'status' = 'implemented'
  AND proposed_project.entity_id <> implemented_project.entity_id
ORDER BY technology, proposed_project, implemented_project;

-- 6-4-a. REPLACES 연쇄를 최대 3단계까지 추적
WITH RECURSIVE replace_edges AS (
    SELECT DISTINCT subject, object
    FROM edges
    WHERE predicate = 'replaces'
), replacement_path AS (
    SELECT subject AS start_use,
           object AS current_use,
           ARRAY[subject, object] AS use_chain,
           1 AS hops
    FROM replace_edges

    UNION ALL

    SELECT path.start_use,
           next_edge.object,
           path.use_chain || next_edge.object,
           path.hops + 1
    FROM replacement_path AS path
    JOIN replace_edges AS next_edge ON next_edge.subject = path.current_use
    WHERE path.hops < 3
      AND NOT next_edge.object = ANY(path.use_chain)
)
SELECT DISTINCT start_use,
       current_use AS replaced_use,
       hops,
       use_chain
FROM replacement_path
ORDER BY hops, start_use, replaced_use;

-- 6-4-b. 공유 기술로 연결된 프로젝트를 1~2단계 추적
WITH RECURSIVE project_technology AS (
    SELECT DISTINCT part.object AS project_id, uses.object AS technology_id
    FROM edges AS part
    JOIN edges AS uses
      ON uses.subject = part.subject AND uses.predicate = 'usesTechnology'
    WHERE part.predicate = 'partOf'
), project_links AS (
    SELECT DISTINCT left_side.project_id AS from_project,
           right_side.project_id AS to_project,
           left_side.technology_id
    FROM project_technology AS left_side
    JOIN project_technology AS right_side
      ON right_side.technology_id = left_side.technology_id
     AND right_side.project_id <> left_side.project_id
), project_path AS (
    SELECT link.from_project AS start_project,
           link.to_project AS current_project,
           ARRAY[link.from_project, link.to_project] AS project_chain,
           ARRAY[link.technology_id] AS technology_chain,
           1 AS project_hops
    FROM project_links AS link
    WHERE link.from_project = 'kg:secause'

    UNION ALL

    SELECT path.start_project,
           link.to_project,
           path.project_chain || link.to_project,
           path.technology_chain || link.technology_id,
           path.project_hops + 1
    FROM project_path AS path
    JOIN project_links AS link ON link.from_project = path.current_project
    WHERE path.project_hops < 2
      AND NOT link.to_project = ANY(path.project_chain)
)
SELECT DISTINCT entity.entity_id AS project_id,
       entity.label AS project,
       path.project_hops,
       path.project_chain,
       path.technology_chain
FROM project_path AS path
JOIN entities AS entity ON entity.entity_id = path.current_project
ORDER BY project_hops, project;

-- 6-5. X01 + source/other TechnologyUse에 연결된 모든 근거
WITH evidence_by_use AS (
    SELECT subject AS use_id,
           jsonb_agg(DISTINCT jsonb_build_object(
               'predicate', predicate,
               'object', object,
               'evidence', evidence,
               'chunk_id', chunk_id
           )) AS evidence
    FROM edges
    GROUP BY subject
), x01 AS (
    SELECT DISTINCT
           technology.entity_id AS technology_id,
           technology.label AS technology,
           source_use.entity_id AS source_use_id,
           source_use.props->>'purpose' AS secause_purpose,
           source_use.props->>'status' AS secause_status,
           other_project.entity_id AS other_project_id,
           other_project.label AS other_project,
           other_use.entity_id AS other_use_id,
           other_use.props->>'purpose' AS other_purpose,
           other_use.props->>'status' AS other_status
    FROM entities AS secause
    JOIN edges AS source_part
      ON source_part.object = secause.entity_id AND source_part.predicate = 'partOf'
    JOIN entities AS source_use ON source_use.entity_id = source_part.subject
    JOIN edges AS source_uses
      ON source_uses.subject = source_use.entity_id
     AND source_uses.predicate = 'usesTechnology'
    JOIN entities AS technology ON technology.entity_id = source_uses.object
    JOIN edges AS other_uses
      ON other_uses.object = technology.entity_id
     AND other_uses.predicate = 'usesTechnology'
    JOIN entities AS other_use ON other_use.entity_id = other_uses.subject
    JOIN edges AS other_part
      ON other_part.subject = other_use.entity_id
     AND other_part.predicate = 'partOf'
    JOIN entities AS other_project ON other_project.entity_id = other_part.object
    WHERE secause.entity_id = 'kg:secause'
      AND coalesce(source_use.props->>'purpose', '') LIKE '%큐%'
      AND other_project.entity_id <> secause.entity_id
)
SELECT x01.*,
       source_evidence.evidence AS secause_evidence,
       other_evidence.evidence AS other_project_evidence
FROM x01
JOIN evidence_by_use AS source_evidence
  ON source_evidence.use_id = x01.source_use_id
JOIN evidence_by_use AS other_evidence
  ON other_evidence.use_id = x01.other_use_id
ORDER BY technology, other_project;

-- 진단 1. 관계가 실제로 존재하는가
SELECT predicate, count(*)
FROM edges
GROUP BY predicate
ORDER BY predicate;

-- 진단 2. 관계 방향과 domain/range 타입이 맞는가
SELECT edge.predicate,
       subject.type AS subject_type,
       coalesce(object_entity.type, 'literal') AS object_type,
       count(*)
FROM edges AS edge
JOIN entities AS subject ON subject.entity_id = edge.subject
LEFT JOIN entities AS object_entity ON object_entity.entity_id = edge.object
GROUP BY edge.predicate, subject.type, coalesce(object_entity.type, 'literal')
ORDER BY edge.predicate, subject_type, object_type;

-- 진단 3. SeCause의 목적·상태·기술
SELECT DISTINCT technology.entity_id,
       technology.label,
       use_node.entity_id AS use_id,
       use_node.props->>'purpose' AS purpose,
       use_node.props->>'status' AS status
FROM edges AS part
JOIN entities AS use_node ON use_node.entity_id = part.subject
JOIN edges AS uses
  ON uses.subject = use_node.entity_id AND uses.predicate = 'usesTechnology'
JOIN entities AS technology ON technology.entity_id = uses.object
WHERE part.predicate = 'partOf'
  AND part.object = 'kg:secause'
ORDER BY purpose, technology.label;

-- 진단 4. 상태 값 분포
SELECT props->>'status' AS status, count(*)
FROM entities
WHERE type = 'TechnologyUse'
GROUP BY props->>'status'
ORDER BY count(*) DESC;

-- 진단 5. 정규화 후에도 entity_id가 중복되는가
-- PK 때문에 정상 결과는 항상 0건이다.
SELECT entity_id, count(*)
FROM entities
GROUP BY entity_id
HAVING count(*) > 1;

-- 진단 6. X01 중간 기술별 연결 프로젝트
SELECT technology.entity_id,
       technology.label,
       array_agg(DISTINCT project.entity_id ORDER BY project.entity_id) AS project_ids
FROM edges AS source_part
JOIN entities AS source_use ON source_use.entity_id = source_part.subject
JOIN edges AS source_uses
  ON source_uses.subject = source_use.entity_id
 AND source_uses.predicate = 'usesTechnology'
JOIN entities AS technology ON technology.entity_id = source_uses.object
JOIN edges AS all_uses
  ON all_uses.object = technology.entity_id
 AND all_uses.predicate = 'usesTechnology'
JOIN edges AS all_parts
  ON all_parts.subject = all_uses.subject
 AND all_parts.predicate = 'partOf'
JOIN entities AS project ON project.entity_id = all_parts.object
WHERE source_part.predicate = 'partOf'
  AND source_part.object = 'kg:secause'
  AND coalesce(source_use.props->>'purpose', '') LIKE '%큐%'
GROUP BY technology.entity_id, technology.label
ORDER BY technology.label;
