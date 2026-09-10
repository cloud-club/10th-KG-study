"""Instagram 검색 문서를 grep용 TSV 파일로 변환한다."""

from __future__ import annotations

from common import GREP_CORPUS, load_documents, one_line


def prepare() -> int:
    documents = load_documents()
    GREP_CORPUS.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{document['id']}\t{one_line(document['text'])}" for document in documents]
    GREP_CORPUS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def main() -> None:
    count = prepare()
    print(f"[grep] 저장 완료: {count}줄")
    print(f"파일: {GREP_CORPUS}")
    print("구조: 미디어 ID<TAB>캡션 (인덱스와 순위 없음)")


if __name__ == "__main__":
    main()
