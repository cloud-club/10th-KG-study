"""같은 Instagram 코퍼스의 Nori BM25·pgvector·RRF 검색."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from instagram_common import REPO_ROOT
from fetch_topic_instagram import valid_permalink

OWNER = "kdyann-w3-hybrid-search-v1"
DIMENSION = 384
MODEL_NAME = "intfloat/multilingual-e5-small"
RRF_C = 60
SOURCES = {
    "own": REPO_ROOT / "data/kdyann/processed/instagram_documents.jsonl",
    "reference": REPO_ROOT / "data/kdyann/processed/instagram_topic_documents.jsonl",
}
OUTPUT_DIR = REPO_ROOT / "data/kdyann/processed/hybrid_search"


def load_corpus() -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for corpus, path in SOURCES.items():
        seen: set[str] = set()
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not rows:
            raise ValueError(f"{corpus} 코퍼스가 비어 있습니다.")
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip():
                raise ValueError(f"{corpus} 문서 ID가 올바르지 않습니다.")
            identifier = row["id"]
            if identifier in seen:
                raise ValueError(f"{corpus} 코퍼스에 중복 ID가 있습니다: {identifier}")
            seen.add(identifier)
            text = row.get("text")
            if not isinstance(text, str) or not text.strip() or not valid_permalink(row.get("permalink")):
                raise ValueError(f"{corpus} 문서에 유효한 캡션·Instagram URL이 필요합니다: {identifier}")
            if identifier in merged:
                merged[identifier]["provenance"].append(corpus)
            else:
                merged[identifier] = {"id": identifier, "text": text.strip(), "permalink": row["permalink"],
                                      "corpus": corpus, "provenance": [corpus],
                                      "published_at": row.get("published_at"), "collected_at": row.get("collected_at")}
    return [merged[identifier] for identifier in sorted(merged)]


def load_search_env() -> None:
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        return
    allowed = {"ES_URL", "PG_DSN", "W3_ES_INDEX", "W3_PG_TABLE", "EMBED_MODEL"}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.strip().removeprefix("export ").partition("=")
        name = name.strip()
        if not separator or name not in allowed or name in os.environ:
            continue
        value = value.strip()
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f".env의 {name} 따옴표를 확인하세요.")
            value = value[1:-1]
        os.environ[name] = value


def settings() -> dict[str, str]:
    load_search_env()
    values = {"es_index": os.environ.get("W3_ES_INDEX", "kdyann_hybrid_posts"),
              "pg_table": os.environ.get("W3_PG_TABLE", "kdyann_hybrid_posts"),
              "es_url": os.environ.get("ES_URL", "http://127.0.0.1:9200").rstrip("/"),
              "pg_dsn": os.environ.get("PG_DSN", "postgresql://kg:kg@127.0.0.1:5432/kg"),
              "model": os.environ.get("EMBED_MODEL", MODEL_NAME)}
    if values["model"] != MODEL_NAME:
        raise ValueError("이번 실습의 임베딩 모델은 intfloat/multilingual-e5-small입니다.")
    for name in ("es_index", "pg_table"):
        value = values[name]
        if not re.fullmatch(r"kdyann_hybrid_[a-z0-9_]+", value) or len(value) > 45:
            raise ValueError(f"{name}는 45자 이하의 kdyann_hybrid_ 전용 이름이어야 합니다.")
    return values


def corpus_manifest(documents: list[dict[str, Any]]) -> dict[str, Any]:
    payload = json.dumps(documents, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"owner": OWNER, "sources": {name: str(path.relative_to(REPO_ROOT)) for name, path in SOURCES.items()},
            "model": MODEL_NAME, "dimension": DIMENSION, "fingerprint": hashlib.sha256(payload).hexdigest(),
            "document_count": len(documents), "corpus_counts": {scope: sum(row["corpus"] == scope for row in documents)
                                                               for scope in SOURCES}}


def check_manifest(actual: dict[str, Any], expected: dict[str, Any], *, indexing: bool = False) -> None:
    keys = ("owner", "sources", "model", "dimension") if indexing else tuple(expected)
    if not isinstance(actual, dict) or any(actual.get(key) != expected[key] for key in keys):
        raise ValueError("검색 인덱스의 소유·출처·모델·코퍼스 정보가 다릅니다. 03 index_search.py를 실행하세요.")
    if not indexing and actual.get("status") != "ready":
        raise ValueError("검색 인덱싱이 완료되지 않았습니다. 03 index_search.py를 실행하세요.")


class SearchBackendError(RuntimeError):
    pass


def es_request(method: str, path: str, body: Any = None, content_type: str = "application/json") -> dict[str, Any]:
    data = body if isinstance(body, bytes) else (None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8"))
    req = Request(f"{settings()['es_url']}/{path.lstrip('/')}", method=method, data=data,
                  headers={"Content-Type": content_type, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        raise SearchBackendError(f"Elasticsearch HTTP {error.code}") from None
    except (URLError, OSError):
        raise SearchBackendError("Elasticsearch 연결에 실패했습니다.") from None


@lru_cache(maxsize=1)
def embedding_model():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME, local_files_only=True)
    if model.get_sentence_embedding_dimension() != DIMENSION:
        raise ValueError("임베딩 모델 차원이 384가 아닙니다.")
    return model


def vector_literal(values) -> str:
    numbers = [float(value) for value in values]
    if len(numbers) != DIMENSION or not all(math.isfinite(number) for number in numbers):
        raise ValueError("384차원의 유한한 임베딩이 필요합니다.")
    if not math.isclose(sum(number * number for number in numbers), 1.0, abs_tol=1e-3):
        raise ValueError("임베딩이 정규화되지 않았습니다.")
    return "[" + ",".join(str(number) for number in numbers) + "]"


def reciprocal_rank_fusion(bm25: list[dict[str, Any]], vector: list[dict[str, Any]], c: int = RRF_C) -> list[dict[str, Any]]:
    if isinstance(c, bool) or not isinstance(c, int) or c < 0:
        raise ValueError("RRF 순위 상수는 0 이상의 정수여야 합니다.")
    rows: dict[str, dict[str, Any]] = {}
    for component, ranked in (("bm25", bm25), ("vector", vector)):
        seen: set[str] = set()
        rank = 0
        for row in ranked:
            identifier = row["id"]
            if identifier in seen:
                continue
            seen.add(identifier)
            rank += 1
            result = rows.setdefault(identifier, {**row, "score": 0.0, "bm25_rank": None, "vector_rank": None})
            result[f"{component}_rank"] = rank
            result["score"] += 1.0 / (c + rank)
    return sorted(rows.values(), key=lambda row: (-row["score"], row["id"]))


class HybridSearch:
    def __init__(self):
        self.config = settings()
        self.documents = load_corpus()
        self.by_id = {row["id"]: row for row in self.documents}
        self.manifest = corpus_manifest(self.documents)
        self._checked = False
        self._query_vectors: dict[str, str] = {}

    def _ensure_indexed(self) -> None:
        if self._checked:
            return
        import psycopg
        from psycopg import sql
        index = self.config["es_index"]
        mapping = es_request("GET", f"{index}/_mapping")[index]["mappings"]
        check_manifest(mapping.get("_meta", {}), self.manifest)
        if es_request("GET", f"{index}/_count")["count"] != len(self.documents):
            raise ValueError("Elasticsearch 문서 수가 현재 코퍼스와 다릅니다.")
        with psycopg.connect(self.config["pg_dsn"]) as connection, connection.cursor() as cursor:
            cursor.execute(sql.SQL("SELECT manifest FROM {} WHERE id = 1").format(sql.Identifier(self.config["pg_table"] + "_metadata")))
            row = cursor.fetchone()
            check_manifest(row[0] if row else {}, self.manifest)
            cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(self.config["pg_table"])))
            if cursor.fetchone()[0] != len(self.documents):
                raise ValueError("pgvector 문서 수가 현재 코퍼스와 다릅니다.")
        self._checked = True

    def _bm25(self, query: str, count: int, scope: str) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"size": count, "query": {"bool": {"must": [{"match": {"text": query}}]}},
                                "sort": [{"_score": "desc"}, {"id": "asc"}]}
        if scope != "all":
            body["query"]["bool"]["filter"] = [{"term": {"corpus": scope}}]
        response = es_request("POST", f"{self.config['es_index']}/_search", body)
        return [{**self.by_id[hit["_id"]], "score": float(hit["_score"])} for hit in response["hits"]["hits"]]

    def _vector(self, query: str, count: int, scope: str) -> list[dict[str, Any]]:
        import psycopg
        from psycopg import sql
        if query not in self._query_vectors:
            values = embedding_model().encode([f"query: {query}"], normalize_embeddings=True)[0]
            self._query_vectors[query] = vector_literal(values)
        literal = self._query_vectors[query]
        table = sql.Identifier(self.config["pg_table"])
        where = sql.SQL("") if scope == "all" else sql.SQL("WHERE corpus = %s")
        tie_order = sql.SQL("") if scope == "all" else sql.SQL(", id")
        statement = sql.SQL("SELECT id, 1 - (embedding <=> %s::vector) AS score FROM {} {} ORDER BY embedding <=> %s::vector{} LIMIT %s").format(table, where, tie_order)
        params = [literal] + ([] if scope == "all" else [scope]) + [literal, count]
        with psycopg.connect(self.config["pg_dsn"]) as connection, connection.cursor() as cursor:
            # Avoid filtered ANN under-return for own/reference subsets; scan the matching subset exactly.
            if scope != "all":
                cursor.execute("SET LOCAL enable_indexscan = off")
            else:
                cursor.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(max(100, count)),))
            cursor.execute(statement, params)
            matches = cursor.fetchall()
        rows = [{**self.by_id[identifier], "score": float(score)} for identifier, score in matches]
        return sorted(rows, key=lambda row: (-row["score"], row["id"]))

    def search(self, query: str, mode: str = "hybrid", limit: int = 5, candidates: int = 20, scope: str = "all") -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip() or len(query) > 10000:
            raise ValueError("검색 질문은 1~10,000자여야 합니다.")
        if mode not in {"bm25", "vector", "hybrid"} or scope not in {"own", "reference", "all"}:
            raise ValueError("검색 mode 또는 scope가 올바르지 않습니다.")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (limit, candidates)) or not 1 <= limit <= candidates <= 1000:
            raise ValueError("검색 상한은 1 <= limit <= candidates <= 1000이어야 합니다.")
        self._ensure_indexed()
        query = query.strip()
        bm25 = self._bm25(query, candidates, scope) if mode in {"bm25", "hybrid"} else []
        vector = self._vector(query, candidates, scope) if mode in {"vector", "hybrid"} else []
        rows = reciprocal_rank_fusion(bm25, vector) if mode == "hybrid" else (bm25 if mode == "bm25" else vector)
        if any(row["id"] not in self.by_id or (scope != "all" and row["corpus"] != scope) for row in rows):
            raise ValueError("검색 결과가 현재 코퍼스·범위를 벗어났습니다.")
        return rows[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--mode", choices=("bm25", "vector", "hybrid"), default="hybrid")
    parser.add_argument("--scope", choices=("own", "reference", "all"), default="all")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = HybridSearch().search(args.query, args.mode, args.limit, args.candidates, args.scope)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for rank, row in enumerate(rows, 1):
            print(f"{rank}. {row['id']} [{row['corpus']}] {row['score']:.6f}")
            print("   " + " ".join(row["text"].split())[:180])
            print("   " + row["permalink"])


if __name__ == "__main__":
    main()
