#!/usr/bin/env python3
"""documents.jsonl을 BM25 JSON과 저장된 dense vector 인덱스로 변환합니다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 검색 인덱스 생성")
    parser.add_argument(
        "--documents",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "Data" / "documents.jsonl",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "Data" / "index",
    )
    parser.add_argument(
        "--model",
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    args = parser.parse_args()

    records = [
        json.loads(line)
        for line in args.documents.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError(f"청크 데이터가 비어 있습니다: {args.documents}")

    args.index_dir.mkdir(parents=True, exist_ok=True)
    (args.index_dir / "bm25.json").write_text(
        json.dumps(
            {
                "type": "bm25",
                "source": str(args.documents),
                "documents": records,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    model = SentenceTransformer(args.model)
    embeddings = model.encode(
        [record["text"] for record in records],
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    np.save(args.index_dir / "vectors.npy", np.asarray(embeddings, dtype=np.float32))
    (args.index_dir / "metadata.json").write_text(
        json.dumps({"model": args.model, "count": len(records)}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"BM25 문서 {len(records):,}개와 vector 인덱스를 저장했습니다: {args.index_dir}")


if __name__ == "__main__":
    main()
