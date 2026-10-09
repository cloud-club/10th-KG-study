"""검토된 W6 문서를 고정하고 비교 실습 전용 BM25·벡터 인덱스를 만든다."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(LAB.parent / "03-hybrid-search/src"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", type=Path,
                        default=ROOT / "data/kdyann/processed/content_graph/w6-reviewed/documents.jsonl")
    parser.add_argument("--index", action="store_true", help="별도 실습용 ES·PG 인덱스도 생성/갱신")
    args = parser.parse_args()
    with args.documents.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    if not rows or any(row.get("corpus") not in ("own", "reference") for row in rows):
        parser.error("own/reference로 검토한 문서가 필요합니다.")
    if len({row["id"] for row in rows}) != len(rows):
        parser.error("문서 ID가 중복됩니다.")
    output = ROOT / "data/kdyann/processed/graphrag_comparison"
    corpus = output / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    for scope in ("own", "reference"):
        selected = [row for row in rows if row["corpus"] == scope]
        if not selected:
            parser.error("내 글과 참고 글이 모두 필요합니다.")
        (corpus / f"{scope}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected), encoding="utf-8")
    if args.index:
        os.environ["W3_CORPUS_DIR"] = str(corpus)
        os.environ["W3_ES_INDEX"] = "kdyann_hybrid_w6_posts"
        os.environ["W3_PG_TABLE"] = "kdyann_hybrid_w6_posts"
        import index_search
        index_search.OUTPUT_DIR = output
        manifest = index_search.index_documents()
        print(json.dumps({key: manifest[key] for key in
                          ("document_count", "fingerprint", "es_index", "pg_table")}, ensure_ascii=False))
    else:
        print(json.dumps({"corpus_dir": str(corpus), "documents": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
