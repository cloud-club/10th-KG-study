# W6 실습 — 내 게시물에 맞는 콘텐츠를 찾는 GraphRAG

## 실습 목표와 범위

“내 게시물로 만들 만한 주제가 있어?”라는 질문에 기존 글·관심 분야·참고 글을 연결해 답하도록 v1에 그래프 리트리버를 추가했다. 같은 질문으로 검색 결과와 답변을 비교하고, 별도로 Text2Cypher를 실행했다.

## v1과 v2의 차이

| 구성 | v1: 하이브리드 검색 | v2: 그래프 결합 |
| --- | --- | --- |
| 공통 검색 | W3 Nori BM25 + multilingual-e5-small + RRF | 동일한 검색 결과 사용 |
| 단순 질문 | 상위 5개 캡션 | 상위 시작 게시물을 유지하며 주제·분야 연결로 확장 |
| 다중 홉 | 질문과 비슷한 게시물 | 내 글의 주제 → 관심 분야 → 다른 세부 주제의 참고 글 |
| 추천 | 검색된 캡션 | 계정 관심 분야와 참고 글 연결, 기존 내 Topic과 비교 |
| 전체 집계 | 상위 K개로 전체 수를 확정할 수 없어 보류 | 비교 범위 전체를 Cypher로 집계 |

```text
질문 → BM25 + 벡터 검색 → RRF
  └→ 질문의 표현과 그래프 주제·분야로 검색 경로 선택
       ├─ 단순 검색: 시작 게시물 → 연결 게시물
       ├─ 다중 홉: 내 글 → Topic → InterestArea ← Topic ← 참고 글
       ├─ 추천: Profile → 관심 분야 ← 참고 글의 Topic
       └─ 집계: 비교 범위 전체의 OwnPost·Topic 조회
            ↓
     캡션 + 관계 근거 → 답변 생성 → 근거 검토
```

라우터는 질문 표현과 현재 그래프의 주제·분야를 사용한다. 평가용 질문 ID·정답 문서 ID는 검색 경로를 결정하는 데 사용하지 않는다. 규칙 기반으로 지원하는 표현을 구분하므로 모든 자연어 질문을 처리하는 범용 플래너는 아니다.

`COVERS_TOPIC`은 캡션 원문 근거가 있는 관계다. v2는 선택한 게시물의 `Project`·`Feature`·`Concept` 관계도 원문 Evidence와 대조해 이름과 기능을 문맥에 넣는다. `IN_AREA`는 사람이 검토한 분야 분류이고, `INTERESTED_IN`은 사용자가 설정한 관심사다. 답변에서도 이 출처를 구분한다. 

## 실행 방법

저장소 루트에서 실행한다. Elasticsearch·PostgreSQL·Neo4j가 실행 중이어야 한다. `NEO4J_PASSWORD`를 환경 변수로 설정하고, OpenAI 설정은 W3 `.env`의 `OPENAI_API_KEY`, `OPENAI_MODEL`을 사용한다.

```bash
source members/kdyann/labs/01-instagram-search/.venv/bin/activate

# 비교 데이터를 고정하고 전용 검색 인덱스를 만든다.
python members/kdyann/labs/06-graphrag/src/prepare_comparison.py --index

# 동일한 8개 질문으로 실제 답변까지 비교한다. API 비용 발생.
python members/kdyann/labs/06-graphrag/src/compare_retrievers.py \
  --generate-answers --capture-raw \
  --output data/kdyann/processed/graphrag_comparison/comparison.json

# 내 질문으로 추천받는다.
python members/kdyann/labs/06-graphrag/src/compare_retrievers.py \
  --query "내 게시물로 만들 만한 주제가 있어? 내 기존 글과 관심 분야를 바탕으로 참고 글과 추천 이유를 알려줘." \
  --scope all --generate-answers \
  --output data/kdyann/processed/graphrag_comparison/adhoc.json

# 자유 Text2Cypher 생성 → 검증 → 허용된 읽기 질의 실행
python members/kdyann/labs/06-graphrag/src/text2cypher.py \
  --questions members/kdyann/labs/06-graphrag/evaluation_questions.json \
  --output data/kdyann/processed/graphrag_comparison/text2cypher.json
```

답변 생성 없이 검색만 확인하려면 `--generate-answers --capture-raw`를 생략한다. 실습용 인덱스·테이블은 `kdyann_hybrid_w6_posts`다. 비교 코드는 Neo4j를 조회만 하며, 기존 웹 채팅에는 비교 기능을 붙이지 않았다. 위 CLI가 이번 v1/v2 실행 진입점이다.

## 최종 검색 결과

2026-10-08 로컬 Elasticsearch·pgvector·Neo4j에서 실행했다. Recall@5는 정답 문서 중 상위 5개에 포함된 비율.

