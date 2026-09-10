"""Instagram 검색 문서를 Elasticsearch Nori/BM25 인덱스에 적재한다."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from common import ES_INDEX, ES_URL, load_documents, metric, rate


INDEX_CONFIG = {
    "settings": {
        "index": {"max_ngram_diff": 1},
        "analysis": {
            "tokenizer": {
                "korean_nori": {"type": "nori_tokenizer", "decompound_mode": "mixed"},
                "korean_ngram": {"type": "ngram", "min_gram": 2, "max_gram": 3},
            },
            "analyzer": {
                "korean_nori_analyzer": {
                    "type": "custom",
                    "tokenizer": "korean_nori",
                    "filter": ["nori_part_of_speech", "nori_readingform", "lowercase"],
                },
                "korean_ngram_analyzer": {
                    "type": "custom",
                    "tokenizer": "korean_ngram",
                    "filter": ["lowercase"],
                },
            },
        },
    },
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "id": {"type": "keyword"},
            "source": {"type": "keyword"},
            "text": {
                "type": "text",
                "analyzer": "korean_nori_analyzer",
                "fields": {
                    "ngram": {"type": "text", "analyzer": "korean_ngram_analyzer"}
                },
            },
            "hashtags": {"type": "keyword"},
            "media_type": {"type": "keyword"},
            "media_product_type": {"type": "keyword"},
            "permalink": {"type": "keyword", "index": False},
            "published_at": {"type": "date"},
            "collected_at": {"type": "date"},
            "views": {"type": "long"},
            "reach": {"type": "long"},
            "likes": {"type": "long"},
            "comments": {"type": "long"},
            "saved": {"type": "long"},
            "shares": {"type": "long"},
            "total_interactions": {"type": "long"},
            "engagement_rate": {"type": "double"},
            "save_rate": {"type": "double"},
            "share_rate": {"type": "double"},
        },
    },
}


def request(method: str, path: str, body: Any | None = None, content_type: str = "application/json") -> dict[str, Any]:
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(
        f"{ES_URL}/{path.lstrip('/')}",
        data=data,
        method=method,
        headers={"Content-Type": content_type, "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Elasticsearch 요청 실패(HTTP {error.code}): {detail[:500]}") from error
    except URLError as error:
        raise RuntimeError(f"Elasticsearch에 연결할 수 없습니다: {ES_URL}") from error


def es_document(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": document["id"],
        "source": document["source"],
        "text": document["text"],
        "hashtags": document.get("hashtags", []),
        "media_type": document.get("media_type"),
        "media_product_type": document.get("media_product_type"),
        "permalink": document.get("permalink"),
        "published_at": document.get("published_at"),
        "collected_at": document.get("collected_at"),
        **{name: metric(document, name) for name in (
            "views", "reach", "likes", "comments", "saved", "shares", "total_interactions"
        )},
        **{name: rate(document, name) for name in (
            "engagement_rate", "save_rate", "share_rate"
        )},
    }


def index_documents() -> int:
    documents = load_documents()
    try:
        request("DELETE", ES_INDEX)
    except RuntimeError as error:
        if "HTTP 404" not in str(error):
            raise
    request("PUT", ES_INDEX, INDEX_CONFIG)

    lines: list[str] = []
    for document in documents:
        lines.append(json.dumps({"index": {"_index": ES_INDEX, "_id": document["id"]}}))
        lines.append(json.dumps(es_document(document), ensure_ascii=False))
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    response = request("POST", "_bulk", payload, "application/x-ndjson")
    if response.get("errors"):
        failures = [item for item in response.get("items", []) if item.get("index", {}).get("error")]
        raise RuntimeError(f"Elasticsearch bulk 적재 실패: {len(failures)}건")
    request("POST", f"{ES_INDEX}/_refresh")
    return request("GET", f"{ES_INDEX}/_count")["count"]


def main() -> None:
    count = index_documents()
    print(f"[Elasticsearch BM25] 적재 완료: {count}문서")
    print(f"인덱스: {ES_INDEX}")
    print("분석기: Nori(mixed), 비교용 text.ngram(2~3글자)")


if __name__ == "__main__":
    main()
