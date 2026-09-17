---
title: "Citation과 Provenance: 근거를 어떻게 남겨야 하는가"
date: 2026-09-17
tags: [citation, provenance, rag, alce, w3c-prov, knowledge-graph, evaluation]
status: done
---

# Citation과 Provenance: 근거를 어떻게 남겨야 하는가

`chat.py`를 만들면서 "답변 뒤에 [1], [2]를 붙이자"까지는 이미 했다. 근데 그걸로 충분한 건 아니었다. `failed_questions.md`에 적어둔 사례를 다시 보면, 에이전트가 근거 번호를 붙이긴 붙였는데(SK하이닉스의 용인 클러스터 공시를 [6]으로 인용) 그 근거가 실제로는 질문이 물어본 "AMD 공급사"와는 관계없는 회사 것이었다. **인용은 있었지만, 그 인용이 주장을 제대로 뒷받침하진 못한 것**이다. 이 구멍을 이름 붙여서 이해하고 싶어서 Citation과 Provenance라는 두 개념을 정리해봤다.

## 1. 두 단어는 역할이 다르다

- **Citation**: 최종 답변의 특정 주장에 "이 근거에서 나왔다"고 출처를 붙이는 것. 사용자를 향한 장치다.
- **Provenance**: 그 정보가 어디서 왔고, 언제 만들어졌고, 어떤 문서·버전·처리를 거쳤는지 추적할 수 있게 하는 메타데이터. 시스템 내부를 향한 장치다.

예를 들어 답변이 이렇게 나왔다고 하자.

```text
A사의 2025년 영업이익은 전년 대비 감소했다.
```

이것만으로는 어디서 나온 말인지 알 수 없다. Citation을 붙이면:

```text
A사의 2025년 영업이익은 전년 대비 감소했다. 출처: 2025 사업보고서 p.42
```

이 정도가 된다. Provenance는 이보다 훨씬 자세하다. 내부적으로는 이런 식으로 관리될 수 있다.

```text
company = A사
document_type = 사업보고서
document_title = 2025 사업보고서
published_at = 2026-03-15
reporting_period = 2025-01-01 ~ 2025-12-31
page = 42
table = 연결 손익계산서
metric = 영업이익
scope = 연결
unit = 백만원
value = 125000
source_url = ...
chunk_id = ...
```

Citation은 사용자에게 "근거가 어디인지" 보여주는 것이고, Provenance는 시스템이 "이 정보가 정확히 어디서 왔는지" 추적 가능하게 하는 것 — 이 차이를 갈라두면 나머지는 자연스럽게 이어진다.

## 2. 기업분석에서 provenance가 유독 중요한 이유

같은 숫자라도 맥락이 다르면 완전히 다른 값이 될 수 있다. "매출 10조 원"이라는 값 하나만 봐서는 부족하다.

```text
어느 회사?
몇 년도?
분기인가 연간인가?
연결인가 별도인가?
원 단위인가 백만원 단위인가?
최초 공시인가 정정 공시인가?
```

이런 질문에 다 답할 수 있어야 하기 때문에, 기업분석용 RAG에서는 값 하나를 저장할 때 회사·기간·회계 기준·단위·문서·위치·공시 시점을 같이 들고 다니는 게 맞다. 이 묶음이 provenance다.

## 3. Citation의 품질도 단계가 있다

인용이 "있다"는 것과 "제대로 됐다"는 건 다른 문제다. 보통 세 단계로 나눠본다.

1. **Citation Existence** — 출처가 붙어 있는가?
2. **Citation Relevance** — 그 출처가 이 주제와 관련은 있는가?
3. **Citation Entailment** — 그 출처가 실제로 이 주장을 뒷받침하는가?

우리 프로젝트에서 겪은 사례가 딱 이 세 단계의 차이를 보여준다. "AMD에 HBM4를 공급하는 회사가 최근 공시에서 밝힌 반도체 클러스터는?"이라는 질문에서, 에이전트는 SK하이닉스의 용인 클러스터 공시를 근거로 답했다.

