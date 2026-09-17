---
title: "Single-hop에서 Multi-hop으로, 그리고 지식그래프로"
date: 2026-09-17
tags: [multi-hop, hotpotqa, multihop-rag, ircot, agentic-retrieval, knowledge-graph, error-propagation]
status: done
---

# Single-hop에서 Multi-hop으로, 그리고 지식그래프로

[지난 노트](03-rag-loop.md)에서 RAG 루프와 그 평가 방법을 정리했다. 이번 노트는 그중에서도 이번 주에 계속 부딪혔던 지점 — multi-hop 질문 — 을 문헌으로 한 번 더 짚어보고, 이게 왜 결국 지식그래프 얘기로 이어지는지 정리한다.

## 1. Single-hop과 Multi-hop은 구조 자체가 다르다

Single-hop 질문은 검색 한 번으로 끝난다.

```text
"A사의 2025년 영업이익은?"
    ↓
A사 사업보고서 검색
    ↓
answer
```

Multi-hop 질문은 다르다.

```text
"A사의 종속회사 중 영업이익이 감소했고 B사에도 납품하는 기업은?"

A사
 ↓ subsidiary
A1, A2, A3
 ↓ 각 회사 실적 검색
A2 영업이익 감소
 ↓ A2의 고객 검색
B사 납품 여부 확인
```

다음 검색어가 이전 검색 결과에 의존한다는 게 핵심이다. 우리 실습에서도 이 구조가 그대로 나왔다. "삼성전자 HBM4E 12단 제품의 용량은?"은 청크 하나로 끝나는 single-hop이었고, "AMD에 HBM4를 공급하는 회사가 최근 공시에서 밝힌 클러스터는?"은 (비록 답이 없는 질문이었다는 게 나중에 밝혀졌지만) 구조상으로는 "공급사가 누구인지 찾고 → 그 회사의 공시를 찾는" multi-hop이었다.

## 2. HotpotQA와 Supporting Facts

