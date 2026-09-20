# 개체추출·임베딩·생성 모델의 역할

개체추출·임베딩·생성 모델은 입력과 출력, 담당하는 작업이 다르다. 같은 문서를 처리하더라도 어떤 결과가 필요한지에 따라 사용하는 모델과 평가 기준이 달라진다.

## 참고자료

- [개체명 인식이란? — IBM](https://www.ibm.com/think/topics/named-entity-recognition) — 규칙·학습·혼합 방식과 활용 사례를 설명하는 입문 글.
- [임베딩이란 무엇인가요? — IBM](https://www.ibm.com/kr-ko/think/architectures/rag-cookbook/embedding) — 한국어. 텍스트를 숫자로 표현해 검색에 사용하는 흐름.
- [대규모 언어 모델이란? — AWS](https://aws.amazon.com/ko/what-is/large-language-model/) — 한국어. 언어 모델의 학습과 활용을 설명하는 입문 자료.

## 한 문장을 세 모델이 처리하면

가상 회의록: “재시도 중 주문이 중복되는 것을 막기 위해 요청 ID를 저장하기로 했다.”

| 역할 | 물어보는 것 | 기대하는 출력 |
|---|---|---|
| 개체·개념 추출 | 이 문장에서 다루는 대상은? | `재시도`, `중복 주문`, `요청 ID`와 타입·원문 위치 |
| 관계·의사결정 추출 | 무엇 때문에 무엇을 결정했나? | 결정: 요청 ID 저장 / 이유: 중복 주문 방지 / 근거 구간 |
| 임베딩 | 이 내용과 비슷한 질문·문서는? | 의미 검색에 사용할 숫자 배열 |
| 생성 | “왜 요청 ID를 저장했어?”에 어떻게 답할까? | “중복 주문을 막기 위한 결정입니다 [1].” |

개체만 찾으면 이유와 결정의 연결은 아직 없다. **개체추출과 관계추출을 구분**해야 한다. 또한 “중복 주문”처럼 도메인 개념까지 추출하는 과제는 사람·장소 이름만 찾는 전통적인 NER보다 넓다. 타입과 라벨링 기준을 직접 정해야 한다.

## 모델·앱·라이브러리는 다른 층이다

| 이름 | 무엇인가 | 개발·제공 주체 |
|---|---|---|
| ChatGPT | 생성 모델을 이용하는 대화형 제품 | OpenAI |
| GPT 계열 | 다양한 작업에 쓰이는 모델 계열 | OpenAI |
| Claude | 모델 계열 및 이를 이용하는 제품 이름 | Anthropic |
| Gemini | 모델 계열 및 이를 이용하는 제품 이름 | Google / Google DeepMind |
| Stanford NER | CRF 기반 개체 인식 도구와 학습 모델 | Stanford NLP Group |
| spaCy | 학습된 NER 등 NLP 파이프라인을 실행하는 라이브러리 | spaCy 프로젝트 |
| Cohere Embed | 검색용 임베딩 모델 계열 | Cohere |
| LangChain·Langflow | 모델을 연결·실행하는 개발 도구 | 모델 그 자체와 구분 |

출처: [OpenAI ChatGPT 소개](https://openai.com/index/chatgpt/), [Anthropic Claude](https://www.anthropic.com/claude), [Google Gemini](https://deepmind.google/models/gemini/), [Stanford NER](https://nlp.stanford.edu/software/CRF-NER.html), [spaCy NER](https://spacy.io/usage/linguistic-features#named-entities), [Cohere 의미 검색](https://docs.cohere.com/docs/semantic-search-with-cohere).

“Gemini를 쓴다”만으로는 역할이 정해지지 않는다. Gemini 생성 모델로 문장을 만들 수도 있고, 별도의 Gemini Embedding 모델로 숫자 표현을 만들 수도 있다. 생성 모델 내부에도 임베딩 계산이 있지만 그 내부 값이 곧바로 문서 검색용 임베딩 API와 같지는 않다. [Google 임베딩 문서](https://ai.google.dev/gemini-api/docs/embeddings)

## 파이프라인 구성

추출·검색용 표현·답변 생성을 나누는 것은 공개된 KG/RAG 설계에서도 볼 수 있다. 예를 들어 Microsoft GraphRAG는 개체·관계 추출, 요약, 임베딩 등으로 인덱싱 단계를 구분한다. 기본 경로에서는 LLM으로 개체와 관계를 함께 추출한다. 역할별 단계를 나누되 같은 LLM을 추출과 생성에 함께 사용할 수도 있다. [Microsoft GraphRAG dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/)

| 구성 | 장점 | 감수할 점 |
|---|---|---|
| LLM 추출 + 임베딩 + LLM 답변 | 작은 실험에서 타입·관계 변경이 쉬움 | 추출 비용과 생성 오류, 반복 실행 변동 |
| 전용 NER + 관계 추출기/LLM + 임베딩 + 생성 | 단계별 최적화·검증, 대량 처리 비용 조절 가능 | 앞 단계 누락이 전파되고 운영 구성 증가 |
| 규칙·사전 + 모델 혼합 | 경로·버전 번호 같은 정형 표현에 명확한 기준 사용 | 표현이 달라질 때 규칙 유지 비용 |

온톨로지는 모델 개수의 이름이 아니다. 모델이 뽑는 대상·관계의 **의미와 규칙을 합의하는 층**이다. 모델을 세 개 설치하는 것만으로 만들어지지 않는다.

## 모델 비교 항목

1. 입력과 출력은 무엇인가? 문장·구간·벡터·답변 중 어떤 것을 만드는가?
2. 누가 어떤 목적으로 만들었고 한국어·도메인 입력을 지원하는가?
3. 기존 방법보다 무엇을 편하게 만들며 새 오류는 무엇인가?
4. 어떤 평가셋·버전·분할·지표로 성능을 말하는가?
5. 내 데이터의 최종 질문에도 이 점수가 의미가 있는가?

자세한 비교는 [개체추출](06-entity-extraction-models.md), [임베딩](07-embedding-models.md), [생성 모델](08-generative-models.md)에서 이어진다.