```text
출처 존재: O  (근거 번호가 붙어 있다)
주제 관련: O  (반도체 클러스터 투자 공시라는 주제는 맞다)
주장 뒷받침: X (근데 이 공시는 AMD 공급사인 삼성전자가 아니라 SK하이닉스 것이다)
```

인용이 있고 주제도 얼추 맞는데, 정작 그 인용이 질문이 실제로 물어본 걸 증명하진 못하는 상황 — 이게 RAG에서 자주 나오는 citation 문제다. 그리고 대부분 눈에 잘 안 띈다. 근거 번호가 붙어 있으면 일단 그럴듯해 보이기 때문이다.

## 4. Claim Granularity: 한 인용이 얼마나 많은 주장을 덮는가

문장 하나에 주장이 여러 개 들어있는데 인용 하나만 붙이면 애매해진다.

```text
A사는 매출이 감소했고, 원재료 가격이 상승했으며, 북미 판매도 감소했다. [1]
```

이러면 [1]이 세 주장 중 어디까지 뒷받침하는지 알 수 없다. 주장 단위로 근거를 나누는 게 더 낫다.

```text
A사의 매출은 감소했다. [1]
원재료 가격은 상승했다. [2]
북미 판매량도 감소했다. [3]
```

즉 "답변 생성"만 볼 게 아니라 **Claim → Evidence** 구조로 나눠서 생각하는 게 도움이 된다.

```text
Claim 1  "A사의 영업이익이 감소했다"       → Evidence 1  사업보고서 p.42
Claim 2  "원재료 가격 상승이 영향을 줬다"   → Evidence 2  실적발표 p.8
```

## 5. 이게 왜 지식그래프와 이어지는가

이 Claim → Evidence 구조는 그래프의 엣지에 provenance를 붙이는 것과 같은 모양이다.

```text
A사 ── HAS_METRIC ──> 영업이익
                        value: ...
                        period: 2025
                        source: 사업보고서 p.42
```

지난 노트들에서 계속 얘기했던 "왜 지식그래프가 필요한가"의 연장선이기도 하다. 예를 들어 이런 질문을 생각해보자.

```text
A사의 종속회사 중 최근 영업이익이 감소했고 B사에도 납품하는 회사는?
```

이 질문은 최소 세 개의 사실을 이어야 답이 나온다.

```text
A사의 종속회사 목록      → 출처 1
각 종속회사의 영업이익    → 출처 2, 기간 비교 필요
B사 납품 관계            → 출처 3
```

최종 답만 "C사입니다"라고 나오면, 틀렸을 때 어디서 잘못됐는지 알 방법이 없다. 근데 각 관계에 provenance가 붙어 있으면 얘기가 달라진다.

```text
C ─ SUBSIDIARY_OF → A       source: A사 사업보고서 2025 p.83
C ─ OPERATING_INCOME → 120억  period: 2025, scope: 별도, source: C사 감사보고서 p.31
C ─ SUPPLIES_TO → B          valid_at: 2025, source: B사 공급망 보고서 p.14
```

이러면 세 hop을 각각 검증할 수 있다. 기업 KG에서 provenance는 부가 정보라기보다, 그래프의 관계를 믿을 수 있게 만드는 장치에 가깝다.

## 6. 그렇다고 모든 곳에 다 필요한 건 아니다

Citation·Provenance가 중요해지는 건 "기업분석이라서"가 아니라, **사실 확인이 필요하고 그 출처를 추적할 필요가 큰 주제일수록** 그렇다. 대표적으로:

- 기업·금융·투자 분석 (연결/별도, 분기/연간, 단위, 공시 버전이 다 다른 의미를 가짐)
- 법률·정책·규제 (어느 조항, 최신 개정본인지, 관할권)
- 의학·과학·연구 (연구 대상, 기간, 방법론에 따라 해석이 달라짐)
- 뉴스·사실검증 (초기 보도 vs 후속 보도, 익명 출처 vs 공식 발표)
- 지식그래프·데이터 통합 (여러 출처가 충돌할 때 비교할 근거가 필요함)

