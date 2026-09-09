---
title: 검색의 세 세대 - grep, BM25, 벡터 검색
date: 2026-09-09
tags: [information-retrieval, grep, bm25, embedding, hnsw]
status: done
---

# 02. 검색의 세 세대 - grep, BM25, 벡터 검색

## 핵심 질문: "내 문서를 찾는다"는 것이 왜 어려운가

사람이 정보를 찾을 때 떠올리는 표현과 문서 작성 당시 사용한 표현은 다르다. 문서에는 "마감 직전에 일을 시작한다"라고 적었지만 나중에는 "미루는 습관"으로 검색할 수 있다. 두 문장은 비슷한 의미를 가지지만 같은 문자열이나 단어를 포함하지 않는다.

또한 검색은 단순히 일치하는 문서의 존재를 확인하는 작업이 아니다. 문서가 많아지면 다음 문제를 함께 해결해야 한다.

- 같은 의미를 다른 표현으로 작성한 문서를 찾을 수 있어야 한다.
- 여러 문서 중 질문에 더 관련 있는 결과를 먼저 보여줘야 한다.
- 한국어의 조사, 어미, 복합명사와 띄어쓰기를 적절히 처리해야 한다.
- 문서가 많아져도 사용자가 기다리지 않도록 빠르게 검색해야 한다.
- 검색 결과가 실제로 질문의 답을 포함하는지 평가할 수 있어야 한다.

## 0세대: grep 문자열 매칭

### 검색 원리

