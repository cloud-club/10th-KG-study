"""Elasticsearch BM25와 pgvector 검색을 같은 청크 ID 순위로 반환한다."""
from __future__ import annotations

from collections.abc import Sequence

from common import EMBED_MODEL, ES_INDEX, HNSW_EF_SEARCH, vec_literal
from models import Chunk, RankedHit, SearchFilters


def _es_query(query: str, filters: SearchFilters) -> dict:
    clauses: list[dict] = []
    if filters.room:
        clauses.append({"term": {"room": filters.room}})
    if filters.date_from:
        clauses.append({"range": {"end_at": {"gte": filters.date_from.isoformat()}}})
    if filters.date_to:
        clauses.append({"range": {"start_at": {"lt": filters.date_to.isoformat()}}})
    body: dict = {"must": [{"match": {"text": query}}]}
    if clauses:
        body["filter"] = clauses
    return {"bool": body}


def bm25_search(es, conn, query: str, limit: int, filters: SearchFilters) -> list[RankedHit]:
    if limit < 1:
        return []
    response = es.search(
        index=ES_INDEX,
        query=_es_query(query, filters),
        size=limit,
        sort=[{"_score": {"order": "desc"}}, {"chunk_id": {"order": "asc"}}],
        track_scores=True,
        source=False,
    )
    hits = [
        (int(hit["_id"]), float(hit.get("_score") or 0.0))
        for hit in response["hits"]["hits"]
    ]
    chunks = fetch_chunks(conn, [chunk_id for chunk_id, _ in hits])
    return [
        RankedHit(
            chunk_id=chunk_id,
            content_hash=chunks[chunk_id].content_hash,
            rank=rank,
            score=score,
            source="bm25",
        )
        for rank, (chunk_id, score) in enumerate(hits, start=1)
    ]


def _vector_where(filters: SearchFilters) -> tuple[str, list]:
    clauses = ["e.model = %s"]
    params: list = [EMBED_MODEL]
    if filters.room:
        clauses.append("r.name = %s")
        params.append(filters.room)
    if filters.date_from:
        clauses.append("c.end_at >= %s")
        params.append(filters.date_from)
    if filters.date_to:
        clauses.append("c.start_at < %s")
        params.append(filters.date_to)
    return " AND ".join(clauses), params


def vector_search(
    conn,
    query_vector: Sequence[float],
    limit: int,
    filters: SearchFilters,
    *,
    exact: bool = False,
) -> list[RankedHit]:
    if limit < 1:
        return []
    literal = vec_literal(list(query_vector))
    where, params = _vector_where(filters)
    with conn.transaction(), conn.cursor() as cur:
        if exact:
            cur.execute("SELECT set_config('enable_indexscan', 'off', true)")
        else:
            ef_search = max(HNSW_EF_SEARCH, limit)
            cur.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(ef_search),))
            cur.execute("SELECT set_config('hnsw.iterative_scan', 'strict_order', true)")
        cur.execute(
            f"""SELECT c.id, c.content_hash, 1 - (e.embedding <=> %s::vector) AS cosine
                FROM chunk_embeddings e
                JOIN chunks c ON c.id = e.chunk_id
                JOIN rooms r ON r.id = c.room_id
                WHERE {where}
                ORDER BY e.embedding <=> %s::vector
                LIMIT %s""",
            [literal] + params + [literal, limit],
        )
        rows = [
            (int(chunk_id), content_hash, float(score))
            for chunk_id, content_hash, score in cur.fetchall()
        ]
    # 부동소수점 완전 동점만 chunk_id로 고정한다. 일반 순서는 DB의 거리 순위를 유지한다.
    rows = sorted(enumerate(rows), key=lambda item: (-item[1][2], item[1][0], item[0]))
    return [
        RankedHit(
            chunk_id=chunk_id,
            content_hash=content_hash,
            rank=rank,
            score=score,
            source="vector",
        )
        for rank, (_, (chunk_id, content_hash, score)) in enumerate(rows, start=1)
    ]


def fetch_chunks(conn, chunk_ids: Sequence[int]) -> dict[int, Chunk]:
    ids = list(dict.fromkeys(int(chunk_id) for chunk_id in chunk_ids))
    if not ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """SELECT c.id, c.content_hash, r.name, c.start_at, c.end_at,
                      c.start_seq, c.end_seq, c.participants, c.text
               FROM chunks c JOIN rooms r ON r.id = c.room_id
               WHERE c.id = ANY(%s)""",
            (ids,),
        )
        rows = cur.fetchall()
    chunks = {
        int(row[0]): Chunk(
            chunk_id=int(row[0]),
            content_hash=row[1],
            room=row[2],
            start_at=row[3],
            end_at=row[4],
            start_seq=int(row[5]),
            end_seq=int(row[6]),
            participants=tuple(row[7]),
            text=row[8],
        )
        for row in rows
    }
    missing = sorted(set(ids) - set(chunks))
    if missing:
        raise RuntimeError(
            "Elasticsearch/평가 결과에 Postgres에 없는 chunk_id가 있습니다: "
            f"{missing[:10]}. 재청킹했다면 index_es.py --recreate가 필요합니다."
        )
    return chunks


def corpus_counts(conn, es) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM chunks")
        chunks = int(cur.fetchone()[0])
        cur.execute("SELECT count(*) FROM chunk_embeddings WHERE model = %s", (EMBED_MODEL,))
        embeddings = int(cur.fetchone()[0])
    es_chunks = int(es.count(index=ES_INDEX)["count"])
    return {"postgres_chunks": chunks, "embeddings": embeddings, "elasticsearch_chunks": es_chunks}


def assert_corpus_aligned(counts: dict[str, int]) -> None:
    if not counts or len(set(counts.values())) != 1:
        raise RuntimeError(f"검색 저장소 건수가 다릅니다: {counts}")
