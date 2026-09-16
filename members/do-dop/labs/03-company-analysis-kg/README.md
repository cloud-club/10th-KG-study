# 기업분석 지식 그래프

삼성전자와 SK하이닉스의 공식 뉴스룸 자료 10건, OpenDART 공시 관련 섹션 5건을 같은 JSON 구조로 정리한다.

## 데이터 구조

```json
{
  "id": "newsroom_001",
  "title": "문서 제목",
  "date": "2026-07-30",
  "source": "newsroom",
  "company": ["삼성전자"],
  "text": "검색에 사용할 본문",
  "url": "원문 URL"
}
```

- `source`: `newsroom` 또는 `dart`
- `text`: 뉴스룸은 실제 기사 본문, DART는 HBM·AI·반도체·투자·실적 키워드와 가까운 섹션
- `url`: 원문을 확인할 수 있는 공식 페이지

## 수집 방식

### 뉴스룸

RSS가 아니라 파이썬 표준 라이브러리인 `urllib.request`로 `config/newsroom_sources.json`에 등록한 공식 URL의 HTML을 내려받는다. 삼성전자 뉴스룸의 `single_contents`, SK하이닉스 뉴스룸의 `post-contents` 영역에서 본문만 추출한다. 이미지, 스크립트, 스타일 같은 검색에 필요하지 않은 요소는 제외한다.

현재 URL 10개는 HBM, AI 반도체, 투자, 실적을 비교하기 위해 직접 선정한 고정 실험 데이터셋이다. 같은 자료로 검색 결과를 반복해서 비교하기 위한 방식이며, 새로운 뉴스가 자동으로 추가되지는 않는다.

### OpenDART

`urllib.request`로 OpenDART 원문 API를 호출한다. `config/dart_filings.json`에는 실험에 사용할 공시 5건의 접수번호를 고정해 두었다. 접수번호는 삼성전자와 SK하이닉스의 공시 목록을 조회한 뒤 분기·반기보고서와 시설투자 공시를 직접 선정한 것이다.

공시 원문에서는 HBM, AI, 반도체, 투자, 실적과 관련해 직접 정한 키워드가 많이 등장하는 연속 문단을 선택한다. 이는 작은 실험 데이터셋을 만들기 위한 임시 규칙이며, 실제 KG 파이프라인에서는 기업 코드와 공시 유형을 기준으로 새 공시 목록과 접수번호를 자동으로 수집해야 한다.

## 실행

저장소 루트의 `.env`에 `DART_API_KEY`를 입력한 뒤 실행한다.

```bash
python3 members/do-dop/labs/03-company-analysis-kg/src/collect_newsroom.py
python3 members/do-dop/labs/03-company-analysis-kg/src/collect_dart.py
python3 members/do-dop/labs/03-company-analysis-kg/src/merge_documents.py
python3 members/do-dop/labs/03-company-analysis-kg/src/chunk_documents.py
```

결과는 Git에 올리지 않는 `data/do-dop/company-analysis-kg/` 아래에 생성된다.

```text
data/do-dop/company-analysis-kg/
├── raw/
│   ├── newsroom/documents.jsonl
│   └── dart/documents.jsonl
└── processed/
    ├── documents.jsonl
    └── chunks.jsonl
```

뉴스룸 자료의 `text`에는 공식 페이지에서 추출한 실제 기사 본문이 들어간다. 사람이 정리한 짧은 설명은 `summary`에 따로 보존한다.

## 청킹

`chunks.jsonl`은 뉴스와 DART를 같은 규칙으로 나눈 검색용 데이터다. 긴 문서 전체를 하나의 검색 단위로 사용하면 질문과 관련 없는 내용까지 섞여 실제 정답 부분을 찾기 어렵다.

- BM25는 관련 단어가 밀집된 부분을 찾기 쉬워진다.
- 벡터 검색은 서로 다른 여러 주제가 하나의 임베딩에 섞이는 일을 줄일 수 있다.
- RAG에서는 필요한 부분만 LLM에 전달해 입력 길이와 불필요한 정보를 줄일 수 있다.

기본값은 최대 800자이며 문단 경계를 우선한다. 문맥이 청크 경계에서 갑자기 끊기지 않도록 이전 문단 하나를 다음 청크에 다시 포함한다. 800자는 확정된 정답이 아니라 초기 실험값이므로, 이후 검색 결과를 보며 다른 크기와 비교할 수 있다.

