# 읽을거리

주차별 참고자료와 읽을거리를 정리합니다.

## 2주차 · 검색의 세 세대

- [GNU grep 공식 매뉴얼](https://www.gnu.org/software/grep/manual/grep.html) — grep의 패턴 및 줄 단위 동작 확인
- [How full-text search works](https://www.elastic.co/docs/solutions/search/full-text/how-full-text-works) — 텍스트 분석, 역색인, BM25 검색 흐름
- [Similarity settings](https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity) — Elasticsearch의 기본 BM25 설정
- [nori analyzer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-analyzer) — 한국어 형태소 분석 구성
- [n-gram tokenizer](https://www.elastic.co/docs/reference/text-analysis/analysis-ngram-tokenizer) — 문자 조각 기반 토큰화 방식
- [Introduction to Information Retrieval, Chapter 6](https://nlp.stanford.edu/IR-book/pdf/06vect.pdf) — TF, DF, IDF, TF-IDF와 문서 길이 정규화
- [임베딩 공간과 정적 임베딩](https://developers.google.com/machine-learning/crash-course/embeddings/embedding-space?hl=ko) — 텍스트를 벡터로 표현하고 임베딩 공간의 거리로 의미 관계를 나타내는 방식
- [임베딩에서 유사도 측정](https://developers.google.com/machine-learning/clustering/dnn-clustering/supervised-similarity?hl=ko) — 코사인, 내적, 유클리드 거리의 차이
- [pgvector](https://github.com/pgvector/pgvector) — PostgreSQL의 벡터 자료형, 거리 연산자와 HNSW 인덱스 사용법
- [Efficient and Robust Approximate Nearest Neighbor Search Using Hierarchical Navigable Small World Graphs](https://arxiv.org/abs/1603.09320) — HNSW의 계층형 근접 그래프와 ANN 탐색 원리