| 질문 | v1 Recall@5 | v2 Recall@5 |
| --- | ---: | ---: |
| 디자인 시스템에 사용한 두 도구 | 1.00 | 1.00 |
| 외계인 모리 공부 앱 이름 | 1.00 | 1.00 |
| 내 오픈소스 기여와 같은 분야의 참고 글 | 0.33 | 1.00 |
| 내 AI 글과 연결되는 다른 주제 참고 글 | 0.50 | 1.00 |
| 내 게시물로 만들 만한 주제와 참고 글 | 0.00 | 1.00 |
| 아직 올리지 않은 AI 주제와 참고 글 | 0.00 | 1.00 |

집계 2개는 Recall을 계산하지 않는다. v2는 비교 범위 전체를 조회해 야구 게시물 7개, 가장 많이 연결된 주제 야구·7개를 확인했다. v1은 상위 5개만으로 전체 집계를 확정할 수 없어 보류한다.

## 답변과 추천 결과

최종 실행은 2026-10-08 19:04 KST에 완료했다. 검색된 근거에 참고 글이 없으면 연결·추천을 확정하지 않도록 두 버전에 동일한 보류 기준을 적용했다.

| 질문 | v1 실제 답변 | v2 실제 답변 |
| --- | --- | --- |
| 디자인 도구 | Pen.dev + Claude Code | Pen.dev + Claude Code |
| 공부 앱 이름 | 소개 문구와 스터디언을 혼용 — 부분정확 | 스터디언 |
| 오픈소스 분야 다중 홉 | 참고 글 부재로 보류 | 보안 도구·Python 학습을 개발 분야로 연결. `partial` |
| AI 분야 다중 홉 | 참고 글 부재로 보류 | AI 도구 활용 글과 AI 에이전트 운영 참고 글 연결 |
| 야구 게시물 수 | 전체 집계 보류 | 7개 |
| 가장 많이 연결된 주제 | 전체 집계 보류 | 야구, 7개 |
| 내 게시물로 만들 만한 주제 | 참고 글 부재로 보류 | 보안 도구·Python 학습·AI 에이전트 운영 제안. `partial` |
| 아직 올리지 않은 AI 주제 | 참고 글 부재로 보류 | AI 에이전트 운영 제안. `partial` |

v2의 모델·코드 상태는 `answered` 5개, `partial` 3개였다. 부분 답변에도 추천 후보와 근거는 있지만, 개발 다중 홉에서는 질문에 요구되지 않은 앱 개발 경로의 부족을, 일반 추천에서는 추가 이력의 필요성을, AI 추천에서는 구체적 제작 방식의 부족을 미해결로 남겼다. 검색 성공과 답변 완결성은 구분해서 봐야 한다.

v1 공부 앱 답변은 모델 검토가 `answered`로 통과시켰지만, 실제 문장은 소개 문구를 이름이라고 부른 뒤 스터디언을 덧붙여 명칭이 혼동된다. 위 표에는 수동 대조 결과를 반영했다. 따라서 상태값을 그대로 정답률로 계산하지 않았다.

추가 수동 검토에서는 v2 AI 다중 홉 답변이 관계 설명에 그래프 경로를 직접 인용하지 않은 점, 일반 추천의 부가 문장이 캡션의 디자인 내용을 프로필의 “디자인 관심 분야”처럼 표현한 점도 확인했다. 실제 설정된 관심 분야는 개발·앱·AI·게임·야구다. 아래에는 근거로 확인된 세 참고 주제만 정리했다. 관계 인용을 빠뜨리거나 캡션 주제와 설정된 관심사를 혼동하는 문제는 답변 생성·검토의 남은 한계다.

v2에서 찾은 추천 후보는 다음과 같다.

| 후보 주제 | 내 계정과의 연결 | 콘텐츠로 바꾸는 방향 |
| --- | --- | --- |
| 오픈소스 보안 도구 | 개발 관심 분야·내 오픈소스 기여 글 | 개발자가 살펴볼 보안 도구 소개 |
| Python 학습 | 개발 관심 분야·내 개발 게시물 | Python 학습 노트나 입문 자료 소개 |
| AI 에이전트 운영 | AI 관심 분야·내 AI 도구 활용 글 | 에이전트의 도구 사용·상태 관리·실패 처리 소개 |

표의 콘텐츠 방향은 참고 글을 활용하는 아이디어다. 내가 해당 도구를 직접 써봤다는 사실이나 영상 내용을 확인했다는 뜻은 아니다.

## Text2Cypher 결과

같은 8개 질문에 `gpt-4.1-mini`가 Cypher를 자유 생성하도록 했다. 생성문을 그대로 실행하지 않고 허용된 읽기 문법을 검증한 뒤 매개변수가 있는 질의로 변환한다. 쓰기·프로시저 호출·알 수 없는 관계·추가 조건은 허용하지 않는다. 실행계획의 읽기 유형, 5초 제한, 반환 행 상한도 확인한다.

| 질문 유형 | 결과 | 확인 내용 |
| --- | --- | --- |
| 야구 게시물 수 | 실행 성공 | 7개 |
| 가장 많이 연결된 주제 | 실행 성공 | 야구, 7개 |
| 다중 홉 2개·추천 2개 | 검증 거절 | 생성문이 현재 안전하게 지원하는 질의 형태를 벗어남 |
| 도구·앱 이름 단순 질문 2개 | 지원 불가 응답 | 해당 생성에서 지원 가능한 질의를 만들지 못함 |