`grep`은 입력 파일을 읽으면서 사용자가 지정한 문자열이나 정규 표현식 패턴과 일치하는 행을 출력한다([GNU Grep Manual](https://www.gnu.org/software/grep/manual/grep.html)). 별도의 검색 인덱스를 만들지 않아도 바로 사용할 수 있다.

```bash
grep -Rni "집중" ./documents
```

위 명령은 `documents` 폴더에서 "집중"이라는 문자열이 포함된 행을 찾는다. 데이터는 일반 텍스트 파일로만 존재하면 되며 검색 전에 별도의 형태소 분석이나 임베딩 생성 과정이 필요하지 않다.

### 장점

- 설치와 전처리가 거의 필요 없다.
- 검색 결과가 나온 이유가 명확하다.
- 오류 코드, 함수명, 고유명사처럼 정확한 문자열을 찾는 데 강하다.
- 정규 표현식을 사용해 다양한 문자 패턴을 표현할 수 있다.

### 한계

#### 표현 불일치

`grep`은 패턴과 일치하는 문자열을 찾기 때문에 의미가 같더라도 표현이 다르면 검색하지 못한다.

```text
검색어: 미루는 습관
문서:   마감 직전에야 일을 시작한다
```

두 문장의 의미는 관련 있지만 일치하는 문자열이 없으므로 그대로는 검색되지 않는다. 정규 표현식으로 동의어를 나열할 수 있지만 가능한 표현을 사용자가 미리 알아야 한다.

#### 관련도 순위 없음

`grep`의 목적은 패턴과 일치하는 행을 선택하는 것이다. 어떤 결과가 질문에 더 중요한지 계산하는 검색 점수는 제공하지 않는다. 결과가 수백 개라면 사용자가 직접 필요한 문서를 골라야 한다. 정보 검색에서는 여러 결과 중 사용자의 정보 요구에 가장 적합한 문서를 위에 배치하는 ranked retrieval이 중요하다([Manning et al.](https://nlp.stanford.edu/IR-book/html/htmledition/scoring-term-weighting-and-the-vector-space-model-1.html)).

## 1세대: 키워드 검색

### 역색인

키워드 검색 엔진은 검색할 때마다 모든 문서를 처음부터 읽지 않는다. 먼저 문서를 토큰으로 나눈 뒤, 각 토큰이 어느 문서에 등장했는지 역색인에 저장한다.

```text
집중  -> [문서 1, 문서 3]
타이머 -> [문서 1, 문서 2]
습관  -> [문서 2, 문서 3]
```

일반적인 postings에는 문서 ID뿐만 아니라 단어 빈도와 위치도 함께 저장할 수 있다. 검색 시에는 질문에 포함된 토큰의 postings만 조회하므로 전체 문서를 순차 탐색하는 것보다 효율적이다([Manning et al.](https://nlp.stanford.edu/IR-book/html/htmledition/a-first-take-at-building-an-inverted-index-1.html)).

### TF-IDF

모든 단어가 문서의 의미를 같은 정도로 나타내지는 않는다. TF-IDF는 다음 두 값을 결합해 단어의 중요도를 계산한다.

- **TF(Term Frequency)**: 특정 단어가 한 문서 안에서 얼마나 자주 등장하는가
- **IDF(Inverse Document Frequency)**: 해당 단어가 전체 문서에서 얼마나 희귀한가

IDF의 기본 형태는 다음과 같다([Manning et al.](https://nlp.stanford.edu/IR-book/html/htmledition/inverse-document-frequency-1.html)).

```text
idf(t) = log(N / df(t))
```

`N`은 전체 문서 수이고 `df(t)`는 단어 `t`가 등장한 문서 수다. "문서"처럼 거의 모든 글에 등장하는 단어보다 "HNSW"처럼 일부 글에만 등장하는 단어가 더 높은 가중치를 받는다.

### BM25

BM25는 TF-IDF의 핵심 아이디어에 단어 빈도 포화와 문서 길이 정규화를 추가한 확률적 순위 함수다([Robertson & Zaragoza, 2009](https://doi.org/10.1561/1500000019)).

```text
score(D, Q)
  = Σ IDF(q)
      × tf(q, D) × (k1 + 1)
        / (tf(q, D) + k1 × (1 - b + b × |D| / avgdl))
```

- `tf(q, D)`: 단어 `q`가 문서 `D`에 등장한 횟수
- `|D|`: 현재 문서의 길이
- `avgdl`: 전체 문서의 평균 길이
- `k1`: 단어가 반복될 때 점수가 증가하는 정도와 포화 속도
- `b`: 문서 길이를 얼마나 보정할지 결정하는 값

같은 단어가 문서에 반복될수록 관련도는 높아지지만 그 증가 폭은 점차 줄어든다. 또한 긴 문서는 우연히 검색어를 더 많이 포함할 가능성이 있으므로 평균 문서 길이를 기준으로 점수를 보정한다. Elasticsearch는 BM25를 기본 similarity로 사용한다([Elasticsearch Similarity settings](https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity)).

### 한국어 토크나이징: 형태소 분석과 n-gram

영어는 공백을 기준으로 단어를 나누는 방식이 어느 정도 동작하는데 한국어는 명사 뒤에 조사와 어미가 붙고 복합명사가 만들어진다.

```text
"사용자들이 검색했습니다"
-> 사용자 / 들 / 이 / 검색 / 하 / 았 / 습니다
```

어떻게 토큰을 나누느냐에 따라 역색인에 저장되는 단어와 검색 결과가 달라진다.

#### 형태소 분석: Nori

Elasticsearch의 Nori 분석기는 `mecab-ko-dic` 사전을 이용해 한국어를 형태소 단위로 분석한다([Elasticsearch Nori plugin](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori)). 복합명사를 원형 그대로 둘지, 분해할지, 원형과 분해 결과를 모두 보존할지 설정할 수 있으며 사용자 사전도 추가할 수 있다([Nori tokenizer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer)).

형태소 단위로 의미 있는 토큰을 만들기 때문에 검색 정밀도가 좋고 불필요한 토큰을 줄일 수 있다. 반면 사전에 없는 신조어, 서비스명, 오탈자는 기대한 방식으로 분석되지 않을 수 있으므로 도메인 용어를 사용자 사전에 관리해야 한다.

#### 문자 단위 분할: n-gram

n-gram은 문자열을 연속된 `n`개의 문자 조각으로 나눈다. 예를 들어 2-gram을 사용하면 다음과 같다.

```text
검색엔진 -> 검색 / 색엔 / 엔진
```

사전에 의존하지 않으므로 신조어, 일부 문자열, 띄어쓰기 변형에도 일치할 가능성이 높다. 그러나 하나의 단어에서 많은 토큰이 생성되어 인덱스 크기가 커지고, 의미 없는 부분 문자열까지 일치해 검색 노이즈가 늘어날 수 있다([Elasticsearch N-gram tokenizer](https://www.elastic.co/docs/reference/text-analysis/analysis-ngram-tokenizer)).

| 구분 | 형태소 분석 | n-gram |
| --- | --- | --- |
| 분할 기준 | 언어적 형태소와 사전 | 연속된 문자 조각 |
| 장점 | 의미 있는 토큰, 높은 정밀도 | 신조어와 부분 문자열 대응 |
| 단점 | 미등록 단어와 사전 관리 | 큰 인덱스와 검색 노이즈 |
| 적합한 예 | 본문 검색, 일반적인 한국어 문장 | 자동완성, 상품명, 서비스명, 오탈자 일부 대응 |

## 2세대: 벡터 검색

### 임베딩

임베딩 모델은 단어나 문장을 고정된 차원의 숫자 벡터로 변환한다. 학습 과정에서 의미가 유사한 문장은 벡터 공간에서도 가까워지도록 만든다.

SBERT는 문장을 서로 독립적으로 인코딩한 뒤 코사인 유사도로 비교할 수 있게 해 대규모 의미 검색을 실용적으로 수행할 수 있도록 했다([Reimers & Gurevych, 2019](https://aclanthology.org/D19-1410/)). DPR은 질문과 문서를 각각 인코딩하는 dual-encoder를 학습해 dense passage retrieval을 구현했다([Karpukhin et al., 2020](https://aclanthology.org/2020.emnlp-main.550/)).

```text
"일을 계속 미루고 있어"       -> [0.12, -0.31, 0.77, ...]
"마감 직전에야 시작하는 습관" -> [0.15, -0.29, 0.74, ...]
```

두 문장에 같은 단어가 거의 없어도 의미가 비슷하다면 가까운 벡터가 될 수 있다.

### 코사인 유사도

코사인 유사도는 두 벡터 사이의 각도를 이용해 방향이 얼마나 비슷한지 측정한다.

```text
cosine_similarity(q, d) = (q · d) / (||q|| ||d||)
```

벡터의 크기보다 방향을 비교하기 때문에 문장 임베딩의 유사도를 측정할 때 널리 사용한다. 값이 클수록 두 벡터의 방향이 비슷하다([Manning et al.](https://nlp.stanford.edu/IR-book/html/htmledition/queries-as-vectors-1.html)). 실제로 사용할 때는 임베딩 모델이 권장하는 거리 함수가 코사인 유사도인지, 내적인지, 유클리드 거리인지 확인해야 한다.

### Exact Nearest Neighbor와 ANN

가장 정확한 방법은 질문 벡터를 저장된 모든 문서 벡터와 비교하는 것이다. 이 방식은 정확한 최근접 이웃을 찾지만, 데이터가 많아질수록 계산해야 하는 거리의 수도 함께 증가한다.

ANN(Approximate Nearest Neighbor)은 모든 벡터를 확인하지 않고 가까울 가능성이 높은 후보만 탐색한다. 일부 정답을 놓칠 가능성을 허용하는 대신 검색 속도를 높인다. ANN의 핵심은 속도와 recall 사이의 trade-off

데이터가 적을 때는 정확 검색이 더 단순하고 충분히 빠를 수 있다. 실제로 pgvector는 기본적으로 exact nearest neighbor search를 사용하며 필요할 때 HNSW나 IVFFlat 인덱스를 추가하도록 제공한다([pgvector](https://github.com/pgvector/pgvector)).

### HNSW

HNSW(Hierarchical Navigable Small World)는 벡터를 서로 가까운 이웃과 연결한 다층 그래프로 구성한다([Malkov & Yashunin, 2018](https://arxiv.org/abs/1603.09320)).

```text
상위 계층: 멀리 이동하는 적은 수의 연결로 후보 영역을 빠르게 찾음
하위 계층: 가까운 이웃이 많은 그래프에서 세밀하게 탐색함
```

검색은 연결이 적은 상위 계층에서 시작해 질문 벡터와 가까운 영역으로 빠르게 이동한 뒤, 아래 계층으로 내려오며 더 가까운 이웃을 찾는다. 모든 벡터를 순차 비교하지 않기 때문에 대규모 데이터에서 빠른 근사 검색이 가능하다.

대신 다음 비용이 발생한다.

- 그래프 인덱스를 만들기 위한 시간과 메모리가 필요하다.
- 삽입 및 인덱스 구축이 단순 저장보다 느리다.
- 탐색 범위를 줄이면 검색은 빨라지지만 관련 문서를 놓칠 수 있다.
- 탐색 범위를 늘리면 recall은 좋아지지만 검색 시간이 길어진다.

## 각 방법은 무엇을 잡고 무엇을 놓치는가

| 구분 | grep | BM25 | 벡터 검색 |
| --- | --- | --- | --- |
| 핵심 신호 | 문자열 일치 | 단어 빈도와 희소성 | 벡터 공간의 의미적 유사성 |
| 저장 구조 | 원본 텍스트 파일 | 역색인과 postings | 원문, 임베딩 벡터, ANN 인덱스 |
| 순위 | 기본적으로 없음 | 관련도 점수 제공 | 거리 또는 유사도 점수 제공 |
| 강점 | 정확한 문자열과 패턴 | 고유명사, 키워드, 희귀 용어 | 동의어, 의도, 표현이 다른 문장 |
| 약점 | 표현 불일치 | 단어가 겹치지 않으면 누락 | 정확한 철자, 숫자, 도메인 밖 표현 |
| 전처리 | 거의 없음 | 토크나이징과 분석기 | 청킹과 임베딩 생성 |
| 확장 방식 | 파일 순차 탐색 | 역색인 | exact search 또는 ANN |
| 설명 가능성 | 매우 높음 | 어떤 단어가 기여했는지 확인 가능 | 벡터가 가까운 이유를 해석하기 어려움 |

세 검색 방식은 완전한 대체 관계가 아니다. 오류 코드나 정확한 제품명은 grep과 BM25가 더 안정적으로 찾을 수 있고, 사용자의 의도와 의미가 중요한 자연어 질문은 벡터 검색이 유리할 수 있다. BEIR은 dense retrieval의 성능이 도메인에 따라 달라질 수 있음을 보여주므로, 벡터 검색이 항상 키워드 검색보다 우수하다고 일반화해서는 안 된다([Thakur et al., 2021](https://arxiv.org/abs/2104.08663)).

## 동일한 문서에서 세 방식 비교하기

다음과 같은 두 문서가 있다고 가정한다.

```text
문서 A: 할 일을 자꾸 미루는 사람을 위한 5분 타이머 기능
문서 B: 마감 직전에 시작하는 습관을 줄이는 집중 루틴
```

#### 검색어: `5분 타이머`

- grep은 정확한 문자열이 있는 문서 A를 찾는다.
- BM25도 희귀한 핵심 단어가 일치하는 문서 A에 높은 점수를 줄 수 있다.
- 벡터 검색도 문서 A를 찾을 수 있지만 숫자와 정확한 기능명에서는 키워드 방식이 더 안정적일 수 있다.

#### 검색어: `일을 미루지 않도록 도와주는 방법`

- grep은 전체 문장과 일치하는 문자열이 없어 두 문서를 모두 놓칠 수 있다.
- BM25는 "일", "미루다"처럼 분석된 일부 토큰이 겹치는 문서 A를 찾을 수 있다.
- 벡터 검색은 "미루는 사람"과 "마감 직전에 시작하는 습관"의 의미를 이용해 문서 A와 B를 함께 찾을 수 있다.


> 참고 자료:
>
> - [GNU Grep Manual](https://www.gnu.org/software/grep/manual/grep.html)
> - Manning, Raghavan & Schütze, [Introduction to Information Retrieval](https://nlp.stanford.edu/IR-book/html/htmledition/irbook.html) (2008)
> - Robertson & Zaragoza, [The Probabilistic Relevance Framework: BM25 and Beyond](https://doi.org/10.1561/1500000019) (2009)
> - Elasticsearch, [Similarity settings](https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity)
> - Elasticsearch, [Korean (Nori) analysis plugin](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori)
> - Elasticsearch, [Nori tokenizer](https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer)
> - Elasticsearch, [N-gram tokenizer](https://www.elastic.co/docs/reference/text-analysis/analysis-ngram-tokenizer)
> - Reimers & Gurevych, [Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks](https://aclanthology.org/D19-1410/) (2019)
> - Karpukhin et al., [Dense Passage Retrieval for Open-Domain Question Answering](https://aclanthology.org/2020.emnlp-main.550/) (2020)
> - Thakur et al., [BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models](https://arxiv.org/abs/2104.08663) (2021)
> - Malkov & Yashunin, [Efficient and Robust Approximate Nearest Neighbor Search Using HNSW](https://arxiv.org/abs/1603.09320) (2018)
> - [pgvector 공식 문서](https://github.com/pgvector/pgvector)
