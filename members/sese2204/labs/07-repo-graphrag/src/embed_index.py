"""청크 임베딩 → Elasticsearch(nori BM25 + dense_vector) · Neo4j 벡터 인덱스.

v1 리트리버(BM25 + 벡터 + RRF)는 ES 만 쓴다. Neo4j 벡터 인덱스는 v2 가 "벡터로 시작점 → 같은 DB 에서 확장"을
한 쿼리로 보여 주는 데 쓴다. 임베딩은 outputs/embeddings.jsonl 에 캐시된다.

실행: python embed_index.py   (load_structure.py 다음)
"""
import json

from elasticsearch import helpers

from common import EMBED_DIM, ES_INDEX, OUT, embed, es, neo4j_driver

WIKI_INDEX = "wiki_chunks"

ES_SETTINGS = {
    "analysis": {
        "tokenizer": {"nori_mixed": {"type": "nori_tokenizer", "decompound_mode": "mixed"}},
        "analyzer": {
            "ko": {"type": "custom", "tokenizer": "nori_mixed", "filter": ["lowercase", "nori_part_of_speech"]}
        },
    }
}
ES_MAPPINGS = {
    "properties": {
        "member": {"type": "keyword"},
        "path": {"type": "keyword"},
        "week": {"type": "integer"},
        "title": {"type": "text", "analyzer": "ko"},
        "heading": {"type": "text", "analyzer": "ko"},
        "text": {"type": "text", "analyzer": "ko"},
        "embedding": {"type": "dense_vector", "dims": EMBED_DIM, "index": True, "similarity": "cosine"},
    }
}


def embed_input(doc, c):
    # 제목·소제목을 붙여 임베딩한다 — 청크만으로는 무슨 문서의 어느 절인지 잃는다
    return f"{doc['title']} / {c['heading']}\n{c['text']}"


def main():
    docs = json.loads((OUT / "corpus.json").read_text())
    rows = [(d, c) for d in docs for c in d["chunks"]]
    vecs = embed([embed_input(d, c) for d, c in rows])
    print(f"embedded {len(vecs)}")

    client = es()
    client.indices.delete(index=ES_INDEX, ignore_unavailable=True)
    client.indices.create(index=ES_INDEX, settings=ES_SETTINGS, mappings=ES_MAPPINGS)
    helpers.bulk(
        client,
        (
            {
                "_index": ES_INDEX,
                "_id": c["id"],
                "member": d["member"],
                "path": d["path"],
                "week": d["week"],
                "title": d["title"],
                "heading": c["heading"],
                "text": c["text"],
                "embedding": v,
            }
            for (d, c), v in zip(rows, vecs)
        ),
        chunk_size=200,
    )
    client.indices.refresh(index=ES_INDEX)
    print("es docs", client.count(index=ES_INDEX)["count"])

    with neo4j_driver() as drv, drv.session() as s:
        payload = [{"id": c["id"], "v": v} for (d, c), v in zip(rows, vecs)]
        for i in range(0, len(payload), 300):
            s.run(
                "UNWIND $rows AS r MATCH (c:Chunk {id: r.id}) CALL db.create.setNodeVectorProperty(c, 'embedding', r.v)",
                rows=payload[i : i + 300],
            )
        s.run(
            f"""CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS FOR (c:Chunk) ON c.embedding
            OPTIONS {{indexConfig: {{`vector.dimensions`: {EMBED_DIM}, `vector.similarity_function`: 'cosine'}}}}"""
        )
        print("neo4j chunks with embedding", s.run("MATCH (c:Chunk) WHERE c.embedding IS NOT NULL RETURN count(c) AS n").single()["n"])


def wiki_rows(from_snapshot=False):
    """위키 페이지를 코퍼스와 같은 방식으로 청킹한다. 스냅샷에서 불러왔으면 그때의 청크를 그대로 쓴다
    (위키는 계속 고쳐지므로, 지금 wiki/ 를 다시 읽으면 스냅샷 임베딩과 맞지 않는다)."""
    from corpus import chunk, parse_frontmatter
    from common import REPO

    if from_snapshot:
        return json.loads((OUT / "wiki_chunks.json").read_text())
    rows = []
    for p in json.loads((OUT / "wiki.json").read_text()):
        fm, body = parse_frontmatter((REPO / p["path"]).read_text())
        body = body.split("\n## 출처")[0]  # 출처 목록은 검색 대상에서 뺀다
        for i, (h, t) in enumerate(chunk(body)):
            rows.append({"id": f"{p['name']}#{i}", "page": p["name"], "title": p["title"], "heading": h, "text": t})
    (OUT / "wiki_chunks.json").write_text(json.dumps(rows, ensure_ascii=False))
    return rows


def index_wiki(from_snapshot=False):
    """v3 용 — 위키 청크를 별도 인덱스(wiki_chunks)에. v1·v2 는 이 인덱스를 읽지 않는다."""
    rows = wiki_rows(from_snapshot)
    vecs = embed([f"{r['title']} / {r['heading']}\n{r['text']}" for r in rows])
    client = es()
    client.indices.delete(index=WIKI_INDEX, ignore_unavailable=True)
    mappings = {"properties": dict(ES_MAPPINGS["properties"], page={"type": "keyword"})}
    client.indices.create(index=WIKI_INDEX, settings=ES_SETTINGS, mappings=mappings)
    helpers.bulk(client, ({"_index": WIKI_INDEX, "_id": r["id"], **r, "embedding": v} for r, v in zip(rows, vecs)))
    client.indices.refresh(index=WIKI_INDEX)
    print("wiki chunks", client.count(index=WIKI_INDEX)["count"])


if __name__ == "__main__":
    import sys

    # --snapshot: snapshot.py load 로 되돌린 위키 청크를 쓴다 (키 없이 스냅샷 임베딩으로 인덱스를 만들 때)
    if "--wiki" not in sys.argv:
        main()
    index_wiki(from_snapshot="--snapshot" in sys.argv)
