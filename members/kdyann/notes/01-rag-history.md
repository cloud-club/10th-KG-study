---
title: RAG 기술 변천사
date: 2026-09-09
tags: [rag, retrieval, self-rag, graphrag, agentic-rag]
status: done
---

# 01. RAG 기술 변천사

> 참고 자료:
>
> - Lewis et al., [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://papers.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html) (2020)
> - Karpukhin et al., [Dense Passage Retrieval for Open-Domain Question Answering](https://aclanthology.org/2020.emnlp-main.550/) (2020)
> - Thakur et al., [BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models](https://arxiv.org/abs/2104.08663) (2021)
> - Gao et al., [Retrieval-Augmented Generation for Large Language Models: A Survey](https://arxiv.org/abs/2312.10997) (2023)
> - Asai et al., [Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection](https://openreview.net/forum?id=hSyW5go0v8) (2024)
> - Yan et al., [Corrective Retrieval Augmented Generation](https://arxiv.org/abs/2401.15884) (2024)
> - Sarthi et al., [RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval](https://proceedings.iclr.cc/paper_files/paper/2024/hash/8a2acd174940dbca361a6398a4f9df91-Abstract-Conference.html) (2024)
> - Jeong et al., [Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity](https://aclanthology.org/2024.naacl-long.389/) (2024)
> - Edge et al., [From Local to Global: A Graph RAG Approach to Query-Focused Summarization](https://arxiv.org/abs/2404.16130) (2024)
> - Anthropic, [Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval) (2024)
> - Günther et al., [Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models](https://arxiv.org/abs/2409.04701) (2024)

## 한 줄 요약

RAG는 외부 문서를 한 번 검색해 답변에 넣는 구조에서 출발해서 검색 결과의 품질을 평가하고 문맥과 관계를 보존하며 필요할 때 반복 검색하는 구조로 발전했다.

## RAG란 무엇인가

RAG(Retrieval-Augmented Generation)는 사용자의 질문과 관련된 정보를 외부 지식 저장소에서 검색한 후에 그 정보를 생성 모델의 입력에 포함해 답변을 만드는 방법이다.

언어 모델이 학습 과정에서 가중치에 저장한 지식을 파라메트릭 메모리라고 한다면, 문서 저장소나 검색 인덱스는 모델 밖에 존재하는 비파라메트릭 메모리다. RAG는 두 메모리를 결합해 모델을 다시 학습하지 않고도 새로운 문서와 특정 도메인의 지식을 활용할 수 있게 한다([Lewis et al., 2020](https://papers.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html)).

RAG가 발전한 방향은 크게 세 가지다.

1. 필요한 문서를 더 정확하게 검색하기
2. 잘린 문서의 문맥과 문서 사이의 관계를 보존하기
3. 검색이 필요한지, 검색 결과가 충분한지 스스로 판단하기

## 1기: Dense Retrieval과 원조 RAG의 등장 (2019~2021)

### Dense Retrieval

초기의 검색 시스템은 주로 TF-IDF나 BM25처럼 문서와 질문에 동일한 단어가 얼마나 등장하는지를 이용했다. 이러한 sparse retrieval은 고유명사와 정확한 용어 검색에는 강하지만 질문과 문서가 서로 다른 표현을 사용하면 관련 문서를 놓칠 수 있다.

DPR(Dense Passage Retrieval)은 질문과 문서를 각각 별도의 인코더로 벡터화하는 dual-encoder 구조를 사용했다. 질문 벡터와 가까운 문서 벡터를 찾는 방식이므로 단어가 정확히 일치하지 않아도 의미가 유사한 문서를 검색할 수 있다. DPR 논문에서는 평가한 오픈 도메인 질의응답 데이터셋에서 Lucene-BM25보다 높은 top-20 passage retrieval accuracy를 보였다([Karpukhin et al., 2020](https://aclanthology.org/2020.emnlp-main.550/)).

다만 dense retrieval이 모든 데이터에서 BM25보다 우수한 것은 아니다. BEIR 벤치마크는 검색 모델의 제로샷 성능이 데이터셋과 도메인에 따라 달라질 수 있음을 보여줬다([Thakur et al., 2021](https://arxiv.org/abs/2104.08663)). 이 결과는 이후 sparse retrieval과 dense retrieval을 함께 사용하는 하이브리드 검색의 근거가 됐다.

### 원조 RAG

2020년 Lewis et al.은 검색기와 생성 모델을 결합한 RAG를 제안했다. DPR 계열 retriever가 Wikipedia에서 관련 문서를 검색하고, BART 기반 generator가 검색 결과를 조건으로 답변을 생성한다. 학습 시에는 질문 인코더와 생성 모델이 함께 최적화된다([Lewis et al., 2020](https://papers.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html)).

논문은 검색 문서를 사용하는 단위에 따라 두 방식을 제시했다.

- RAG-Sequence: 하나의 출력 시퀀스를 생성하는 동안 같은 검색 문서 집합을 사용한다.
- RAG-Token: 출력 토큰마다 서로 다른 검색 문서를 고려할 수 있다.

원 논문의 RAG는 현재 흔히 말하는 "고정된 임베딩 모델과 벡터 DB에서 문서를 찾고 LLM 프롬프트에 넣는 방식"과 차이가 있다. 원래의 RAG는 retriever와 generator를 하나의 학습 구조 안에서 결합한 모델이었다.

## 2기: Naive RAG의 대중화 (2022~2023)

대규모 언어 모델이 널리 사용되면서 RAG는 모델 학습 방법보다 애플리케이션을 만드는 방법으로 대중화됐다. 다음과 같은 구조가 대표적인 Naive RAG 파이프라인이 됐다.

```text
문서 수집
  -> 문서 청킹
  -> 임베딩 생성
  -> 벡터 DB 저장
  -> 질문과 가까운 top-k 청크 검색
  -> 검색 결과를 프롬프트에 삽입
  -> LLM 답변 생성
```

Naive RAG는 구현하기 쉽고 문서만 교체해도 새로운 지식을 반영할 수 있다는 장점이 있다. 그러나 다음과 같은 한계가 드러났다.

- 필요한 문서가 검색 결과에 포함되지 않을 수 있다.
- 문서를 청크로 나누면서 주어, 대명사, 앞뒤 문단의 문맥이 사라질 수 있다.
- 검색 점수는 높지만 답변에는 필요 없는 문서가 포함될 수 있다.
- 단순한 질문과 복잡한 질문 모두 동일한 횟수와 방식으로 검색한다.
- 올바른 문서를 검색해도 생성 모델이 근거를 무시하거나 잘못 해석할 수 있다.

Gao et al.의 서베이는 RAG를 Naive RAG, Advanced RAG, Modular RAG로 분류하며 이러한 발전 과정을 정리했다([Gao et al., 2023](https://arxiv.org/abs/2312.10997)).

## 3기: Advanced RAG와 Modular RAG (2023~2024)

Advanced RAG는 Naive RAG의 기본 구조를 유지하면서 검색 전후의 품질을 개선한다.

- 검색 전: 문서 정제, 의미 단위 청킹, 메타데이터 추가, 쿼리 재작성과 분해
- 검색 중: BM25와 dense retrieval을 결합한 하이브리드 검색, 메타데이터 필터
- 검색 후: 리랭킹, 중복 제거, 불필요한 문맥 압축
- 생성 후: 답변과 근거의 일치 여부 및 인용 확인

Modular RAG는 검색, 라우팅, 메모리, 재작성, 평가, 생성 단계를 교체 가능한 모듈로 본다. 모든 질문을 같은 검색기로 처리하지 않고, 질문 유형과 데이터 소스에 따라 필요한 모듈을 조합할 수 있다([Gao et al., 2023](https://arxiv.org/abs/2312.10997)).

이 시기부터 RAG의 핵심은 "벡터 DB를 사용하는가"에서 "무엇을 언제 어떻게 검색하고, 검색 결과를 어떻게 정제할 것인가"로 확장됐다.

## 4기: 검색 결과를 평가하고 교정하는 RAG (2024)

### Self-RAG

Self-RAG는 모든 질문에 고정된 개수의 문서를 무조건 검색하는 방식을 개선했다. 모델은 reflection token을 사용해 검색이 필요한지, 검색한 문서가 관련 있는지, 생성한 답변이 근거를 따르는지 판단한다([Asai et al., 2024](https://openreview.net/forum?id=hSyW5go0v8)).

기존의 `검색 -> 생성` 흐름에 자기 평가가 추가됐다.

### CRAG

CRAG(Corrective RAG)는 별도의 retrieval evaluator로 검색 결과의 품질을 평가한다. 검색 결과가 부정확하면 웹 검색과 같은 다른 지식 소스를 사용하며 문서에서 중요한 부분을 골라 다시 구성한다([Yan et al., 2024](https://arxiv.org/abs/2401.15884)).

검색 결과가 항상 옳다고 가정하지 않고 잘못된 검색을 교정 가능한 대상으로 본 것!

### Adaptive-RAG

Adaptive-RAG는 질문의 복잡도에 따라 검색 전략을 선택한다. 간단한 질문은 검색하지 않고, 단일 근거가 필요한 질문은 한 번 검색하며, 여러 근거를 연결해야 하는 질문은 반복 검색한다([Jeong et al., 2024](https://aclanthology.org/2024.naacl-long.389/)).

모든 질문에 무거운 검색 파이프라인을 적용하는 대신 질문에 맞는 비용과 전략을 선택한다.

## 5기: 문맥과 관계를 보존하는 RAG (2024~)

### RAPTOR

일반적인 RAG는 짧은 청크를 독립적으로 검색하기 때문에 문서 전체의 주제나 여러 부분을 연결하는 질문에 약하다. RAPTOR는 청크를 임베딩하고 군집화한 뒤 요약을 재귀적으로 생성해 트리 구조를 만든다. 검색 시 서로 다른 추상화 수준의 원문 청크와 요약을 활용한다([Sarthi et al., 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/8a2acd174940dbca361a6398a4f9df91-Abstract-Conference.html)).

### Contextual Retrieval과 Late Chunking

Contextual Retrieval은 각 청크가 원래 문서에서 어떤 역할을 하는지를 설명하는 짧은 문맥을 청크 앞에 붙인 뒤 임베딩과 BM25 인덱싱을 수행한다([Anthropic, 2024](https://www.anthropic.com/engineering/contextual-retrieval)).

Late Chunking은 문서를 먼저 잘라 각각 임베딩하는 대신에 긴 문서 전체를 토큰 수준에서 인코딩한 후 청크 경계에 맞춰 벡터를 만든다. 이를 통해 각 청크의 벡터에 전체 문서의 문맥을 반영한다([Günther et al., 2024](https://arxiv.org/abs/2409.04701)).

두 방식 모두 청킹 과정에서 사라지는 문맥을 보완하려는 접근이다.

### GraphRAG

벡터 검색은 질문과 비슷한 개별 청크를 찾는 데 유용하다. 하지만 문서 전체에 등장하는 인물과 개념의 관계를 종합하는 질문에는 한계가 있다.

Microsoft의 GraphRAG는 원문에서 엔티티와 관계를 추출해 지식 그래프를 만들고 연결된 엔티티의 커뮤니티별 요약을 생성한다. 개별 엔티티 주변을 탐색하는 local search와 전체 커뮤니티 요약을 종합하는 global search를 구분한다([Edge et al., 2024](https://arxiv.org/abs/2404.16130)).

GraphRAG는 단순 벡터 검색의 대체재라기보다 관계와 전체적인 주제를 묻는 질문을 위한 추가 검색 구조다. 엔티티 및 관계 추출과 요약 생성이 필요하기 때문에 구축 비용과 데이터 품질 관리 부담도 커진다.

## 6기: Agentic RAG — 파이프라인에서 루프로

기존 RAG는 정해진 순서대로 한 번 실행되는 파이프라인이었다.

```text
질문 -> 검색 -> top-k 문서 -> 답변
```

Agentic RAG에서는 검색을 에이전트가 사용할 수 있는 도구로 취급한다.

```text
질문 분석
  -> 검색 필요성 판단
  -> 검색 도구와 데이터 소스 선택
  -> 검색 결과 평가
  -> 정보가 부족하면 쿼리를 수정해 재검색
  -> 근거가 충분하면 답변 생성
```

Self-RAG, CRAG, Adaptive-RAG는 구현 방식은 서로 다르지만 검색의 필요성과 결과 품질을 판단한다는 공통된 방향을 보여준다. 이러한 접근이 계획 및 도구 사용과 결합되면서 Agentic RAG로 이어진다.

다만 반복 검색은 모델 호출 횟수, 응답 시간, 비용과 실패 지점을 늘린다. 따라서 모든 질문에 가장 복잡한 구조를 적용하기보다 질문과 데이터의 특성에 맞는 단순한 구조부터 시작해야 한다.

## 세대별 요약

| 시기 | 대표 방식 | 해결하려는 문제 | 남은 한계 |
| --- | --- | --- | --- |
| 2019~2021 | DPR, 원조 RAG | 의미 검색과 외부 지식 기반 생성 | 검색기 및 생성기의 학습 복잡도 |
| 2022~2023 | Naive RAG | LLM에 새로운 문서를 쉽게 연결 | 검색 실패, 청킹에 의한 문맥 손실 |
| 2023~2024 | Advanced·Modular RAG | 검색과 컨텍스트 품질 개선 | 파이프라인 복잡도 증가 |
| 2024 | Self-RAG, CRAG, Adaptive-RAG | 검색 필요성 및 결과 품질 평가 | 추가 모델 호출과 지연 |
| 2024~ | RAPTOR, Contextual Retrieval, GraphRAG | 문서 전체의 문맥과 관계 보존 | 인덱싱 비용과 추출 오류 |
| 현재 | Agentic RAG | 계획·검색·평가·재검색의 반복 | 비용, 지연, 제어 및 평가 난이도 |

## 정리

RAG의 발전은 벡터 검색 성능만 높이는 과정이 아니었다. 초기 RAG는 외부 문서를 검색해 생성 모델에 전달하는 데 집중했다. 이후에는 검색 실패와 문맥 손실을 줄이기 위해 하이브리드 검색, 리랭킹, 쿼리 재작성, 계층 검색과 그래프 검색이 등장했다. 최근에는 검색 결과를 그대로 신뢰하지 않고, 검색 필요성과 근거의 품질을 평가해 재검색하는 방향으로 발전하고 있다.

## 궁금한 점 / 더 알아볼 것

- [ ] RAG 구조가 복잡해질수록 얻는 정확도 향상이 비용과 지연을 감수할 만큼 클지
- [ ] 복잡한 RAG 기법을 추가하기 전에, 현재 검색 품질이 충분한지를 어떤 기준과 지표로 판단할 수 있을까