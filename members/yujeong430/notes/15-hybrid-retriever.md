---
title: 하이브리드 리트리버 - 벡터로 진입하고 그래프로 확장하기
date: 2026-10-07
tags: [graphrag, hybrid-retriever, vector-search, neo4j]
status: done
---

# 하이브리드 리트리버: 벡터로 진입하고 그래프로 확장하기

> 참고 자료:
> - [Neo4j GraphAcademy: GraphRAG Retrievers](https://graphacademy.neo4j.com/courses/workshop-graphrag-introduction/3-querying/2-retrievers/)
> - [Neo4j Cypher Manual: Vector indexes](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)
> - [Microsoft GraphRAG: Local Search](https://microsoft.github.io/graphrag/query/local_search/)

## 한 줄 요약

하이브리드 리트리버는 벡터 검색으로 그래프 탐색의 출발점(진입 노드)을 찾고, 그 노드에서 관계를 따라 정보를 넓혀 가는 검색 방식이다. 의미가 비슷한 곳을 찾는 일은 벡터 검색이, 연결된 정보를 가져오는 일은 그래프 탐색이 맡는다.

이 노트의 그래프 구조와 쿼리 예시는 Neo4j 기준이다. 노드 설명문 임베딩으로 출발 노드를 찾는 로컬 서치도 같은 패턴에 속한다.

## 1. 기본 개념

- **리트리버**: RAG에서 질문에 맞는 자료를 찾아오는 구성 요소
- **청크**: 문서를 일정 길이로 나눈 조각
- **벡터 검색**: 질문 임베딩과 의미가 가까운 청크를 찾는 검색
- **진입 노드**: 그래프 탐색을 시작하는 노드. 로컬 서치의 엔티티 링킹 결과와 같은 역할을 한다

## 2. 왜 필요한가

| 방식 | 강점 | 약점 |
| --- | --- | --- |
| 벡터 검색 | 표현이 달라도 의미가 비슷한 청크를 찾는다 | 찾은 청크에 없는 연결 정보는 가져오지 못한다 |
| 그래프 탐색 | 출발 노드에서 연결된 정보를 정확히 따라간다 | 질문 표현이 노드 이름과 다르면 출발 노드를 정하지 못한다 |

두 방식의 약점이 서로 반대이므로, 순서대로 이으면 서로를 보완할 수 있다.

> 질문: "반지하 가족이 부잣집에 하나씩 취업하는 영화, 그 감독의 다른 작품은?"

질문에 영화 제목도, 감독 이름도 없다.

- **그래프 탐색만 사용**: 질문과 일치하는 노드 이름이 없어 출발점을 정하지 못한다.
- **벡터 검색만 사용**: 기생충 줄거리 청크는 찾지만, 그 청크에는 감독의 다른 작품 정보가 없다.
- **두 방식 결합**:

```text
① 벡터 검색    질문과 가까운 청크 검색 → "반지하에 사는 기택 가족은..." 청크
② 노드 이동    청크가 언급하는 노드 → (기생충)
③ 그래프 확장   (기생충) ←연출─ (봉준호) ─연출→ (살인의 추억), (괴물), (설국열차)
④ 답변         "봉준호의 다른 작품은 살인의 추억, 괴물, 설국열차다."
```

벡터 검색이 엔티티 링킹을 대신하므로, 이름이 없는 질문에서도 출발점을 찾을 수 있다.

## 3. 그래프 구조: Lexical Graph와 Domain Graph

벡터 검색은 청크를 찾고 그래프 탐색은 엔티티 노드에서 시작한다. 그래서 그래프 안에 청크와 엔티티를 잇는 관계가 있어야 한다. Neo4j는 이 구조를 lexical graph와 domain graph로 나눠 설명한다.

```text
[Lexical graph]  (Chunk: "반지하에 사는 기택 가족은...")
                          ▲
                          │ FROM_CHUNK
[Domain graph]   (기생충) ←연출─ (봉준호) ─연출→ (괴물), (설국열차), (살인의 추억)
```

| 구성 | 내용 | 역할 |
| --- | --- | --- |
| Lexical graph | 문서, 청크 노드와 청크 임베딩 | 벡터 검색 대상 |
| Domain graph | 추출한 엔티티와 관계 (일반적인 지식 그래프) | 그래프 탐색 대상 |
| 엔티티-청크 관계 | 엔티티가 어느 청크에서 추출되었는지 | lexical graph와 domain graph 사이 이동 |

청크에서 엔티티를 추출할 때 출처 청크를 관계로 함께 저장하면 이 구조가 만들어진다. 관계 이름은 도구마다 다르다. Neo4j의 `neo4j-graphrag`는 기본값으로 `(엔티티)-[:FROM_CHUNK]->(청크)`를 쓰고, LangChain의 `Neo4jGraph`는 `(문서)-[:MENTIONS]->(엔티티)`를 쓴다. 이 노트는 `neo4j-graphrag` 기본값을 따른다.

## 4. 진입 대상

| 진입 대상 | 임베딩 대상 | 특징 |
| --- | --- | --- |
| 청크 | 원문 청크 | 기존 벡터 검색을 그대로 활용하고, 원문 근거를 바로 얻는다 |
| 엔티티 노드 | 노드 설명문 | 질문이 특정 대상에 관한 것일 때 정확하다. 로컬 서치의 의미 매칭과 같은 방식 |

## 5. Cypher 예시

Neo4j에서는 벡터 검색과 그래프 탐색을 하나의 쿼리로 이어서 실행할 수 있다.

```cypher
// ① 질문 임베딩과 가장 가까운 청크 5개
CALL db.index.vector.queryNodes('chunk_embedding', 5, $questionEmbedding)
YIELD node AS chunk, score

// ② 청크에서 추출된 영화 노드로 이동
MATCH (movie:Movie)-[:FROM_CHUNK]->(chunk)

// ③ 감독을 거쳐 감독의 다른 영화로 확장
MATCH (movie)<-[:DIRECTED]-(director:Person)-[:DIRECTED]->(other:Movie)
WHERE other <> movie

RETURN movie.title AS matchedMovie, director.name AS director,
       collect(other.title) AS otherMovies, score
ORDER BY score DESC;
```

```text
matchedMovie | director | otherMovies
기생충        | 봉준호    | [살인의 추억, 괴물, 설국열차]
```

`$questionEmbedding`은 질문을 임베딩한 값이고, `score`는 청크와 질문의 유사도다.

Neo4j의 `neo4j-graphrag` 라이브러리는 이 패턴을 `VectorCypherRetriever`로 제공한다. 벡터 검색(①)은 라이브러리가 처리하고, 개발자는 확장 쿼리(②, ③)만 작성한다.

## 6. 설계 시 고려할 점

| 항목 | 고려 사항 |
| --- | --- |
| 진입 개수(top-k) | 늘리면 놓치는 청크는 줄지만 확장 후 정보량이 크게 늘어난다 |
| 확장 범위 | 몇 홉까지, 어떤 관계를 따라갈지 정한다 |
| 원문 포함 여부 | 답변 근거를 제시하려면 관계와 함께 원문 청크도 넣는다 |

## 7. 한계

| 한계 | 설명 |
| --- | --- |
| 진입 실패 | 벡터 검색에서 관련 청크를 찾지 못하면 확장해도 답을 얻을 수 없다 |
| 연결 누락 | 엔티티-청크 관계가 빠지면 청크에서 엔티티로 이동할 수 없다 |
| 과도한 확장 | 진입 노드가 허브 노드와 연결되어 있으면 무관한 정보가 많이 들어온다 |
| 지연 시간 | 벡터 검색과 그래프 탐색을 모두 거치므로 한 가지만 쓸 때보다 느리다 |
