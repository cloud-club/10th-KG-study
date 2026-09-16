"""질의를 임베딩해 pgvector HNSW 코사인 검색을 수행한다."""
from __future__ import annotations
import argparse
import psycopg
from sentence_transformers import SentenceTransformer
from index_pgvector import MODEL_NAME, vector_literal

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query"); parser.add_argument("--dsn", default="postgresql://study:study@127.0.0.1:5433/search_study"); parser.add_argument("--model", default=MODEL_NAME); parser.add_argument("--top-k", type=int, default=5); parser.add_argument("--explain", action="store_true", help="HNSW index 실행 계획을 출력")
    args = parser.parse_args(); model = SentenceTransformer(args.model); vector = model.encode([f"query: {args.query}"], normalize_embeddings=True)[0]
    with psycopg.connect(args.dsn) as connection, connection.cursor() as cursor:
        cursor.execute("SET hnsw.ef_search = 100")
        if args.explain:
            cursor.execute("SET enable_seqscan = off")
            cursor.execute("EXPLAIN (COSTS OFF) SELECT id FROM document_chunks ORDER BY embedding <=> %s::vector LIMIT %s", (vector_literal(vector), args.top_k))
            print("HNSW 실행 계획:")
            for (line,) in cursor.fetchall():
                print("  Order By: embedding <=> query_vector" if "Order By:" in line else f"  {line}")
        cursor.execute("SELECT id, date, content, 1 - (embedding <=> %s::vector) AS cosine_similarity FROM document_chunks ORDER BY embedding <=> %s::vector LIMIT %s", (vector_literal(vector), vector_literal(vector), args.top_k)); rows = cursor.fetchall()
    for rank, (chunk_id, date, content, similarity) in enumerate(rows, 1): print(f"{rank}. cosine_similarity={similarity:.3f} id={chunk_id} date={date}"); print(f"   {content.replace(chr(10), ' ')[:180]}")

if __name__ == "__main__": main()
