---
title: Elasticsearch nori 인덱스 재색인
tags: [elasticsearch, nori, korean, reindex, study]
---

# Elasticsearch nori 인덱스 재색인

한글 분석기 설정을 바꿀 때마다 인덱스를 새로 만들어야 해서 정리.

analyzer 설정은 인덱스 생성 후 바꿀 수 없다. 새 인덱스를 만들고 `_reindex` 로 옮긴 뒤 alias 를 바꾸는 게 정석.

```bash
# 1. 새 인덱스 생성 (analyzer 변경 반영)
curl -X PUT localhost:9200/notes-v2 -H 'Content-Type: application/json' -d '{
  "settings": {
    "analysis": {
      "analyzer": {
        "korean": { "type": "custom", "tokenizer": "nori_tokenizer" }
      }
    }
  }
}'

# 2. 재색인
curl -X POST localhost:9200/_reindex -H 'Content-Type: application/json' -d '{
  "source": { "index": "notes-v1" },
  "dest":   { "index": "notes-v2" }
}'

# 3. alias 교체 (무중단)
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -d '{
  "actions": [
    { "remove": { "index": "notes-v1", "alias": "notes" } },
    { "add":    { "index": "notes-v2", "alias": "notes" } }
  ]
}'
```

분석 결과 확인:

```bash
curl -X POST localhost:9200/notes-v2/_analyze -H 'Content-Type: application/json' -d '{
  "analyzer": "korean",
  "text": "인증서 만료로 API 서버가 안 뜬다"
}'
```

처음부터 alias 로 붙여두면 나중에 교체가 편하다. v1 을 alias 없이 직접 쓰다가 고생했다.

BM25 랑 벡터 검색 차이는 [[pgvector-vs-elasticsearch-검색방식]] 에 정리.
