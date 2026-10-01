# 개체추출 모델 · 규칙에서 NER와 LLM까지

## 참고자료

- [개체명 인식이란? — IBM](https://www.ibm.com/think/topics/named-entity-recognition) — 규칙·학습·혼합 방식과 활용 사례를 설명하는 입문 글.
- [spaCy 개체명 인식 예제](https://spacy.io/usage/linguistic-features#named-entities) — 추출한 이름·타입·원문 위치를 코드에서 확인하는 예제.
- [Stanford NER 소개와 실행 예제](https://nlp.stanford.edu/software/CRF-NER.html) — CRF 기반 추출기가 어떤 입력과 출력을 사용하는지 확인할 수 있다.

## 하는 일: 이름에 밑줄을 긋는 것부터

가상 문장 “주문서비스가 배송서비스를 호출한다”에서 두 서비스 이름에 밑줄을 긋고 `Service`라는 타입을 붙이는 것이 개체 인식의 예다.

```text
개체 인식(NER): 주문서비스[Service], 배송서비스[Service]
개체 연결: 주문서비스 → service:order라는 정규 ID
관계 추출(RE): service:order --calls--> service:shipping
```

`주문 API 서버`와 `order-service`가 같은 대상인지 판단하는 것은 별도 연결 문제다. 문장에 둘 다 등장한다고 `calls` 관계가 있는 것도 아니다. 전통적인 NER의 인물·기관·장소 타입과 이번 프로젝트의 서비스·API·의사결정 타입은 다르다.

## 예전에는 어떻게 했나

| 접근 | 방식 | 얻는 것과 한계 |
|---|---|---|
| 사전·정규식·규칙 | 알려진 이름 목록, 접미사, 경로 패턴으로 찾음 | 명시적인 표현에 강하지만 새 이름·다른 문맥에 취약 |
| 통계적 시퀀스 라벨링 | 사람이 설계한 특징으로 토큰별 라벨 학습, CRF 등 | 일관된 라벨열을 학습하지만 특징·학습 라벨 필요 |
| 신경망 NER | 문맥·문자 표현을 학습하고 구간/라벨 예측 | 수작업 특징 의존을 줄이지만 라벨 데이터는 필요 |
| 사전학습 모델 미세조정 | BERT 계열에 NER용 예측 층을 붙여 학습 | 풍부한 문맥 표현을 재사용, 도메인 차이는 남음 |
| 타입을 입력받는 모델·LLM | 찾을 타입과 설명을 주고 추출 | 새로운 스키마 실험이 쉬워지지만 오류 검증 필요 |

이것은 모든 프로젝트가 순서대로 교체한 연표가 아니라 대표적인 접근의 흐름이다. CRF도 이미 기계학습이었다. “옛날에는 AI가 없고 지금 처음 AI가 해준다”는 설명은 정확하지 않다. 신경망 NER의 특징 학습은 [Lample 등, 2016](https://aclanthology.org/N16-1030/), 사전학습 후 과제별 적용은 [BERT, 2019](https://aclanthology.org/N19-1423/)에서 볼 수 있다.

## 개발 주체와 대표적인 선택지

| 이름 | 주체·발표 맥락 | 실제 사용하는 방법 |
|---|---|---|
| BERT | Google 연구진, 2018 사전공개·NAACL 2019 | 기본 모델 자체를 완성된 도메인 NER로 보지 않고 과제별 미세조정 |
| Stanford NER | Stanford NLP Group | CRF 기반 모델로 원문에 개체 타입을 붙임. 전통적 학습 기반 추출 사례 |
| spaCy NER | spaCy 프로젝트 | 언어별 학습 파이프라인으로 개체 구간과 라벨을 추출. 라이브러리와 개별 모델을 구분 |
| 범용 생성 LLM | OpenAI·Anthropic·Google 등 | 타입 정의·예시·출력 스키마를 주고 JSON 후보 생성 |

Stanford NER의 CRF 방식과 spaCy의 NER 파이프라인은 추출기를 사용하는 서로 다른 사례다. spaCy의 `EntityRuler`처럼 규칙을 학습 모델과 함께 사용할 수도 있다. 한국어 금융 문서의 서비스·정책 타입을 바로 지원하는지는 별도로 확인해야 한다.

참고: [Stanford NER](https://nlp.stanford.edu/software/CRF-NER.html), [spaCy NER](https://spacy.io/usage/linguistic-features#named-entities), [규칙과 모델을 결합하는 EntityRuler](https://spacy.io/usage/rule-based-matching#entityruler).

## 무엇이 편리해졌고 무엇은 사람이 해야 하나

LLM에 타입 설명과 예시를 주면 모든 새 타입에 대해 처음부터 대량 라벨링·재학습하지 않고 후보를 시험할 수 있다. 예를 들어 `Decision`을 “팀이 채택하기로 명시한 설계 선택”으로 설명할 수 있다.

하지만 “이 방안도 가능하다”는 제안을 확정 결정으로 바꾸거나, 원문에 없는 대상을 만들어낼 수 있다. 사람은 타입 경계, 조건·부정 처리, 정답 기준을 정하고 검토해야 한다. “호출하지 않는다”를 긍정 `calls`로 저장하면 구간 인식이 정확해도 지식 그래프는 틀린다.

## 평가: 정확도 하나로 보지 않는다

개체 평가에서 일반적인 엄격 일치 기준은 **원문 시작·끝 위치와 타입이 모두 맞아야 정답**이다. “배송서비스팀”이 정답인데 “배송서비스”까지만 추출하면 경계 오류다.

가상 골드 개체가 10개이고 8개를 추출했으며 그중 6개가 엄격히 맞았다면:

```text
Precision = 6 / 8 = 0.75        뽑은 것 중 얼마나 맞았나
Recall    = 6 / 10 = 0.60       찾아야 할 것 중 얼마나 찾았나
F1        = 2PR / (P+R) ≈ 0.667
```

전체 건수를 합쳐 계산하는 micro와 타입별 계산 후 평균내는 macro는 다르다. 중요한 희소 타입이 전체 점수에 묻힐 수 있으므로 타입별 점수도 확인한다. 일부 글자가 맞았다고 주는 부분 점수와 엄격 구간 점수도 섞지 않는다.

## 대표 평가셋: 출처·발표 시점·적용 한계

날짜는 확인 가능한 논문 발표·최초 사전공개 기준이다. 데이터의 최종 수정일이나 현재 버전 배포일과 같다고 가정하지 않는다.

| 평가셋 | 출처·시점 | 데이터·과제 | 지표와 내 실습에서의 한계 |
|---|---|---|---|
| CoNLL-2003 NER | Tjong Kim Sang·De Meulder, CoNLL 2003 | 영어 Reuters·독일어 신문, 인물·기관·장소·기타 | 개체 구간/타입 일치 P/R/F1; 한국어 API·정책 타입의 성능 보장 아님 |
| KLUE-NER | KLUE 공동 연구팀; arXiv 2021-05-20, NeurIPS Datasets and Benchmarks 2021 | 한국어 뉴스·리뷰, 인물·장소·기관·날짜·시간·수량 | entity-level macro F1와 character-level macro F1; 도메인 라벨 별도 필요 |
| KLUE-RE | 같은 KLUE 프로젝트, 2021 | 한국어 위키·뉴스 문장과 개체쌍의 관계 | no_relation을 제외한 micro F1, AUPRC; NER와 다른 과제 |

원자료: [CoNLL-2003 논문](https://aclanthology.org/W03-0419/), [KLUE 논문과 최초 공개 이력](https://arxiv.org/abs/2105.09680), [KLUE 원문 §3.4~3.5](https://arxiv.org/html/2105.09680v4), [공식 평가표](https://github.com/KLUE-benchmark/KLUE).

관계 평가에서는 정답 개체쌍을 미리 준 평가와 개체 인식부터 실행한 end-to-end 평가를 구분한다. 정답 개체쌍을 준 실험에서 관계를 잘 맞혀도 실제 파이프라인이 개체를 놓치면 최종 관계는 사라진다.
