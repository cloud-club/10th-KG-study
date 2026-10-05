// 노드 개수: 라벨별
CALL {
  MATCH (node:Project)
  RETURN 'Project' AS kind, count(node) AS count
  UNION ALL
  MATCH (node:Technology)
  RETURN 'Technology' AS kind, count(node) AS count
  UNION ALL
  MATCH (node:TechnologyUse)
  RETURN 'TechnologyUse' AS kind, count(node) AS count
}
RETURN kind, count
ORDER BY kind;

// 관계 개수: 타입별
MATCH ()-[relationship]->()
RETURN type(relationship) AS relationship_type, count(*) AS count
ORDER BY relationship_type;

// 같은 id를 가진 중복 노드. UNIQUE 제약이 정상이라면 0건이다.
MATCH (node)
WHERE node.id IS NOT NULL
WITH node.id AS id, collect(labels(node)) AS node_labels, count(*) AS count
WHERE count > 1
RETURN id, node_labels, count
ORDER BY count DESC, id;

// 공백·하이픈·밑줄·대소문자만 다른 유사 라벨과 서로 다른 id를 찾는다.
MATCH (node)
WHERE (node:Project OR node:Technology OR node:TechnologyUse)
  AND node.label IS NOT NULL
WITH toLower(
       replace(replace(replace(trim(node.label), ' ', ''), '-', ''), '_', '')
     ) AS normalized_label,
     collect(DISTINCT {id: node.id, label: node.label, types: labels(node)}) AS candidates
WHERE size(candidates) > 1
RETURN normalized_label, candidates
ORDER BY normalized_label;

// 관계 방향과 양 끝 라벨 확인
MATCH (source)-[relationship]->(target)
RETURN type(relationship) AS relationship_type,
       labels(source) AS source_labels,
       labels(target) AS target_labels,
       count(*) AS count
ORDER BY relationship_type, source_labels, target_labels;
