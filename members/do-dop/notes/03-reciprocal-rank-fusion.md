---
title: "하이브리드 검색 결과 합치기: RRF와 Score-based Fusion"
date: 2026-09-17
tags: [rrf, reciprocal-rank-fusion, hybrid-search, bm25, elasticsearch, opensearch, score-normalization, score-based-fusion, min-max-normalization]
status: done
---

# 하이브리드 검색 결과 합치기: RRF와 Score-based Fusion

[지난 노트](03-beir-benchmark.md)에서 BEIR를 보고 내린 결론은 "BM25와 Dense Retrieval 둘 다 강점이 다르니 함께 써야 한다"였다. 그러면 자연스럽게 다음 질문이 따라온다. 두 검색기의 결과를 어떻게 하나로 합칠까? 이번 노트는 이 질문에 대한 두 가지 답 — 등수를 합치는 **RRF(Reciprocal Rank Fusion)**와 점수 자체를 정규화해서 합치는 **Score-based Fusion**을 Elasticsearch·OpenSearch 공식 문서를 기준으로 정리해본다.

## 문제: 왜 점수를 그냥 더하면 안 되는가

BM25와 벡터 검색은 점수가 나오는 방식 자체가 다르다.

```text
BM25
  문서 A → 13.24점
  문서 B → 9.72점

벡터 검색 (코사인 유사도)
  문서 A → 0.78
  문서 C → 0.91
```

`13.24 + 0.78`처럼 그냥 더해버리면 값의 크기가 훨씬 큰 BM25 점수가 결과를 사실상 지배해버린다. 두 숫자는 애초에 같은 자로 잰 게 아니라서 더하는 것 자체가 성립하지 않는다.

이제부터 이 문제에 대한 두 가지 답 — RRF와 Score-based Fusion — 을 따로 정리한다.

## Part 1. RRF (Reciprocal Rank Fusion)

RRF의 아이디어는 여기서 출발한다. "점수를 비교하지 말고, 몇 등을 했는지만 보자"는 것이다. 점수는 검색기마다 스케일이 다르지만, 등수(rank)는 어느 검색기든 1등부터 시작하는 공통 언어이기 때문이다.

### 1. 공식

```python
score = 0.0

for q in queries:
    if d in result(q):
        score += 1.0 / (k + rank(result(q), d))

return score
```

- `k`: 순위 상수(rank constant)
- `q`: 여러 검색 쿼리 중 하나 (또는 여기서는 서로 다른 검색기 하나하나로 이해해도 된다)
- `d`: 검색 결과에 포함된 문서
- `result(q)`: 검색 결과 집합
- `rank(result(q), d)`: 그 집합에서 문서 `d`의 등수 (1등부터 시작)

이름을 그대로 풀면 이해가 더 쉽다. **Rank**(등수) → **Reciprocal**(역수, `1/등수`) → **Fusion**(합치기). 다만 실제로는 `1/rank`가 아니라 `1/(k+rank)`를 쓰는데, 이유는 아래 4절에서 다룬다.

### 2. Elasticsearch RRF retriever의 주요 파라미터

| 파라미터 | 의미 |
|---|---|
| `retrievers` | 결합할 하위 검색기(child retriever) 배열. 최소 2개 필요, 모두 동일한 가중치로 결합된다 |
| `rank_constant` | 위 공식의 `k`. 정수, 1 이상, 기본값 60. 커질수록 낮은 순위 문서의 영향력이 상대적으로 커진다 |
| `rank_window_size` | 각 검색기가 RRF 계산에 넘길 후보 개수. 크게 잡으면 관련성은 좋아질 수 있지만 계산 비용도 커진다. 최종 응답은 요청의 `size`만큼만 다시 잘린다 |

([Elasticsearch RRF retriever 공식 문서](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/rrf-retriever) 기준.)

### 3. 손으로 계산해보는 예제

공식 문서에 나온 예제를 그대로 따라가 보면 감이 확실히 잡힌다. 문서 5개, 벡터는 이해를 돕기 위해 1차원으로 단순화했다.

```text
문서 1: text="rrf",         vector=[5]
문서 2: text="rrf rrf",     vector=[4]
문서 3: text="rrf rrf rrf", vector=[3]
문서 4: text="rrf rrf rrf rrf", vector 없음
문서 5: text 없음,           vector=[0]
```

