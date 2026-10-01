---
title: 2주차 - RAG 데이터셋 선정과 임베딩 준비
date: 2026-09-17
tags: [rag, dataset, embedding, knowledge-graph, ontology, neo4j]
status: in-progress
---

# 02. RAG 데이터셋 선정과 임베딩 준비

## 한 줄 요약

RAG와 Knowledge Graph 실습에 사용할 데이터셋을 비교한 뒤, 제품·기능·기술 간 관계를 표현하기 좋은 SLEXN TechDocs를 선택했다. 이후 JSON/Markdown 형태로 데이터를 정리하고, Markdown 문서를 기준으로 Chunking과 Embedding을 수행해 Vector Search에 사용할 데이터 구조를 준비했다.

## 1. 데이터셋 후보 비교

처음에는 개인 Notion, 여러 기업 정보, SLEXN TechDocs를 후보로 생각했다.

### 개인 Notion

- 직접 작성한 데이터라 이해하기 쉽다.
- 데이터 수정과 추가가 편하다.
- 개인 RAG 실습에는 적합하다.
- 다만 관계 구조가 단순해질 수 있고, 포트폴리오에서는 개인 문서 검색 프로젝트로 보일 수 있다.

### 여러 기업 정보

- 기업, 산업군, 제품, 기술 스택 등 다양한 Entity를 만들 수 있다.
- 기업 비교나 검색 서비스로 확장할 수 있다.
- 하지만 기업 간 관계를 자연스럽게 정의하기 어렵고 최신성 관리가 필요하다.

### 회사 TechDocs

최종적으로 기술 문서를 데이터셋으로 선택했다.

기술 문서에는 Product, Feature, Technology, Concept, UseCase, Integration, Document와 같은 정보가 함께 존재한다.

따라서 단순한 Vector Search뿐 아니라, 이후 Neo4j에서 관계를 표현하는 Knowledge Graph로 확장하기 좋다고 판단했다.

## 2. 왜 기술 문서를 선택했는가

일반적인 Vector RAG는 질문과 의미적으로 가까운 문서를 찾는다.

```text
Question
   ↓
Embedding
   ↓
Vector Search
   ↓
Top-K Chunks
   ↓
LLM
```

하지만 기술 문서에서는 의미 유사도뿐 아니라 관계도 중요하다.

```text
Product -[HAS_FEATURE]-> Feature
Product -[USES]-> Technology
Product -[INTEGRATES_WITH]-> Product

Feature -[SUPPORTS]-> UseCase

Document -[DESCRIBES]-> Product
Document -[EXPLAINS]-> Feature
```

이런 관계를 표현하려면 Vector Search만으로는 한계가 있기 때문에, 최종적으로는 Graph Search까지 결합하는 구조를 목표로 잡았다.

## 3. Data 형식 결정

TechDocs는 JSON, Markdown, HTML 중 어떤 방식으로 export할 지 고민을했습니다.
데이터는 JSON과 Markdown 중심으로 준비했습니다. JSON은 문서 ID나 제목, 상위 문서 같은 Metadata를 보존하는 용도로 보고, Markdown은 실제 RAG에서 텍스트를 나누고 임베딩하는 용도로 사용했습니다.

이미지도 처음에는 같이 활용하려고 했는데, 이미지까지 처리하려면 Vision Model이나 별도 파이프라인이 필요해서 이번 실습 범위에서는 제외했습니다. 우선 텍스트 기반으로 구조를 단순하게 가져가기로 했습니다.
이번 실습에서는 JSON과 Markdown을 중심으로 사용하기로 했다.

### JSON

JSON은 원본 데이터와 Metadata를 보존하는 용도로 사용한다.

```json
{
  "id": "...",
  "title": "...",
  "parent": "...",
  "content": "...",
  "createdAt": "...",
  "updatedAt": "..."
}
```

이 정보를 이용하면 이후 문서 간 계층 구조도 그래프로 표현할 수 있다.

```text
Collection
   ↓ CONTAINS
Document
   ↓ HAS_SECTION
Section
```

### Markdown

Markdown은 RAG용 텍스트 처리에 사용한다.

```markdown
# Product

## Feature A

설명...

## Feature B

설명...
```

Heading 구조를 기준으로 문서를 나누면 문맥을 유지한 Chunk를 만들기 쉽다.

```text
Markdown
   ↓
Heading 기준 Split
   ↓
Chunk
   ↓
Embedding
```

## 4. 이미지 제외