## 검색 실행

### grep

JSONL 전체가 아니라 각 청크의 `text` 필드에서 고정 문자열을 찾는다. 자연어 질문 전체를 그대로 검색한 결과와, 사람이 고른 `grep_query`를 검색한 결과를 함께 기록한다. 이를 통해 grep 자체는 질문의 의미를 이해하지 못하고 적절한 검색 문자열을 사람이 골라야 한다는 점을 확인할 수 있다.

```bash
python3 members/do-dop/labs/03-company-analysis-kg/src/search_grep.py "HBM4E 12단" --show
python3 members/do-dop/labs/03-company-analysis-kg/src/run_grep_queries.py
```

### Elasticsearch BM25

2주차와 같은 Nori 분석기를 사용한다. 본문뿐 아니라 제목도 검색하고 제목 일치에는 두 배의 가중치를 준다.

```bash
python3 members/do-dop/labs/03-company-analysis-kg/src/index_es.py --recreate
python3 members/do-dop/labs/03-company-analysis-kg/src/search_es.py \
  "AMD의 AI 가속기에 고대역폭 메모리를 공급하는 회사는?" --show
python3 members/do-dop/labs/03-company-analysis-kg/src/run_es_queries.py
```

### pgvector

```bash
cd members/do-dop/labs/03-company-analysis-kg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 src/index_pgvector.py --recreate
python3 src/search_pgvector.py \
  "AMD의 AI 가속기에 고대역폭 메모리를 공급하는 회사는?" --show
python3 src/run_pgvector_queries.py
```

세 방식의 일괄 실행 결과는 `data/do-dop/company-analysis-kg/results/`에 JSONL로 저장된다. 각 결과에는 상위 청크 ID와 `Hit@5`, `Recall@5`가 포함된다.

검색 실습에서 반복되는 JSONL 입출력, Elasticsearch HTTP 요청, Ollama 임베딩, 평가 지표 계산은 `members/do-dop/search_common/`에 분리했다. 데이터 필드와 청킹 규칙은 실습마다 다르므로 각 실습에 남겨둔다.

현재 10개 질문의 초기 결과는 다음과 같다.

| 검색 방식 | 평균 Hit@5 | 평균 Recall@5 |
|---|---:|---:|
| grep: 자연어 질문 전체 | 0% | 0% |
| grep: 사람이 고른 핵심 문자열 | 100% | 83.3% |
| BM25 | 100% | 96.7% |
| Vector Search | 100% | 100% |

데이터셋이 57개 청크로 작고 평가 질문도 10개뿐이므로 이 수치만으로 검색 방식의 일반적인 우열을 결론 내릴 수는 없다. 현재 결과는 같은 데이터와 정답셋으로 구현이 동작하는지 확인한 기준선이다.

## 검색 평가 질문

`config/evaluation_queries.json`에는 grep, BM25, 벡터 검색, 하이브리드 검색에 공통으로 사용할 질문 10개가 들어 있다.

- `keyword`: 제품명, 시설명, 수치처럼 정확한 단어가 중요한 질문
- `semantic`: 원문의 표현을 바꿔 물어보는 질문
- `multi_hop`: 서로 다른 문서의 정보를 함께 찾아야 답할 수 있는 질문

`relevant_document_ids`는 정답 원문, `relevant_chunk_ids`는 정답 내용이 실제로 들어 있는 검색 청크다. 검색 결과의 상위 k개 안에 이 청크가 포함됐는지 확인하면 Recall@k를 계산할 수 있다.

## 이후 작업

- [ ] OpenDART에서 기업 코드와 공시 유형으로 새 공시 목록 및 접수번호 자동 수집
- [ ] 공식 뉴스룸의 새 기사 URL 자동 탐색
- [ ] 청크 크기와 중복 범위를 바꿔 검색 품질 비교
- [ ] grep, BM25, 벡터 검색 결과 비교
- [ ] BM25와 벡터 검색 결과를 RRF로 결합
- [ ] 문서에서 기업, 제품, 인물, 투자, 사건과 관계 추출
- [ ] 추출한 개체와 관계를 지식 그래프에 저장
