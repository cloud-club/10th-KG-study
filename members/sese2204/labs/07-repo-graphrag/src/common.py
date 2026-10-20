"""공용 설정 — 경로, 클라이언트(OpenAI 호환 LLM 게이트웨이 · Neo4j · Elasticsearch), 캐시."""
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

LAB = Path(__file__).resolve().parent.parent
REPO = LAB.parents[3]
OUT = LAB / "outputs"  # 캐시·중간 산출물 (git 무시)
OUT.mkdir(exist_ok=True)

load_dotenv(REPO / ".env")

CHAT_MODEL = os.getenv("GRAPHRAG_CHAT_MODEL", "gpt-5.4-mini")
EMBED_MODEL = os.getenv("GRAPHRAG_EMBED_MODEL", "gemini-embedding-2")  # 3072차원
EMBED_DIM = 3072
ES_INDEX = "repo_chunks"


def llm():
    """OpenAI 호환 엔드포인트. 루트 .env 의 LLM_BASE_URL · LLM_API_KEY 를 쓴다."""
    from openai import OpenAI

    return OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"])


def neo4j_driver():
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        f"bolt://localhost:{os.getenv('NEO4J_BOLT_PORT', '7687')}",
        auth=("neo4j", os.getenv("NEO4J_PASSWORD", "kgstudy2026")),
    )


def es():
    from elasticsearch import Elasticsearch

    return Elasticsearch(f"http://localhost:{os.getenv('ES_PORT', '9200')}")


class JsonCache:
    """키(프롬프트 해시) → 결과. LLM·임베딩 호출을 다시 돌려도 같은 결과가 나오게 한다."""

    def __init__(self, name):
        self.path = OUT / f"{name}.jsonl"
        self.data = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                rec = json.loads(line)
                self.data[rec["k"]] = rec["v"]

    @staticmethod
    def key(*parts):
        return hashlib.sha256("\x00".join(map(str, parts)).encode()).hexdigest()[:24]

    def get(self, k):
        return self.data.get(k)

    def put(self, k, v):
        self.data[k] = v
        with self.path.open("a") as f:
            f.write(json.dumps({"k": k, "v": v}, ensure_ascii=False) + "\n")


def embed(texts, cache=None, batch=32):
    """gemini-embedding-2 로 임베딩. 캐시에 있으면 호출하지 않는다."""
    cache = cache or JsonCache("embeddings")
    client = llm()
    out = [None] * len(texts)
    todo = []
    for i, t in enumerate(texts):
        hit = cache.get(JsonCache.key(EMBED_MODEL, t))
        if hit is None:
            todo.append(i)
        else:
            out[i] = hit
    for s in range(0, len(todo), batch):
        idx = todo[s : s + batch]
        resp = client.embeddings.create(model=EMBED_MODEL, input=[texts[i] for i in idx])
        for i, d in zip(idx, resp.data):
            out[i] = d.embedding
            cache.put(JsonCache.key(EMBED_MODEL, texts[i]), d.embedding)
    return out
