# sunghyun

안녕하세요! 클클 10기에 새로 합류한 이성현입니다.
이번 스터디에서 다른 분들과 함께 배우고, 공부한 내용을 꾸준히 기록하겠습니다.

## 스터디 목표

KG, Graph 개념들을 이해하고 RAG 관련된 내용들을 최대한 많이 습득하고자합니다.
PostgreSQL, Elasticsearch, Docker를 직접 사용해 데이터 저장과 검색 과정을 이해하고, 최종적으로 Notion 데이터를 활용한 지식 그래프와 개인 에이전트를 만드는 것이 목표입니다.

## 폴더 구조

```text
members/sunghyun/
├── README.md                  # 자기소개, 목표, 진행 현황
├── readings.md                # 주차별 읽을거리·참고자료
├── notes/                     # 학습 정리
│   ├── 01-knowledge-graph-and-ontology.md
│   ├── 02-search-methods.md
│   ├── 03-hybrid-rag-and-evaluation.md
│   └── 04-knowledge-graph-background.md
├── labs/                      # 실습 기록과 코드
│   └── 01-search-lab/
│       ├── README.md           # 목표, 환경, 실행 방법, 결과
│       └── src/               # 검색·임베딩·RAG·평가 코드
│           ├── bm25_lab/      # Elasticsearch / BM25 실습
│           └── pgvector_lab/  # pgvector / HNSW 실습
└── assets/                    # 노트·실습에서 사용하는 스크린샷
```

- [주차별 읽을거리·참고자료](readings.md)
- 새 학습 정리는 `notes/NN-topic.md`, 새 실습은 `labs/NN-topic/README.md`와 `src/`에 기록한다.
- 작성 양식은 공용 [노트 템플릿](../../templates/note-template.md), [실습 템플릿](../../templates/lab-template.md), [읽을거리 템플릿](../../templates/readings-template.md)을 참고한다.

## 진행 현황

- 1주차: [RAG와 지식 그래프 기초 정리](notes/01-knowledge-graph-and-ontology.md)
- 2주차: [청킹·BM25·벡터 검색·HNSW 정리](notes/02-search-methods.md)
- 실습: [검색의 세 세대 비교](labs/01-search-lab/README.md) — 전체 2,685개 청크 검색, JSON/DB 결과 비교, HNSW 실행 계획 확인
- 3주차: [하이브리드 검색, RAG와 Recall 평가](notes/03-hybrid-rag-and-evaluation.md) — RRF 결합, HNSW 검색, 로컬·OpenRouter 답변 생성과 검색 평가 실습. 다중 홉 질문은 후속 과제로 남겼다.
- 4주차: [지식 그래프의 배경 — 온톨로지 변천사와 방법론](notes/04-knowledge-graph-background.md) — RDF·OWL·링크드 데이터, Wikidata 질의, 그래프 모델 비교, 팔란티어와 GraphRAG 이론 학습. 실제 W3 질문의 그래프 검증은 후속 과제다.
