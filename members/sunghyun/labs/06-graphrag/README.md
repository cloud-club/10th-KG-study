# 06. GraphRAG와 에이전틱 검색 비교

관련 노트: [6주차 학습 기록·실제 비교 결과](../../notes/06-graphrag-and-agentic-search.md).

회사 실습의 검색·그래프 확장·실행 기록 로직을 합성 데이터로 옮겼다. 공개 예제는 JSON 그래프를 사용하며 운영 실습의 Neo4j 전체 집계나 브라우저 UI를 그대로 배포한 것은 아니다. 샘플은 W5 예제와 같은 ID를 사용한다.

## 준비

Python 3.10 이상이면 코드 자체는 표준 라이브러리로 실행된다. Ollama와 `qwen3-embedding:0.6b`가 필요하다. 답변은 기본 `qwen2.5:7b`를 쓴다.

GLM을 사용할 때는 아래 환경 변수를 설정한다. 키는 셸에서 별도로 주입하고 파일이나 Git에 넣지 않는다.

- `LLM_API_KEY`: 모델 API 키.
- `LLM_BASE_URL`: 기본 `https://api.mangoboost.io/v1`.
- `LLM_MODEL`: 기본 `zai-org/GLM-5.2`.

선택 변수는 `OLLAMA_URL`, `OLLAMA_MODEL`, `EMBED_MODEL`이다.

## 1. 동일 질문 v1/v2

```bash
python src/compare.py 'v0.1.0 1차에서 어떤 케이스가 실패했고 어떤 빌드로 테스트했나?'
```

v1은 정확 벡터 검색+BM25+RRF 청크만, v2는 같은 검색 결과에 양방향 3-hop 그래프를 추가한다. `outputs/comparison.json`에 답변·컨텍스트·시간·토큰을 저장한다. Top-k와 제한된 서브그래프만으로 전체 집계를 보장하지 않는다. 이 예제의 시간은 답변 생성 구간이며 아래 실제 실험의 전체 시간과 다르다.

## 2. 그래프 없이 에이전틱 검색 / 그래프 도구 추가

```bash
python src/agentic.py 'v0.1.0 1차에서 어떤 케이스가 실패했고 어떤 빌드로 테스트했나?'
```

두 방식 모두 모델이 청크 검색·원문 읽기·종료를 선택한다. 그래프 방식에는 ID 기준 이웃 조회 도구를 추가한다. 조회 예산은 각각 5회, 모델 호출은 최대 6회다. `outputs/agentic.json`에 각 도구 요청과 받은 결과를 저장한다.

운영 실습에서는 그래프 도구가 조회 전용 Cypher를 실행했다. 이 공개 예제는 임의 Cypher를 실행하지 않고 JSON 그래프의 1-hop 도구로 제한했다. API 응답이 JSON이 아니거나 도구 예산을 넘으면 오류를 기록한다. 실패도 결과로 확인한다.

## 3. Cypher 생성

```bash
python src/text2cypher.py 'v0.1.0 실패 Case Run의 케이스 이름과 실행 차수는?'
python src/text2cypher.py '관련 커밋이 있으니 이슈가 수정 완료인가?'
```

생성 결과는 `outputs/generated-cypher.json`에 저장한다. 생성된 문자열을 자동 실행하지 않는다. W5의 라벨·관계와 맞는지 검토한다. 두 번째 질문은 참조 관계만으로 완료를 판단할 수 없으므로 `answerable:false`가 적절하다.

## 기준 답과 기록

샘플의 정답은 `case:1` 실패, Test Run `run:1` 1차, 파일 `file:1`, 릴리즈 `v0.1.0`이다. 이것은 합성·시뮬레이션 데이터다.

실제 회사 코퍼스로 실행한 에이전틱 실험은 별도이며, 그래프 없이 4/9·그래프 도구 추가 3/9였다. 도구별 토큰·시간·사실 항목 점수는 `measured-summary.json`에 원문 없이 보존했다. 결과와 범위 오류는 [학습 노트](../../notes/06-graphrag-and-agentic-search.md)에 기록했다. 확정된 API 단가가 없어 화폐 비용은 계산하지 않았다.

게시 전 검색의 오프라인 스모크 검증, 그래프 확장, Python 구문 검사를 실행했다. 새 공개 코드의 전체 GLM·Ollama 답변 호출은 재실행하지 않았다. 회사 실습에서 이미 측정한 수치를 공개 예제의 성능으로 주장하지 않는다.
