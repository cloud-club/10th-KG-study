#!/usr/bin/env python3
"""뉴스룸과 DART 데이터를 하나의 JSONL로 합친다."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DATA = ROOT / "data" / "do-dop" / "company-analysis-kg"
INPUTS = (
    DATA / "raw" / "newsroom" / "documents.jsonl",
    DATA / "raw" / "dart" / "documents.jsonl",
)
OUTPUT = DATA / "processed" / "documents.jsonl"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for path in INPUTS:
        if not path.exists():
            raise SystemExit(f"먼저 수집 스크립트를 실행해 주세요: {path}")
        lines.extend(line for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"통합 데이터 {len(lines)}건 저장: {OUTPUT}")


if __name__ == "__main__":
    main()
