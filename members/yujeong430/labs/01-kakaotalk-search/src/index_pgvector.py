"""다국어 임베딩을 생성해 PostgreSQL + pgvector HNSW 인덱스에 저장한다."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import psycopg
from sentence_transformers import SentenceTransformer

MODEL_NAME, DIMENSION = "intfloat/multilingual-e5-small", 384
def vector_literal(vector) -> str: return "[" + ",".join(str(float(value)) for value in vector) + "]"

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True); parser.add_argument("--dsn", default="postgresql://study:study@127.0.0.1:5433/search_study"); parser.add_argument("--model", default=MODEL_NAME); parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    chunks = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    model = SentenceTransformer(args.model)
    if model.get_sentence_embedding_dimension() != DIMENSION: raise ValueError(f"예상 차원 {DIMENSION}과 모델 차원이 다릅니다.")
    embeddings = model.encode([f"passage: {chunk['content']}" for chunk in chunks], batch_size=args.batch_size, normalize_embeddings=True, show_progress_bar=True)
    with psycopg.connect(args.dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector"); cursor.execute("DROP TABLE IF EXISTS document_chunks")
            cursor.execute(f"CREATE TABLE document_chunks (id TEXT PRIMARY KEY, date TEXT NOT NULL, source TEXT NOT NULL, message_count INTEGER NOT NULL, char_count INTEGER NOT NULL, content TEXT NOT NULL, embedding VECTOR({DIMENSION}) NOT NULL)")
            cursor.executemany("INSERT INTO document_chunks (id, date, source, message_count, char_count, content, embedding) VALUES (%s, %s, %s, %s, %s, %s, %s::vector)", [(c["id"], c["date"], c["source"], c["message_count"], c["char_count"], c["content"], vector_literal(v)) for c, v in zip(chunks, embeddings)])
            cursor.execute("CREATE INDEX document_chunks_embedding_hnsw_idx ON document_chunks USING hnsw (embedding vector_cosine_ops)"); cursor.execute("SELECT COUNT(*) FROM document_chunks"); count = cursor.fetchone()[0]
        connection.commit()
    print(f"임베딩 모델: {args.model}"); print(f"pgvector HNSW 적재 청크 수: {count}")

if __name__ == "__main__": main()
