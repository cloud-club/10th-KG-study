# **세 가지 검색 방식의 데이터 저장 구조**

이번 실습에서는 grep / Elasticsearch BM25 / pgvector를 비교하기 위해 **세 방식 모두 동일한 chunk를 사용**했다.

## **1. 공통 데이터 생성 (내 데이터 저장 방식)**

Notion 원본을 Markdown으로 가져온 뒤, `chunk.py`를 통해 검색에 사용할 작은 단위로 분리한다.

```
Notion ZIP
    ↓
collect_notion.py
    ↓
data/raw/             # Notion Markdown 원본 131개
    ↓
chunk.py
    ↓
data/chunks.jsonl     # 1,562 chunks
```

각 chunk는 다음과 같은 구조를 가진다.

```json
{
  "chunk_id": "obs:daily/2026-03-14#2",
  "doc_id": "obs:daily/2026-03-14",
  "source": "notion",
  "ord": 2,
  "text": "검색에 사용할 실제 문서 내용...",
  "created_at": "2026-03-14T21:12:00+09:00",
  "meta": {
    "title": "문서 제목",
    "tags": []
  }
}
```

`chunk_id`는 각 문서 조각을 구분하는 **공통 식별자**다.

세 검색 방식에 서로 다른 데이터를 넣으면 검색 결과를 제대로 비교할 수 없기 때문에, 동일한 `chunks.jsonl`을 세 방식의 공통 입력으로 사용했다.

---

## **2. grep — 파일 그대로 저장**

```
chunks.jsonl
    ↓
gen0_grep.py
    ↓
문자열 직접 검색
```

grep은 별도의 DB나 검색 인덱스를 만들지 않는다.

`chunks.jsonl`에 저장된 `text`를 직접 읽으면서 검색 문자열이 포함되어 있는지 확인한다.

```
저장 위치 : data/chunks.jsonl
저장 형태 : JSONL 파일
추가 인덱스 : 없음
```

즉, 검색할 때마다 파일을 직접 확인하는 가장 단순한 구조다.

---

## **3. Elasticsearch — 역색인으로 저장**

```
chunks.jsonl
      ↓
  gen1_es.py
      ↓
Elasticsearch
      ↓
   역색인
```

Elasticsearch에는 각 chunk가 하나의 document로 들어간다.

특히 `text`는 같은 원문을 **nori와 n-gram 두 방식으로 분석**할 수 있도록 구성했다.

```
text
├── nori   → 한국어 형태소 기반
└── ngram  → 글자 조각 기반
```

개념적으로는 다음과 같은 **단어 → 문서** 구조의 역색인이 만들어진다.

```
"캐시"
 ├── chunk_17
 ├── chunk_31
 └── chunk_82

"Redis"
 ├── chunk_17
 └── chunk_82
```

이를 이용해 BM25가 각 chunk의 관련도 점수를 계산하고 검색 결과에 순위를 매긴다.

```
저장 위치 : Elasticsearch
저장 단위 : chunk = ES document
검색 구조 : Inverted Index
검색 기준 : BM25
Analyzer  : nori + n-gram
```

---

## **4. pgvector — 원문과 임베딩 저장**

```
chunks.jsonl
      ↓
gen2_pgvector.py
      ↓
┌──────────── PostgreSQL ────────────┐
│                                    │
│ chunks            emb_bge_m3       │
│ 원문/메타데이터     1024차원 벡터     │
│       └──── chunk_id ────┘         │
└────────────────────────────────────┘
```

PostgreSQL에는 크게 두 종류의 데이터를 저장한다.

### **`chunks`**

원래 chunk의 정보와 실제 문서 내용을 저장한다.

```
chunk_id
doc_id
source
ord
text
created_at
meta
```

### **`emb_bge_m3`**

각 chunk의 `text`를 BGE-M3 모델에 넣어 만든 **1024차원 embedding**을 저장한다.

```
chunk_id
embedding
```

예를 들어 하나의 chunk는 다음처럼 연결된다.

```
chunks

chunk_id = chunk_17
text = "Redis Look-Aside 캐시 전략을 적용했다."
        │
        │ chunk_id
        ▼
emb_bge_m3

chunk_id = chunk_17
embedding = [-0.026, -0.011, 0.038, ...]
```

그리고 embedding에는 HNSW 인덱스를 생성하여 가까운 벡터를 빠르게 검색할 수 있도록 했다.

```
저장 위치 : PostgreSQL + pgvector
원문 저장 : chunks
벡터 저장 : emb_bge_m3
연결 기준 : chunk_id
Embedding : BAAI/bge-m3, 1024차원
검색 구조 : HNSW
검색 기준 : Cosine Distance
```

---

## **5. 세 방식 비교**

|  | **grep** | **Elasticsearch** | **pgvector** |
| --- | --- | --- | --- |
| 공통 입력 | `chunks.jsonl` | `chunks.jsonl` | `chunks.jsonl` |
| 실제 저장 | JSONL 파일 | Elasticsearch Index | PostgreSQL |
| 저장 단위 | chunk | ES document | row |
| 추가 구조 | 없음 | 역색인 | Embedding + HNSW |
| 검색 기준 | 문자열 일치 | 단어 관련도 | 의미적 거리 |
| 대표 검색 | `SeCause` | `Redis 캐시 전략` | `성능을 개선한 경험` |

전체 구조를 한 번에 보면 다음과 같다.

```
                    Notion 원본
                        ↓
                      chunk.py
                        ↓
                  chunks.jsonl
                  1,562 chunks
                        │
          ┌─────────────┼─────────────┐
          ↓             ↓             ↓
        grep       Elasticsearch    pgvector
          │             │             │
      JSONL 직접       역색인      PostgreSQL
        검색          + BM25       + Embedding
                                      + HNSW
          │             │             │
          ↓             ↓             ↓
       문자열          단어           의미
        검색           검색           검색
```

### **정리**

결국 세 방식 모두 **같은 `chunk_id`와 `text`에서 출발하지만 검색을 위해 데이터를 저장하는 방식이 다르다.**

- **grep**: 추가 저장 없이 원본 chunk를 직접 검색
- **Elasticsearch**: 단어를 빠르게 찾고 순위를 계산하기 위해 **역색인** 생성
- **pgvector**: 의미가 비슷한 문서를 찾기 위해 **문장을 벡터로 변환하여 저장**

따라서 이번 실습에서는 검색 알고리즘뿐 아니라 **검색 방식에 따라 같은 데이터가 어떤 형태로 저장되는지**까지 비교할 수 있었다.