BM25 검색("rrf")과 kNN 검색(질의 벡터 `[3]`)을 각각 돌리면 등수가 이렇게 나온다.

```text
        BM25   kNN
문서 4   1위    -      (벡터가 없어서 kNN에는 아예 안 나옴)
문서 3   2위    1위
문서 2   3위    2위
문서 1   4위    3위
문서 5   -      4위    (BM25 대상 텍스트가 없어서 안 나옴)
```

`rank_constant=1`로 RRF 점수를 계산하면 (문서가 한쪽 검색기에만 나오면 그 항만 더한다):

```text
문서 1 = 1/(1+4) + 1/(1+3) = 0.4500
문서 2 = 1/(1+3) + 1/(1+2) = 0.5833
문서 3 = 1/(1+2) + 1/(1+1) = 0.8333
문서 4 =                     1/(1+1) = 0.5000
문서 5 = 1/(1+4)                     = 0.2000
```

최종 순위는 문서3(0.8333) > 문서2(0.5833) > 문서4(0.5000) > 문서1(0.4500) > 문서5(0.2000) 순이다. `rank_window_size=5`로 다섯 개를 다 계산했지만 최종 `size=3`이면 문서3·2·4만 반환된다.

여기서 직관이 보인다. 문서3은 BM25 2등, kNN 1등으로 양쪽 모두에서 상위권이라 1등을 차지했다. 문서4는 BM25 1등이지만 kNN에는 아예 안 나와서 3등으로 밀렸다. "한쪽에서 확실한 1등"보다 "양쪽에서 고르게 좋은" 문서가 유리해지는 구조인 셈이다.

### 4. `rank_constant`(k)가 결과를 어떻게 바꾸는가

같은 공식이라도 `k`값에 따라 등수 차이가 얼마나 반영되는지가 완전히 달라진다.

```text
k=1
  1위 = 1/(1+1) = 0.500
  2위 = 1/(1+2) = 0.333
  10위 = 1/(1+10) = 0.091
  → 1위와 10위 차이가 큼

k=60
  1위 = 1/(60+1) = 0.01639
  2위 = 1/(60+2) = 0.01613
  10위 = 1/(60+10) = 0.01429
  → 차이가 훨씬 작아짐
```

`k`가 작으면 "1위가 정말 중요하다"는 뜻이고, `k`가 크면 "1등부터 20등 정도까지는 엇비슷하게 보자"는 뜻이 된다. Elasticsearch가 기본값을 60으로 잡은 건 대규모 검색 결과(수천~수만 건 후보)를 염두에 둔 값이다.

이건 이론으로만 끝난 얘기가 아니라 이번 주 실습([03-company-analysis-kg](../labs/03-company-analysis-kg/README.md))에서도 그대로 나타났다. 57개 청크짜리 우리 코퍼스에서 BM25 1등(점수 21.56, 2등과 격차가 컸다)이었던 문서가 벡터 검색 후보에는 아예 없었는데, `k=60`으로 RRF를 돌리자 이 문서가 11위로 밀려났다. `k`를 1로 낮추자 다시 정답 위치(top-5 안)로 돌아왔다. 작은 코퍼스에 큰 데이터셋용 기본값을 그대로 쓰면 오히려 손해를 볼 수 있다는 걸 실측으로 확인한 셈이다.

### 5. 한쪽 검색기에만 나온 문서는 어떻게 처리되나

문서4가 kNN에서 아예 안 나왔을 때 0점이나 꼴찌 취급을 받은 게 아니라, 그 검색기의 항만 공식에서 빠졌을 뿐이다. `for q in queries: if d in result(q):` 조건문이 정확히 이 역할을 한다. 등장하지 않으면 그 항의 기여가 없을 뿐이지, 벌점을 받는 게 아니다.

우리 실습에서도 같은 패턴이 나왔다(README의 q009 사례). 정답 청크 하나가 벡터 검색에서만 2위였고 BM25 후보 20개 안에는 아예 없었는데, RRF 점수는 벡터 쪽 기여분(`1/(60+2)`)만 받고 BM25 쪽은 0으로 처리됐다 — 두 검색기 모두에서 어중간하게 걸친 다른 문서들에 밀렸다.

### 6. RRF의 약점: 원래 점수 차이를 버린다

