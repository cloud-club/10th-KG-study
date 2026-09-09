# 읽을거리

주차별 참고자료. `## N주차` 아래 불릿 하나가 자료 하나 (`[제목](링크) — 한 줄 메모`).

## 1주차 · OT / 데이터 선정 · 개인정보

- [When to use Graphs in RAG: A Comprehensive Analysis for Graph RAG (ICLR 2026)](https://arxiv.org/abs/2506.05690) — GraphRAG가 일반 RAG에 자주 지는 이유와 이기는 조건. 엔티티가 느슨하게 연결된 코퍼스로는 그래프 이점을 검증할 수 없다 → "오프라인 활동이 반복되는 단톡방"을 데이터로 고른 근거
- [Balog & Kenter, Personal Knowledge Graphs: A Research Agenda (ICTIR 2019)](https://dl.acm.org/doi/10.1145/3341981.3344241) — 개인적으로 중요한 엔티티·관계만 담는 PKG의 정의와 연구 과제. 이 스터디 산출물의 이름표
- [Can LLMs interpret unstructured chat data on group decision-making? (arXiv 2601.05582)](https://arxiv.org/pdf/2601.05582) — 단톡방의 여행지 공동 결정 과정을 KG로 분석. "누가 제안했고 누가 어떻게 반응했나"를 잇는 데 KG가 자연스러운 틀이라는 설명
- [카카오 고객센터 — 대화 내용을 저장하고 싶어요](https://cs.kakao.com/helps_html/1073209354?locale=ko) — 기기별 내보내기 경로. '텍스트만 보내기'(txt, 메일 전송) vs '모든 메시지 내부저장소에 저장'
- [법률타임즈 — 카카오톡 단체방에 올린 개인정보, 모두 처벌될까?](https://www.thelawtimes.co.kr/news/articleView.html?idxno=1860) — 2025 대법원 판례 해설. 유효한 사전 동의 범위 안이면 '누설'이 아니다 → 방 멤버 동의 + 가명화를 첫 단계로 둔 이유
- [Gemini API Additional Terms of Service](https://ai.google.dev/gemini-api/terms_preview) — 무료 서비스(AI Studio, 무료 할당량)는 제출 콘텐츠를 제품 개선에 쓰고 사람이 검토할 수 있으며 개인정보를 넣지 말라고 명시. 카톡 데이터에 무료 티어를 쓰지 않은 이유
- [OpenAI — Your data (API data controls)](https://developers.openai.com/api/docs/guides/your-data) — API로 보낸 데이터는 명시적 옵트인 없이는 학습에 쓰이지 않음. 유료 API를 쓸 때의 기준

## 2주차 · grep에서 벡터까지 — 검색의 세 세대

- 『데이터 중심 애플리케이션 설계』 3장 저장소와 검색 (Martin Kleppmann, 위키북스) — 해시 인덱스 → SSTable/LSM → B-tree, 전문 검색·퍼지 색인, OLTP vs OLAP. Lucene(ES)과 Postgres가 다른 이유가 이 장 그대로. 노트 03
- [DDIA 2nd Edition, Chapter 4 "Storage and Retrieval" (O'Reilly, 2026)](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch04.html) — 2판(Kleppmann & Riccomini)에서는 같은 장이 4장으로 이동. 미리보기 첫 절만 무료
- [Elastic Blog — Practical BM25 Part 2: The BM25 Algorithm and its Variables](https://www.elastic.co/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables) — k1(TF 포화)·b(길이 정규화)가 점수에 미치는 영향을 예제 인덱스로 보여줌. BM25를 처음 볼 때 가장 친절한 글
- [Elastic Blog — Practical BM25 Part 3: Picking b and k1](https://www.elastic.co/blog/practical-bm25-part-3-considerations-for-picking-b-and-k1-in-elasticsearch) — 기본값 b=0.75, k1=1.2가 대부분 코퍼스에 맞고, 튜닝보다 분석기·쿼리 설계가 먼저라는 결론
- [Lucene BM25Similarity javadoc](https://lucene.apache.org/core/8_1_1/core/org/apache/lucene/search/similarities/BM25Similarity.html) — 실제 구현 식. IDF = log(1 + (docCount − docFreq + 0.5)/(docFreq + 0.5)), 기본값 k1=1.2, b=0.75. 출처는 Okapi at TREC-3 (1994)
- [Elasticsearch — Similarity (index settings)](https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity) — BM25 파라미터(k1, b, discount_overlaps)와 다른 유사도 모듈. 필드별로 유사도를 바꾸는 방법
- [Elasticsearch — Korean (nori) analysis plugin](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori) — mecab-ko-dic 기반 형태소 분석기. 노드마다 `elasticsearch-plugin install analysis-nori` 후 재시작. 공식 이미지에는 없음
- [Elasticsearch — nori_tokenizer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer) — `decompound_mode`(none / discard=기본 / mixed), `discard_punctuation`, `user_dictionary`(팀 용어를 명사로 등록). 노트 01
- [Elasticsearch — N-gram tokenizer](https://www.elastic.co/docs/reference/text-analysis/analysis-ngram-tokenizer) — `min_gram`/`max_gram`, `index.max_ngram_diff`. 분담 과제 "nori vs n-gram"의 반대편 재료
- [Malkov & Yashunin, Efficient and robust ANN search using Hierarchical Navigable Small World graphs (arXiv 1603.09320 / TPAMI 2018)](https://arxiv.org/abs/1603.09320) — 다층 근접 그래프로 로그 스케일 근사 최근접 검색. M, efConstruction, ef의 의미. 노트 02
- [pgvector README](https://github.com/pgvector/pgvector) — `<->` L2, `<#>` 음의 내적, `<=>` 코사인 거리, opclass와 연산자 매칭, HNSW 옵션(m=16, ef_construction=64, `hnsw.ef_search`=40), 인덱스 차원 제한 2,000(halfvec 4,000), 0.8의 iterative scan
- [pgvector HNSW on Postgres 18 tuning tutorial (Nerd Level Tech)](https://nerdleveltech.com/pgvector-hnsw-postgres-18-production-tuning-tutorial) — `ef_search` 대비 재현율 측정, halfvec 양자화, 필터 질의에서 `hnsw.iterative_scan='relaxed_order'`가 필요한 상황. 실습 그다음 단계용
- [nlpai-lab/KURE — 한국어 검색 특화 임베딩](https://github.com/nlpai-lab/KURE) — bge-m3를 한국어 질의-문서 쌍으로 파인튜닝, 1024차원, 시퀀스 8192, MIT. 실습 임베딩 모델. `SentenceTransformer("nlpai-lab/KURE-v1")` 한 줄로 로드
- [Reimers & Gurevych, Sentence-BERT (EMNLP 2019)](https://arxiv.org/abs/1908.10084) — bi-encoder로 문장 하나를 벡터 하나에 담는 방식의 출발점. 오늘 임베딩 모델의 조상
- [Postgres 18 Docker Silently Ignores Your Named Volume (RD Blog)](https://rdiachenko.com/posts/databases/postgresql/postgres-18-docker-silently-ignores-your-named-volume/) — 실습 트러블슈팅. PG18 이미지부터 PGDATA가 `/var/lib/postgresql/18/docker`로 바뀌어 볼륨을 `/var/lib/postgresql`에 마운트해야 함
- [Elasticsearch — Bootstrap checks](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/bootstrap-checks) — 실습 트러블슈팅. `discovery.type=single-node`면 부트스트랩 체크를 피하므로 Colima 기본 VM에서도 기동됨

## 3주차 · 하이브리드 검색 (미리 볼 것)

- [Cormack, Clarke & Buettcher, Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods (SIGIR 2009)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) — RRF 원 논문. 점수 대신 순위를 합치는 이유(1/(k+rank), k=60). 실습 "BM25 ∩ 벡터 = 1개"의 다음 단계
- [Elasticsearch — RRF retriever](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/rrf-retriever) — ES 안에서 BM25와 kNN을 RRF로 합치는 내장 기능. 직접 구현과 비교용
