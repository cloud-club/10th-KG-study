#!/usr/bin/env python3
"""Retrieve relevant Talk_*.txt chunks with BM25 and dense vector search."""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    text: str


def tokenize(text: str) -> list[str]:
    """Keep Korean, Latin, and numeric terms while ignoring punctuation."""
    return [token.lower() for token in TOKEN_RE.findall(text)]


def read_chunks(
    data_dir: Path,
    pattern: str = "Talk_*.txt",
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    paths = sorted(data_dir.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No files matching {pattern!r} found in {data_dir}")

    chunks: list[Chunk] = []
    for path in paths:
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
        if not text:
            continue
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if not paragraphs:
            continue

        buffer = ""
        chunk_number = 0
        for paragraph in paragraphs:
            if buffer and len(buffer) + len(paragraph) + 2 > chunk_size:
                chunks.append(Chunk(f"{path.name}#{chunk_number}", path.name, buffer))
                chunk_number += 1
                buffer = buffer[-overlap:] if overlap else ""
            while len(paragraph) > chunk_size:
                piece = paragraph[:chunk_size]
                chunks.append(Chunk(f"{path.name}#{chunk_number}", path.name, piece))
                chunk_number += 1
                paragraph = paragraph[chunk_size - overlap :]
            buffer = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if buffer:
            chunks.append(Chunk(f"{path.name}#{chunk_number}", path.name, buffer))
    if not chunks:
        raise ValueError(f"Text files in {data_dir} did not contain any text")
    return chunks


class BM25:
    """Small, dependency-free BM25 implementation for local corpora."""

    def __init__(self, documents: Iterable[str], k1: float = 1.5, b: float = 0.75):
        self.documents = [tokenize(document) for document in documents]
        self.k1 = k1
        self.b = b
        self.average_length = sum(map(len, self.documents)) / max(len(self.documents), 1)
        document_frequency: dict[str, int] = {}
        for document in self.documents:
            for token in set(document):
                document_frequency[token] = document_frequency.get(token, 0) + 1
        self.idf = {
            token: math.log(1 + (len(self.documents) - frequency + 0.5) / (frequency + 0.5))
            for token, frequency in document_frequency.items()
        }

    def search(self, query: str, limit: int) -> list[tuple[int, float]]:
        query_tokens = tokenize(query)
        scores: list[tuple[int, float]] = []
        for index, document in enumerate(self.documents):
            frequencies: dict[str, int] = {}
            for token in document:
                frequencies[token] = frequencies.get(token, 0) + 1
            score = 0.0
            for token in query_tokens:
                if token not in frequencies:
                    continue
                term_frequency = frequencies[token]
                denominator = term_frequency + self.k1 * (
                    1 - self.b + self.b * len(document) / max(self.average_length, 1)
                )
                score += self.idf.get(token, 0.0) * term_frequency * (self.k1 + 1) / denominator
            scores.append((index, score))
        return sorted(scores, key=lambda item: (-item[1], item[0]))[:limit]


def reciprocal_rank_fusion(
    ranked_lists: Iterable[Iterable[int]], limit: int, constant: int = 60
) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, index in enumerate(ranked, start=1):
            scores[index] = scores.get(index, 0.0) + 1 / (constant + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]


class HybridRetriever:
    def __init__(self, chunks: list[Chunk], model_name: str = DEFAULT_MODEL):
        if not chunks:
            raise ValueError("At least one chunk is required")
        self.chunks = chunks
        self.bm25 = BM25(chunk.text for chunk in chunks)
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "Vector search requires sentence-transformers. Install requirements.txt first."
            ) from error
        self.model = SentenceTransformer(model_name)
        self.embeddings = self.model.encode(
            [chunk.text for chunk in chunks],
            normalize_embeddings=True,
            show_progress_bar=True,
        )

    def search(self, query: str, limit: int = 5, candidate_limit: int = 30) -> list[dict]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit <= 0 or candidate_limit <= 0:
            raise ValueError("limit and candidate_limit must be positive")
        candidate_limit = min(candidate_limit, len(self.chunks))
        bm25_results = self.bm25.search(query, candidate_limit)
        query_embedding = self.model.encode([query], normalize_embeddings=True)[0]
        vector_scores = self.embeddings @ query_embedding
        vector_results = sorted(
            enumerate(vector_scores), key=lambda item: (-float(item[1]), item[0])
        )[:candidate_limit]
        fused = reciprocal_rank_fusion(
            ([index for index, _ in bm25_results], [index for index, _ in vector_results]),
            min(limit, len(self.chunks)),
        )
        bm25_scores = dict(bm25_results)
        vector_score_map = {index: float(score) for index, score in vector_results}
        return [
            {
                **asdict(self.chunks[index]),
                "score": score,
                "bm25_score": bm25_scores.get(index, 0.0),
                "vector_score": vector_score_map.get(index, 0.0),
            }
            for index, score in fused
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Talk_*.txt용 BM25 + 벡터 하이브리드 검색")
    parser.add_argument("query", help="검색 질의")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "Data")
    parser.add_argument("--pattern", default="Talk_*.txt")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=30)
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=120)
    args = parser.parse_args()

    chunks = read_chunks(args.data_dir, args.pattern, args.chunk_size, args.overlap)
    retriever = HybridRetriever(chunks, args.model)
    for rank, result in enumerate(
        retriever.search(args.query, args.top_k, args.candidate_k), start=1
    ):
        print(json.dumps({"rank": rank, **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