```text
BM25
  문서 A: 1위, score 50
  문서 B: 2위, score 49        ← A와 거의 차이 없음

Vector
  문서 A: 1위, similarity 0.99
  문서 B: 2위, similarity 0.51  ← A가 압도적으로 유사
```

벡터 검색에서는 A와 B의 실제 유사도 차이가 크다. 그런데 RRF는 등수만 보기 때문에 "A=1위, B=2위"라는 사실만 남고, 그 격차가 얼마나 컸는지는 버려진다.

이것도 이론으로만 끝내지 않고 실제로 검증해봤다. `search_common/score_fusion.py`에 점수를 정규화해서 더하는 방식을 따로 구현해 RRF와 비교했는데, BM25에서 20개 후보 중 압도적 1위(21.56점, 2위는 16.41점)였던 문서가 벡터 검색에는 없었던 사례에서, RRF는 이 문서를 11위로 묻어버렸지만 점수 정규화 방식은 원래 점수 격차를 반영해 4위로 살려냈다. 반대로 코퍼스를 넓히자(57개→69개 청크) 이번엔 RRF가 이기고 점수 정규화가 밀리는 결과가 나왔다. 어느 방식이 이기는지는 코퍼스 구성에 따라 달라지는 것 같다. 자세한 수치는 [labs/03-company-analysis-kg/README.md](../labs/03-company-analysis-kg/README.md)의 "점수 정규화 융합" 절에 정리해뒀다.

### 7. `rank_window_size`: 후보를 얼마나 넓게 볼 것인가

```text
BM25 rank_window_size=100  ─┐
                             ├→ RRF 계산
Vector rank_window_size=100 ┘
        ↓
최종 응답은 size 만큼만 잘라서 반환
```

후보 풀을 넓게 잡을수록(예: 100개) 놓치는 문서가 줄어들 가능성은 커지지만, 계산해야 할 후보도 그만큼 늘어난다. 우리 스크립트의 `--pool-size` 옵션이 정확히 이 역할이다 — 기본값 20으로 BM25·벡터 각각 20개씩 뽑은 뒤 RRF로 합치고 최종 `--size`(기본 5)만큼 자른다.

## Part 2. Score-based Fusion