처음에는 이미지와 첨부파일도 활용하는 것을 고려했다.

하지만 Architecture Diagram, UI Screenshot까지 처리하면 Vision Model이나 별도의 이미지 파이프라인이 필요해져 실습 범위가 너무 커질 수 있다고 판단했다.

따라서 이번 프로젝트에서는 텍스트 데이터만 사용하기로 했다.

```text
사용
- JSON
- Markdown
- Text Metadata

제외
- Image
- Screenshot
- Diagram
- Attachment
```

## 5. 데이터 정제와 Chunking

문서를 그대로 임베딩하지 않고, 검색에 적합한 크기로 나누는 과정을 진행했다.

단순 글자 수 기준보다 Markdown Heading 구조를 유지하는 방식을 우선적으로 고려했다.

```markdown
# Codebeamer

## Requirement Management

...

## Test Management

...
```

이를 다음과 같이 나눌 수 있다.

```text
Chunk 1
Codebeamer / Requirement Management

Chunk 2
Codebeamer / Test Management
```

각 Chunk에는 원본 문서를 추적할 수 있도록 Metadata를 유지한다.

```json
{
  "document_id": "doc_001",
  "title": "Codebeamer",
  "section": "Requirement Management",
  "content": "...",
  "source": "TechDocs"
}
```

## 6. Embedding

정제된 Chunk를 Embedding Model을 이용해 Vector로 변환했다.

```text
Document
   ↓
Parsing
   ↓
Chunking
   ↓
Embedding
   ↓
Vector
```

이를 통해 자연어 질문과 의미적으로 가까운 Chunk를 검색할 수 있는 구조를 만들었다.

```text
Question
   ↓
Embedding
   ↓
Vector Similarity Search
   ↓
Top-K Chunks
```

이번 단계의 목적은 완성된 RAG 서비스를 만드는 것보다, 문서가 실제로 검색 가능한 Vector 형태로 변환되는 전체 흐름을 이해하는 데 있었다.

## 7. 초기 Ontology 아이디어

데이터를 살펴보면서 다음 Entity를 우선 후보로 잡았다.

```text
Product
Feature
Technology
Concept
UseCase
Document
Vendor
```

초기 Relation 후보:

```text
Product -[HAS_FEATURE]-> Feature
Product -[USES]-> Technology
Product -[INTEGRATES_WITH]-> Product

Feature -[SUPPORTS]-> UseCase

Document -[DESCRIBES]-> Product
Document -[EXPLAINS]-> Feature
Document -[MENTIONS]-> Technology
```

처음부터 모든 Ontology를 고정하기보다, 실제 문서를 기준으로 Entity와 Relation을 점진적으로 확장할 예정이다.

## 8. 이번 주에 배운 점

### 데이터셋은 양보다 구조가 중요하다

Knowledge Graph까지 고려한다면 단순히 문서가 많은 것보다, 문서 안에서 Entity와 Relation을 찾을 수 있는지가 더 중요하다.

```text
무엇이 존재하는가?
→ Entity

서로 어떻게 연결되는가?
→ Relationship
```

### Chunking 방식이 검색 품질에 영향을 준다

같은 문서라도 어디서 나누느냐에 따라 검색되는 정보가 달라질 수 있다.

따라서 문서 구조와 의미 단위를 최대한 보존하는 방식이 중요하다.

### Vector Search와 Graph Search의 역할은 다르다

Vector Search는 의미적으로 유사한 내용을 찾는 데 강하다.

```text
"요구사항 변경 관리"
≈
"Requirement change management"
```

Graph Search는 명시적인 관계 탐색에 강하다.

```text
Product
  ↓ HAS_FEATURE
Traceability
  ↓ SUPPORTS
Change Management
```

따라서 이후에는 두 검색 방식을 함께 사용하는 Hybrid RAG로 확장할 계획이다.

## 9. 다음 단계

다음 단계에서는 현재 준비한 데이터를 기반으로 Neo4j에 Knowledge Graph를 구축한다.

1. Entity 후보 추출
2. Relation 후보 추출
3. Ontology Schema 정의
4. Neo4j Node / Relationship 설계
5. 샘플 데이터 적재
6. Graph Query 작성
7. Vector Search와 Graph Search 결합

최종 목표:

```text
Technical Documents
        ↓
Parsing / Chunking
        ↓
Embedding
        ↓
Vector Search

        +

Entity / Relation Extraction
        ↓
Ontology
        ↓
Neo4j
        ↓
Graph Search

        ↓
     Hybrid RAG
```