총 실행 성공 2개, 검증 거절 4개, 지원 불가 2개다. 집계 두 질의는 같은 모델 출력에 문법 검증을 적용해 실행한 결과이며, 원래 생성문과 실제 실행문을 모두 기록했다. `rejected`가 전부 Cypher 문법 오류라는 뜻은 아니다. 반대로 실행에 성공했다는 이유만으로 모든 자연어 질문의 의미를 정확히 반영한다고 볼 수도 없다.

## 해석과 결과 파일

이 데이터에서는 단순 정보 검색은 v1으로도 정답 자료를 찾았지만, 내 글과 참고 글의 관계를 요구하는 질문에서는 v2가 필요한 참고 글을 더 잘 남겼다. 전체 집계는 상위 검색 결과를 세는 대신 전체 범위를 조회해야 했다. 핵심은 그래프를 많이 확장하는 것보다 질문에 맞는 시작점과 경로를 고르고, 필요한 참고 글을 최종 문맥에 남기는 것었다.

- `comparison.json`: v1/v2 검색 문서·관계 경로·집계·실제 답변·근거 검토·프롬프트.
- `text2cypher.json`: 자유 생성문·검증 결과·실행문·조회 결과.
- `corpus/`, `index_metadata.json`: 고정한 비교 자료와 색인 정보.

검색 시간은 공통 하이브리드 검색 시간에 v2의 그래프 조회 시간을 더해 기록한다. 최초 모델 로딩 등이 포함될 수 있어 운영 지연시간 벤치마크로 해석하지 않는다.

## 기존 그래프 확인과 데이터 갱신

Neo4j Browser는 <http://127.0.0.1:7474/browser/>에서 연다.

- 중심 계정: `Profile`의 `junyounge`.
- 관심 분야: `InterestArea`의 개발·앱·AI·게임·야구.
- 게시물: 내 글 `OwnPost`, 참고 글 `ReferencePost`. 내 글 번호는 `own_post_numbers.json`으로 고정한다.
- 원문 주제·프로젝트·기능·개념: `Topic`, `Project`, `Feature`, `Concept`.
- 원문 근거: `Assertion`, `Evidence`. 관심 분야 분류는 `interests.json`의 수동 검토 설정이다.

브라우저에서 다음 파라미터 설정을 먼저 실행하고, [관심 분야 개요 질의](src/queries/01_graph_overview.cypher)의 `MATCH`부터 마지막 `RETURN`까지 실행한다. [전체 내 게시물 질의](src/queries/03_all_own_posts.cypher)도 사용할 수 있다.

```text
:param {profile_id: 'junyounge', as_of: datetime()}
```

`:style`에서 [browser.grass](browser.grass)를 적용하면 게시물 번호와 유형별 색상을 볼 수 있다. 개요는 최근 7일 참고 글과 야구 글 최대 3개만 표시하므로, 전체 데이터와 화면에 나온 수는 다를 수 있다.


```bash
python members/kdyann/labs/06-graphrag/src/build_reviewed_input.py
python members/kdyann/labs/05-content-graph/src/pipeline.py \
  --documents data/kdyann/processed/content_graph/w6-reviewed-input/documents.jsonl \
  --predictions data/kdyann/processed/content_graph/w6-reviewed-input/predictions.jsonl \
  --limit-own 14 --limit-reference 3 --as-of 2026-10-06 \
  --output data/kdyann/processed/content_graph/w6-reviewed
python members/kdyann/labs/06-graphrag/src/persist_unified.py \
  --output data/kdyann/processed/content_graph/w6-reviewed --target both
```

위 명령의 개수와 기준일은 이번 검토본 기준이다. 새 검토본에서는 검토 목록·개수·기준일을 맞춰야 한다. 비교 데이터를 바꿨다면 `prepare_comparison.py --index`를 다시 실행하고 이전 결과와 구분해 저장한다.

기존 후보 선택·대본 초안 웹 UI는 다음 명령으로 실행한다. 이 UI의 대본은 캡션 근거만 사용한다.

```bash
python members/kdyann/labs/06-graphrag/src/local_chat.py
```

## 검증

```bash
python -m unittest discover -s members/kdyann/labs/06-graphrag/tests -v
python -m unittest discover -s members/kdyann/labs/03-hybrid-search/tests -v
```

## 다음에 할 것

- 게시물 링크에서 접근 가능한 영상을 분석해 음성 전사·화면 자막·주요 장면을 시간 정보와 함께 추출한다. 현재는 캡션만 사용하므로 영상에서 실제로 보여준 행동이나 기능을 알 수 없다.
- 추출 결과를 게시물과 연결된 근거로 저장하고, 추천 이유와 대본 초안이 캡션·영상 중 어느 자료에 기반했는지 표시한다. 시간대가 필요한 질문은 해당 장면의 근거를 확인한 뒤 답하도록 한다.
