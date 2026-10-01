# Notion 검색·평가·지식 그래프 실습

프로젝트 Notion에서 필요한 근거를 찾는 검색 실험과, 사실·관계를 구조화하는 그래프 실험을 진행했다.

## 진행 결과

| 실습 | 실행 결과 | 기록 |
|---|---|---|
| 전처리·텍스트 적재 | 628개 Markdown → 1,477개 청크 | [적재와 BM25 RAG](03-notion-ingest/README.md) |
| 키워드·벡터·하이브리드 | 공통 스냅샷 1,369개, 질문 10개 비교 | [검색 평가](04-hybrid-evaluation/README.md) |
| 개인 데이터 질의 | BM25·벡터·RRF 선택 후 Gemini 답변 | [검색 평가 실행](04-hybrid-evaluation/README.md#실행) |
| 관계 추출 | 첫 실행 7개 후보, 문맥 보강 실행 5개 후보 | [관계 추출](05-triple-extraction/README.md) |
| 그래프 적재 | 근거 대조 후 15개 엔티티·20개 관계·29건 근거 | [그래프 적재](05-triple-extraction/README.md#저장-결과) |
| 조회·시각화 | 1-hop, `1..3` 경로, 조건 질의, 브라우저 화면 | [Cypher 조회](05-triple-extraction/README.md#cypher-조회) |

평가 라벨과 그래프의 의미 검토는 AI 보조 초안이며 작성자 검토가 남아 있다. 코드 실행·건수·파일 파싱·중복 방지 검증과 의미적 정답 판단을 구분한다.

## 전체 흐름

```text
Notion → 전처리·청킹
           ├─ Elasticsearch BM25 ─┐
           ├─ 로컬 임베딩 → pgvector ─┴─ RRF → 근거 → Gemini 답변
           └─ 선택한 문서 → LLM 관계 추출 → 근거 검토
                                  ├─ Postgres 엔티티·관계·근거
                                  ├─ Turtle / JSON-LD
                                  └─ Neo4j → Cypher → 브라우저
```

그래프를 답변 생성 루프의 리트리버로 연결하는 GraphRAG는 W6 범위다. 이번에는 그래프의 관계 질의까지 실행했다.

## 결과를 다시 보는 순서

저장소 루트에서 가상환경을 활성화한다. 환경 설치는 [검색 실험 README](04-hybrid-evaluation/README.md#실행)를 따른다.

### 1. 검색 결과와 점수

```bash
python members/Yeongeunn/labs/03-notion-ingest/src/notion_search.py count
python -m json.tool data/Yeongeunn/evaluation/results.json
```

검색 결과 파일의 `summary`는 BM25 0.60, 벡터 0.70, RRF 0.55다. 모두 같은 10문항의 **지정 근거 Recall@5**이며 답변 정답률이 아니다. q05의 대체 근거 사례처럼 라벨의 범위가 점수에 영향을 준다.

### 2. 질문 하나의 검색·답변

```bash
python members/Yeongeunn/labs/03-notion-ingest/src/notion_search.py search \
  --query '<질문>'
python members/Yeongeunn/labs/04-hybrid-evaluation/src/search_lab.py ask \
  --method rrf --query '<질문>'
```

첫 명령은 로컬 BM25 검색이다. 두 번째는 질문 임베딩·BM25·벡터 검색·RRF를 수행하고 근거 5개를 Gemini에 보내므로 새 호출이 발생한다. 기존 답변은 `data/Yeongeunn/evaluation/answers/`에서 다시 읽을 수 있다.

### 3. 추출 결과와 저장 결과

```bash
python -m json.tool data/Yeongeunn/kg-v0/run.json
python -m json.tool data/Yeongeunn/kg-v0/graph-run.json
python members/Yeongeunn/labs/05-triple-extraction/src/graph_lab.py query
```

첫 실행의 후보 7개가 검토 없이 그대로 20개가 된 것이 아니다. 원문과 소속 문맥을 대조해 관계를 보완하고 정책을 나눈 결과다. 이 변경 이력은 로컬 `graph-reviewed.json`에 남겼다.

### 4. 그래프 화면

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory data/Yeongeunn/kg-v0
```

[로컬 그래프](http://127.0.0.1:8765/graph.html)에서 연결과 근거를 확인한다. 이미 이 포트로 서버가 실행 중이면 명령을 다시 실행하지 않고 페이지를 열면 된다.

## 결과를 해석할 때 구분할 것

- **BM25 점수:** 한 질문에서 문서를 정렬하는 값. 정답률이 아니다.
- **Recall@5:** 필요한 근거 중 상위 5개에서 찾은 비율. 이번에는 지정 근거 기준의 파일럿 평가다.
- **RRF:** BM25·벡터의 순위를 합치는 방법. 이번 실험에서는 평균 점수가 오히려 낮아졌다.
- **RAG:** 찾은 근거로 답변을 생성하는 흐름. 근거를 잘 찾아도 대상을 잘못 연결할 수 있다.
- **닫힌 스키마:** 추출할 종류·관계·방향을 미리 제한한 약속.
- **Turtle:** RDF를 텍스트로 적는 문법. 모델이나 DB가 아니다.
- **Cypher:** Neo4j 그래프의 연결을 질의하는 언어.

## 남은 검토

- 지정 근거 외의 대체 근거를 평가셋에 추가하고 작성자 검토.
- 그래프의 정책·용어 통합과 문서 버전 차이 확인.
- 별도 개발 질문과 테스트 질문을 나눠 검색 설정 실험.

실험 결과를 저장소에 공유할 때는 코드·설정·집계·해석을 사용한다. 개인 문서와 인용문·질문별 결과·그래프 파일은 로컬 `data/Yeongeunn/`에 보관한다.