[HotpotQA](https://aclanthology.org/D18-1259/)는 이런 multi-hop QA를 연구하려고 만들어진 대표적인 데이터셋이다. 위키백과 기반 질문-답변 11만 3천 쌍으로 구성돼 있고, 답을 맞히려면 여러 문서를 찾아 근거를 연결하는 reasoning이 필요하다. 여기서 중요한 개념이 **supporting facts**다. 답 하나만 맞히면 끝이 아니라, 그 답이 어떤 사실들을 근거로 나왔는지 문장 단위로 같이 제공한다.

```text
Fact A + Fact B → Answer
```

이건 [지난 노트](03-citation-and-provenance.md)에서 다룬 Claim → Evidence 구조와 사실상 같은 이야기다. 그리고 기업 KG로 옮기면 이런 그래프 경로가 된다.

```text
Company A ── SUBSIDIARY ──> Company C ── SUPPLIES_TO ──> Company B
```

## 3. MultiHop-RAG: 일반 RAG는 왜 여기서 힘든가

[MultiHop-RAG](https://arxiv.org/abs/2401.15391)는 기존 RAG가 multi-hop 질문에 필요한 여러 근거를 찾고 그걸로 추론하는 데 약하다는 걸 보여준 논문이다. Inference·Comparison·Temporal·Null 네 종류의 multi-hop 질의로 벤치마크를 만들었고, 검색과 LLM 추론 둘 다 평가했는데 두 쪽 다 성능이 충분치 않았다고 보고한다.

이 논문에서 나온 실패 유형을 기업분석에 대응시켜보면, 이번 주에 우리가 겪은 것과 거의 정확히 겹친다.

| 실패 유형 | 의미 | 우리 사례 |
|---|---|---|
| Retrieval failure | 필요한 문서를 못 찾음 | (BM25는 실제로 찾았던 경우가 많았다) |
| Coverage failure | 근거 여러 개 중 일부만 검색 | q009: 정답 청크 3개 중 2개만 top-5에 들어옴 |
| Entity failure | 서로 다른 회사를 잘못 연결 | `dart_005`(SK하이닉스)를 "AMD 공급사"(삼성전자) 질문의 근거로 씀 |
| Temporal failure | 다른 시점의 정보를 무심코 결합 | (아직 직접 테스트는 안 해봤지만, Citation·Provenance 노트에서 다룬 연/분기 혼동과 같은 종류) |
| Metric failure | 지표를 혼동 | (마찬가지로 아직 직접 테스트는 안 함, 매출/영업이익 혼동 같은 것) |
| Scope failure | 연결/별도 기준 혼동 | (아직 직접 테스트는 안 함) |
| Relation failure | "A가 B에 공급"을 "B가 A에 공급"으로 잘못 해석 | (아직 직접 테스트는 안 함) |

이 중 Coverage failure와 Entity failure는 이번 주 실습에서 실제로 확인한 것이고, 나머지 셋(Temporal·Metric·Scope failure)은 아직 직접 겪어보진 않았지만 Citation·Provenance 노트에서 다룬 "같은 숫자도 맥락이 다르면 다른 값"이라는 문제와 정확히 같은 종류라서 언젠가 나타날 가능성이 높아 보인다.

## 4. Agentic/Iterative Retrieval — 이미 만들어봤던 것

여기까지 보면 자연스럽게 "그럼 첫 검색 결과를 보고 다음 검색어를 다시 만들면 되지 않나?"라는 생각이 든다. 맞다. 그게 iterative retrieval, agentic retrieval 계열의 아이디어다. [IRCoT](https://aclanthology.org/2023.acl-long.557/)가 대표적인데, 구조는 이렇다.

```text
기존:                  IRCoT 스타일:
Question               Question
  ↓                       ↓
Retrieve               Reasoning step
  ↓                       ↓
Generate               Retrieve → 새 정보
                          ↓
                        Reasoning step
                          ↓
                        Retrieve → ...
```

이 구조는 `agentic_chat.py`로 이미 구현돼 있고, 논문이 말하는 문제도 그대로 겪었다.

```text
Hop 1에서 entity를 잘못 선택
    ↓
Hop 2 질의도 같이 틀림
    ↓
Hop 3도 틀림
```

이게 error propagation인데, 실제로 우리 테스트에서는 이런 모습으로 나타났다. 작은 모델(2.4B)은 애초에 재질의 자체를 안 해서 이 문제가 드러나지도 않았고, 큰 모델(7.8B)은 "지금 근거가 부족하다"는 자각은 했지만, 표현만 바꾼 검색어로 계속 재검색하면서 같은 자리를 맴돌았다. 정답 문서를 이미 근거로 갖고 있었는데도 그걸 알아채지 못했다는 점에서, IRCoT 논문이 지적하는 문제와 결이 같다. 즉 재질의 루프를 붙이는 것만으로는 error propagation이 완전히 없어지지 않는다.

## 5. 그래서 지식그래프가 필요하다

정리하면 이렇다.

- 일반 RAG(검색 1회)는 구조적으로 multi-hop을 못 푼다. 다음 검색어가 이전 결과에 의존하는데, 검색을 한 번만 하기 때문이다.
- Agentic/Iterative Retrieval은 이 구조적 한계를 부분적으로 우회한다. 쿼리 분해(`--decompose`)로 같은 문서 안에 흩어진 얕은 multi-hop(q009)은 풀었다. 하지만 Entity failure가 실제로 나타난 질문(1번 사례)에는 재질의 루프와 `--decompose` 둘 다 따로 적용해봤는데 문제가 없어지지 않았다 — 재질의 루프는 표현만 바꾼 검색어로 계속 맴돌았고, `--decompose`는 하위 질의를 서로 독립적으로(앞선 하위 질의 결과를 넘겨받지 않고) 만들다 보니 두 회사의 근거를 한꺼번에 섞어 질문에 답하지 않는 회피성 답변을 냈다(로그는 [failed_questions.md](../labs/03-company-analysis-kg/failed_questions.md) 4번 참고).

지식그래프는 이 문제를 다른 방식으로 푼다. 엔티티와 관계를 미리 명시적으로 저장해두면:

```text
Company A ── SUBSIDIARY ──> Company C ── SUPPLIES_TO ──> Company B
```

이 경로를 그래프 탐색으로 따라가면 되기 때문에, "검색해서 찾고 → 그게 맞는 회사 것인지 매번 판단"하는 과정 자체가 없어진다. Entity failure는 애초에 다른 노드니까 섞일 수 없고, Relation failure는 엣지의 방향이 명시돼 있어서 헷갈릴 수 없고, Temporal·Scope·Metric failure는 엣지에 `period`, `scope`, `unit` 같은 provenance 속성을 달아두면 애초에 혼동할 여지가 줄어든다. MultiHop-RAG의 실패 유형표가 곧 KG의 엣지 속성 설계표가 되는 셈이다.

## 마치며

이번 주에 실습으로 확인한 것(RRF·점수 정규화의 코퍼스 의존성, 에이전틱 검색의 한계, 엔티티 혼동)과 이번 노트에서 본 문헌(HotpotQA, MultiHop-RAG, IRCoT)이 거의 같은 결론을 가리키고 있다. RAG와 그 위에 재질의를 얹은 에이전틱 검색까지는 만들어봤고, 어디서 왜 막히는지도 구체적인 사례로 남겨뒀다. 다음 단계(W4)는 이 실패 유형들을 실제로 막아주는 엔티티·관계 구조, 즉 지식그래프를 만드는 것이다.

## 참고 자료

- [HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering (ACL Anthology)](https://aclanthology.org/D18-1259/)
- [MultiHop-RAG: Benchmarking Retrieval-Augmented Generation for Multi-Hop Queries (arXiv)](https://arxiv.org/abs/2401.15391)
- [Interleaving Retrieval with Chain-of-Thought Reasoning for Knowledge-Intensive Multi-Step Questions, IRCoT (ACL Anthology)](https://aclanthology.org/2023.acl-long.557/)
- [03-rag-loop.md](03-rag-loop.md) — retrieval/generation 실패 구분
- [03-citation-and-provenance.md](03-citation-and-provenance.md) — Claim → Evidence, 엔티티별 provenance
- [failed_questions.md](../labs/03-company-analysis-kg/failed_questions.md) — Coverage failure·Entity failure 실제 사례
- [rag-vs-kg-summary.md](../labs/03-company-analysis-kg/rag-vs-kg-summary.md) — RAG로 되는 것과 KG가 필요한 것 정리
