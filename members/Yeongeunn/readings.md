# 참고자료

## 2주차 · 검색 방식과 데이터 저장

- [실용적인 BM25: 알고리즘과 변수 — Elastic](https://www.elastic.co/kr/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables) — 한국어. 단어가 자주 나온다고 점수가 계속 같은 비율로 오르지 않는 이유와 문서 길이 보정을 설명한다.
- [공식 한국어 분석 플러그인 “노리” — Elastic](https://www.elastic.co/kr/blog/nori-the-official-elasticsearch-plugin-for-korean-language-analysis) — 한국어. 조사·복합어 때문에 공백 분리만으로 부족한 이유와 Nori의 처리 방식을 살펴볼 수 있다.
- [HNSW 설명과 구현 — Pinecone](https://www.pinecone.io/learn/series/rag/hnsw/) — 영어. 계층별 그래프 그림으로 탐색 과정을 설명하고 Faiss 예제를 제공한다. pgvector와는 원리를 연결해서 읽을 수 있다.
- [고급 RAG 기술: 데이터 처리와 수집 — Elastic](https://www.elastic.co/kr/search-labs/blog/advanced-rag-techniques-part-1) — 한국어. 문서 정제·청킹 방식이 검색에 미치는 영향을 살펴보기 좋다.
- [pgvector README](https://github.com/pgvector/pgvector) — 벡터 컬럼 생성, 거리 연산자, 정확 검색과 HNSW의 SQL 예제.
- DDIA 3장 「저장소와 검색」 — 해시 인덱스·SSTable/LSM·B-tree와 검색 구조를 연결하는 교재.

## 3주차 · 하이브리드 검색과 RAG

- [검색 증강 생성(RAG)이란? — Elastic](https://www.elastic.co/kr/what-is/retrieval-augmented-generation) — 한국어. 검색한 정보를 생성 모델에 전달하는 전체 흐름부터 볼 수 있다.
- [하이브리드 검색에 RRF 도입하기 — OpenSearch](https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/) — 영어. 점수 정규화와 순위 융합의 차이, 계산 예시를 함께 설명한다. 설정 예제는 OpenSearch용이다.
- [Aurora PostgreSQL에서 한국어 하이브리드 검색 구현하기 — AWS](https://aws.amazon.com/ko/blogs/tech/aurora-postgresql-pg-bigm-pgvector-korean-hybrid-search/) — 한국어. 텍스트·벡터 저장과 SQL로 RRF를 결합하는 흐름을 보여준다. 이 글의 키워드 검색은 pg_bigm이므로 스터디의 Elasticsearch BM25와 구분해서 본다.
- [검색 평가 지표 설명 — Pinecone](https://www.pinecone.io/learn/offline-evaluation/) — 영어. Precision·Recall·MRR·nDCG를 순위 예시와 함께 비교한다.
- [RAG 시리즈 — Pinecone](https://www.pinecone.io/learn/series/rag/) — 임베딩·검색·리랭킹 등 주제별로 찾아볼 수 있는 목록.
- Weaviate Advanced RAG Techniques ebook — 청킹·질문 변환·하이브리드 검색·리랭킹 참고.

## 추가 학습 · 개체추출·임베딩·생성 모델

- [개체명 인식이란? — IBM](https://www.ibm.com/think/topics/named-entity-recognition) — 규칙·학습·혼합 방식과 활용 사례를 설명하는 입문 글.
- [spaCy 개체명 인식 예제](https://spacy.io/usage/linguistic-features#named-entities) — 추출한 이름·타입·원문 위치를 코드에서 확인하는 예제.
- [임베딩이란 무엇인가요? — IBM](https://www.ibm.com/kr-ko/think/architectures/rag-cookbook/embedding) — 한국어. 텍스트를 숫자로 표현해 검색에 사용하는 흐름.
- [Cohere 의미 검색 튜토리얼](https://docs.cohere.com/docs/semantic-search-with-cohere) — 문서와 질문을 각각 임베딩하고 검색 결과를 얻는 과정.
- [대규모 언어 모델이란? — AWS](https://aws.amazon.com/ko/what-is/large-language-model/) — 한국어. 언어 모델의 학습과 활용을 설명하는 입문 자료.
- [Stanford NER 소개와 실행 예제](https://nlp.stanford.edu/software/CRF-NER.html) — CRF 기반 추출기가 어떤 입력과 출력을 사용하는지 확인할 수 있다.

모델별 발전 과정, 평가셋의 발표 시점과 원 논문은 [개체추출](notes/06-entity-extraction-models.md)·[임베딩](notes/07-embedding-models.md)·[생성 모델](notes/08-generative-models.md)에 정리했다.


## 4주차 · 지식 그래프와 온톨로지

- [RDF Primer — W3C](https://www.w3.org/TR/rdf11-primer/) — 트리플·식별자·리터럴을 예제로 읽기.
- [OWL 2 Primer — W3C](https://www.w3.org/TR/owl2-primer/) — 클래스와 관계의 의미, 열린 세계 가정 이해.
- [구글 지식 그래프 소개](https://blog.google/products/search/introducing-knowledge-graph-things-not/) — 문자열 검색에서 대상 중심 검색으로 관심이 확장된 배경.
- [Wikidata 진술](https://www.wikidata.org/wiki/Help:Statements) — 값에 한정어·출처·순위를 붙이는 구조.
- [Wikidata SPARQL 튜토리얼](https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial) — 직접 관계와 진술 노드를 조회하는 차이.

- [Apple — Growing and Serving Large Open-domain Knowledge Graphs](https://machinelearning.apple.com/research/open-domain-knowledgegraphs) — 대상과 웹 콘텐츠의 연결.
- [LinkedIn — Building the LinkedIn Knowledge Graph](https://www.linkedin.com/blog/engineering/knowledge/building-the-linkedin-knowledge-graph) — 사람·직무·스킬의 표준화와 검증.
- [Amazon — COSMO](https://www.amazon.science/blog/building-commonsense-knowledge-graphs-to-aid-product-recommendation) — 사용 목적 관계 생성과 품질 관리.
- [Siemens — The AI context layer](https://blogs.sw.siemens.com/rapidminer/ai-context-layer-knowledge-graph/) — 산업 데이터의 의미 연결.
- [Elsevier — AstraZeneca 사례](https://www-prod.elsevier.com/resources/astrazeneca-epimap-case-study) — 연구 근거를 연결한 표적 탐색.

## 5주차 · 트리플 추출과 저장

- [RDFS — W3C](https://www.w3.org/TR/rdf-schema/) — 클래스·속성·domain/range의 의미.
- [JSON-LD 1.1 — W3C](https://www.w3.org/TR/json-ld11/) — JSON 키와 ID를 RDF의 의미에 연결하기.
- [Neo4j MERGE](https://neo4j.com/docs/cypher-manual/current/clauses/merge/) — 식별자를 기준으로 반복 적재하는 방법과 유일성 주의점.
- [Cypher 가변 길이 경로](https://neo4j.com/docs/cypher-manual/current/patterns/variable-length-patterns/) — 관계를 여러 번 따라가는 질의.
- DDIA 2장 「데이터 모델과 질의 언어」, 4장 「부호화와 발전」 발췌 — 그래프 표현과 직렬화·스키마 변경 연결.