반대로 단순 창작·번역·일반적인 생활 조언처럼 "정확히 어느 원문에서 나왔는지"가 핵심이 아닌 작업, 혹은 정답이 거의 안 바뀌고 근거가 한 문서에 분명히 있는 단순 FAQ라면 citation 정도로 충분하고 provenance까지 엄격하게 관리할 필요는 없다. 판단 기준은 이 정도 질문으로 가늠해볼 수 있다.

```text
잘못된 답의 비용이 큰가?
정보가 자주 바뀌는가?
여러 문서의 정보를 합쳐야 하는가?
수치·기간·버전이 중요한가?
서로 충돌하는 출처가 있을 수 있는가?
나중에 왜 이런 답이 나왔는지 추적해야 하는가?
```

여러 개가 "그렇다"면 provenance를 신경 쓸 만한 상황이다.

## 7. Citation·Provenance는 지표가 아니라 지표를 만드는 바탕

둘 다 그 자체로 측정값은 아니고, 시스템이 보존해야 할 속성 내지 설계 개념에 가깝다. 이 위에 다음 같은 평가 지표를 얹을 수 있다.

- Citation correctness — 인용한 문서가 실제 그 주장을 뒷받침하는가
- Citation completeness — 중요한 주장마다 근거가 빠짐없이 붙어 있는가
- Citation relevance — 인용한 문서가 해당 주장과 관련 있는가
- Provenance completeness — source·date·page·period 같은 추적 정보가 충분히 남아 있는가
- Provenance consistency — 서로 다른 출처·버전을 섞어 쓰지는 않았는가

이 중 citation 쪽 평가는 [ALCE](https://arxiv.org/abs/2305.14627) 같은 연구에서 다루고, provenance 쪽은 [W3C PROV](https://www.w3.org/TR/prov-primer/) 같은 표준으로 발전해왔다. ALCE는 단순히 "인용이 있느냐"가 아니라 "그 인용이 실제로 주장을 지지하느냐"를 자동으로 평가하려는 관점을 가지고 있어서, 3절에서 다룬 Citation Entailment와 정확히 맞닿아 있다.

## 마치며

이번 주에는 두 개념을 이 정도로만 구분해두면 충분할 것 같다.

```text
Citation  = 답변의 주장에 출처를 붙이는 것
Provenance = 그 근거가 만들어지고 수집된 맥락까지 추적 가능하게 하는 것

좋은 기업분석 RAG
= 답변이 맞고
+ 근거가 실제로 존재하고
+ 그 근거가 해당 주장을 뒷받침하고
+ 기간·단위·연결/별도·문서 버전까지 추적 가능한 것
```

지금 `chat.py`는 "근거 번호를 붙여라"까지만 시스템 프롬프트에 넣어뒀는데, 여기에 Claim → Evidence 단위로 답변을 쪼개거나, 근거마다 회사·기간·단위 같은 provenance 필드를 같이 보여주는 식으로 발전시킬 여지가 있다. 이건 나중에 지식그래프의 엣지 속성 설계와도 그대로 이어질 부분이다.

## 참고 자료

- [Enabling Large Language Models to Generate Text with Citations (ALCE, EMNLP 2023, arXiv)](https://arxiv.org/abs/2305.14627)
- [ALCE GitHub](https://github.com/princeton-nlp/ALCE)
- [PROV Model Primer — W3C](https://www.w3.org/TR/prov-primer/)
- [PROV-DM: The PROV Data Model — W3C](https://www.w3.org/TR/prov-dm/)
- [failed_questions.md](../labs/03-company-analysis-kg/failed_questions.md) — citation existence/relevance는 있었지만 entailment가 깨졌던 실제 사례

---

**다음 노트**: [RAG 루프와 Retrieval Evaluation: 어디서 틀렸는지 구분하기](03-rag-loop.md)