RRF가 "등수만 보자"는 접근이라면, Score-based Fusion은 반대로 원래 점수를 살리되 스케일만 맞춰서 합치자는 접근이다. OpenSearch와 Elasticsearch 둘 다 이 방식을 공식 기능으로 제공한다(OpenSearch는 [normalization processor](https://docs.opensearch.org/latest/search-plugins/search-pipelines/normalization-processor/), Elasticsearch는 [linear retriever](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/linear-retriever)).

절차는 두 단계다.

```text
1. 정규화(normalization)
   BM25 점수  → 0~1 사이로 스케일 변환
   Vector 점수 → 0~1 사이로 스케일 변환

2. 가중합(weighted sum)
   S(d) = α · S_BM25norm(d) + β · S_vectornorm(d)
```

### 1. Min-Max 정규화

가장 흔히 쓰는 정규화가 min-max다.

```text
s' = (s - s_min) / (s_max - s_min)
```

이 결과 집합에서 가장 높은 점수는 1에, 가장 낮은 점수는 0에 가까워진다. (OpenSearch는 이 외에 L2 정규화도 지원한다.)

### 2. 손으로 계산해보는 예제

BM25와 Vector 점수를 정규화한 뒤, `α=0.4`(BM25), `β=0.6`(Vector)로 가중합해보자.

```text
         BM25(정규화)  Vector(정규화)
문서 A       1.0            0.4
문서 B       0.6            1.0

S(A) = 0.4×1.0 + 0.6×0.4 = 0.64
S(B) = 0.4×0.6 + 0.6×1.0 = 0.84
```

BM25만 보면 A가 이겼을 문서인데, Vector에서 B가 워낙 강하고 가중치도 Vector 쪽에 더 실려 있어서 최종적으로는 B가 위로 올라온다. RRF에는 없던 "어느 검색기를 얼마나 더 믿을지"를 숫자로 정하는 손잡이(α, β)가 여기엔 있는 셈이다.

### 3. RRF와 정확히 무엇이 다른가

같은 상황을 RRF와 Score-based Fusion에 각각 넣어보면 차이가 뚜렷해진다.

```text
BM25 점수: A=100, B=99   ← 사실상 거의 차이 없음
BM25 점수: A=100, B=3    ← 격차가 매우 큼

두 경우 다 RRF에서는 동일하게: A=1위, B=2위
```

RRF는 이 두 상황을 구분하지 못한다. 등수만 보기 때문에 "격차가 거의 없었다"와 "격차가 압도적이었다"가 똑같이 "1위, 2위"로 뭉개진다. Score-based Fusion은 정규화된 점수를 그대로 들고 가기 때문에 이 격차(margin)를 끝까지 보존한다.

| | RRF | Score-based Fusion |
|---|---|---|
| 무엇을 쓰나 | 등수(rank) | 정규화된 점수(score) |
| 튜닝 | 거의 불필요 (k값 하나) | 정규화 방식 + 가중치(α, β) 튜닝 필요 |
| 점수 격차 | 버림 | 보존 |
| 서로 다른 검색기 결합 | 쉬움 (스케일 신경 안 써도 됨) | 스케일에 민감, 정규화 필수 |
| 적합한 상황 | 빠르게 기본값으로 합치고 싶을 때 | 우리 데이터로 검증해서 최적 비율을 찾고 싶을 때 |

### 4. 가중치는 어떻게 정하나

보통 `Score = α·BM25norm + (1-α)·Vectornorm` 형태로 두고, α를 0.2·0.4·0.5·0.6·0.8처럼 여러 값으로 바꿔가며 Recall@k나 nDCG@k가 가장 좋은 값을 고른다. RRF가 "일단 공평하게 등수로 합쳐보자"에 가깝다면, Score-based Fusion은 "우리 데이터에서는 Vector를 BM25보다 1.5배 더 믿는 게 낫더라" 같은 데이터 기반 튜닝이 가능하다는 점이 다르다.

### 5. 실제 구현과 대조

이 개념은 [labs/03-company-analysis-kg/src/score_fusion.py](../labs/03-company-analysis-kg/src/score_fusion.py)에 그대로 구현되어 있고, 실제 데이터로 비교까지 해봤다. `_normalize()`가 여기서 말한 min-max 정규화이고, `normalized_score_fusion()`의 `bm25_weight`가 위 α에 해당한다(기본값 0.5로 동일 가중치).

실측 결과도 이론과 얼추 맞아떨어졌다. BM25에서 압도적 1위(21.56점, 2위는 16.41점)였던 문서가 Vector 후보에는 아예 없었던 경우, RRF는 이 점수 격차를 무시하고 그 문서를 11위로 묻어버렸지만, Score-based Fusion은 원래 점수 격차를 반영해 4위로 살려냈다. 반대로 코퍼스를 넓히자(57개→69개 청크) 이번엔 RRF가 이기고 Score-based Fusion이 밀리는 결과가 나왔다. "어느 방식이 항상 낫다"는 결론은 없고, 우리 평가 질문·코퍼스로 직접 재봐야 한다는 걸 다시 한번 확인한 셈이다. 자세한 수치는 [labs/03-company-analysis-kg/README.md](../labs/03-company-analysis-kg/README.md)의 "점수 정규화 융합" 절에 있다.

## 우리 프로젝트에 옮겨보면

기업분석 질문 "AMD에 HBM4를 공급하면서 엔비디아와 반도체 AI 팩토리도 구축하는 기업은?"으로 실제 검색해보면 이렇게 나온다.

```text
                       BM25 등수   Vector 등수
newsroom_005_chunk_02    2위         1위     ← 양쪽 다 최상위권
newsroom_003_chunk_02   16위         2위     ← Vector에서만 상위권
newsroom_003_chunk_01   15위         4위     ← Vector에서만 상위권
```

`newsroom_005_chunk_02`는 BM25·Vector 양쪽에서 모두 최상위권이라 RRF로 합쳐도 잘 살아남는다. 반면 `newsroom_003_chunk_01/02`(AMD·삼성전자 MOU 관련 청크)는 Vector에서는 상위권이지만 BM25에서는 15~16위로 한참 밀린다. "엔비디아·AI 팩토리" 쪽 단어가 텍스트에 더 강하게 들어있어서 BM25가 "AMD" 관련 문맥을 잘 못 잡아낸 것으로 보인다. RRF는 그래도 두 검색기 모두에 어느 정도 걸쳐 있는 문서들이라 최종 상위권에 들어오지만, BM25에서 확실한 1등이었는데 Vector에 아예 없는 문서(Part 1의 "`rank_constant`(k)가 결과를 어떻게 바꾸는가" 절에서 다룬 dart_005 사례)와는 상황이 좀 다르다.

```text
BEIR
"검색 방법마다 강점이 다르다"
        ↓
BM25 + Dense Retrieval
"그러면 둘 다 써보자"
        ↓
문제: "그런데 점수 척도가 다른데?"
        ↓
RRF
"점수 말고 등수를 합치자"
        ↓
Hybrid Retrieval
```

## 결론: 그래서 뭐가 더 좋은가

정직하게 답하면 "둘 다 항상 이기지는 않는다"이다. 이론이 아니라 같은 평가 질문 10개, 같은 청크를 갖고 실제로 재봐서 나온 결론이다.

| 코퍼스 | RRF (k=60) Recall@5 | Score-based Fusion Recall@5 |
|---|---:|---:|
| 57개 청크 (뉴스룸 10건) | 96.7% | **100%** |
| 69개 청크 (뉴스룸 14건, 무관한 문서 4건 추가) | **100%** | 96.7% |

문서를 늘리기 전과 후, 승자가 그대로 뒤집혔다. 원인도 각각 확인했다.

- **57개 청크일 때 Score-based Fusion이 이긴 이유**: `dart_005_chunk_01`이 BM25에서 20개 후보 중 압도적 1위(21.56점, 2위는 16.41점)였는데 Vector 후보에는 아예 없었다. RRF는 이 문서를 11위로 묻어버려 top-5를 놓쳤지만, Score-based Fusion은 원래 점수 격차를 살려 4위로 건져냈다.
- **69개 청크일 때 RRF가 이긴 이유**: q009(정답 청크 3개가 필요한 질문)에서 Score-based Fusion은 `newsroom_005` 문서의 청크들에 점수가 쏠려 top-5가 전부 그 문서로 채워지면서 다른 문서에 있던 정답 하나를 놓쳤다(Recall@5 = 0.667). RRF는 등수만 보기 때문에 이렇게 한 문서로 점수가 쏠리는 현상에 상대적으로 덜 휘둘렸다.

즉 "한쪽에서 압도적인 1등을 살려야 하는 상황"에서는 Score-based Fusion이 유리하고, "점수가 소수 문서에 쏠려 결과가 편향되는 상황"에서는 RRF가 유리했다. 어느 상황이 더 자주 일어나는지는 코퍼스와 질문에 따라 다르므로 미리 정할 수 없다.

**실무적으로는 이렇게 접근하면 된다.** 평가용 질문·정답 세트가 없거나 튜닝할 여유가 없다면 RRF를 기본값으로 쓴다 — 파라미터가 `k` 하나뿐이고 Elasticsearch·OpenSearch 둘 다 기본 제공 방식이라 시작하기 쉽다. 반대로 우리처럼 평가 질문 세트가 있고 Recall@k를 직접 잴 수 있다면, 두 방식을 다 구현해서 실제로 비교한 뒤 이기는 쪽을 쓰거나(혹은 α 가중치를 데이터로 튜닝하거나) 최소한 "이 코퍼스에서는 이게 더 낫더라"를 실측으로 남겨두는 게 맞다. [labs/03-company-analysis-kg](../labs/03-company-analysis-kg/)에 두 방식 다 구현해두고 계속 재보고 있는 이유가 이거다.

## 참고 자료

- [Reciprocal rank fusion — Elasticsearch Reference](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion)
- [RRF retriever — Elasticsearch Reference](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/rrf-retriever)
- [Weighted reciprocal rank fusion (RRF) in Elasticsearch — Elasticsearch Labs](https://www.elastic.co/search-labs/blog/weighted-reciprocal-rank-fusion-rrf)
- [03-beir-benchmark.md](03-beir-benchmark.md) — 이 노트의 배경이 된 BEIR 논문 정리
- [labs/03-company-analysis-kg/README.md](../labs/03-company-analysis-kg/README.md) — RRF·점수 정규화를 실제로 구현하고 비교한 실습

---

**다음 노트**: [Citation과 Provenance: 근거를 어떻게 남겨야 하는가](03-citation-and-provenance.md)
