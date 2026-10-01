# 읽을거리

학습 노트에서 참고한 자료를 주차별로 모읍니다. `## N주차` 아래 자료는 스터디 현황판에도 모아서 표시됩니다.

## 1주차 · RAG, 지식 그래프와 온톨로지 기초

- 개인 Notion 1 Week — RAG와 지식 그래프 기초 학습 기록
- 온톨로지 세미나 PDF — 트리플과 온톨로지 개념 참고자료

## 2주차 · 청킹, BM25와 벡터 검색

- [pgvector](https://github.com/pgvector/pgvector) — PostgreSQL 벡터 저장과 검색
- [Elasticsearch similarity settings](https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity) — BM25 관련도 계산 설정
- [Nori 분석기](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori) — 한국어 형태소 분석

## 3주차 · 하이브리드 검색, RAG와 Recall 평가

- [Elastic: Hybrid retrieval와 RRF](https://www.elastic.co/search-labs/blog/improving-information-retrieval-elastic-stack-hybrid) — 키워드·벡터 검색 결과 결합
- [pgvector: HNSW](https://github.com/pgvector/pgvector#hnsw) — 근사 최근접 이웃 검색 인덱스
- [Ollama Chat API](https://docs.ollama.com/api/chat) — 로컬 모델로 RAG 답변 생성
- [OpenRouter Quickstart](https://openrouter.ai/docs/quickstart) — 외부 모델 호출과 답변 비교

## 4주차 · 지식 그래프의 배경과 온톨로지 방법론

- [학습 원본: Notion](https://www.notion.so/3ebdbb08775281a1a19ecc9804484067) — 지식 그래프의 필요성과 온톨로지 변천사
- [RDF Primer](https://www.w3.org/TR/rdf11-primer/) — RDF 트리플과 데이터 표현
- [RDFS](https://www.w3.org/TR/rdf-schema/) — 클래스와 관계의 계층 정의
- [OWL Primer](https://www.w3.org/TR/owl2-primer/) — 온톨로지 모델링과 논리적 의미
- [SHACL](https://www.w3.org/TR/shacl/) — RDF 그래프의 제약과 검증
- [Linked Data](https://www.w3.org/DesignIssues/LinkedData.html) — 웹 식별자를 통한 데이터 연결
- [Wikidata SPARQL 튜토리얼](https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial) — 공개 지식 그래프 질의
- [Google Knowledge Graph 소개](https://blog.google/products-and-platforms/products/search/introducing-knowledge-graph-things-not/) — 검색에서의 지식 그래프 활용
- [Palantir Ontology](https://www.palantir.com/docs/foundry/architecture-center/ontology-system) — 업무 대상·관계·행동 모델
- [Microsoft GraphRAG 논문](https://arxiv.org/abs/2404.16130) — 그래프 기반 커뮤니티 요약과 검색
- [GraphRAG Global Search](https://microsoft.github.io/graphrag/query/global_search/) — 전체 자료를 대상으로 하는 질의 방식
