"""data/raw/*.md -> data/processed/chunks.jsonl

세 세대를 공정하게 비교하려면 입력이 같아야 한다. 그래서 청킹은 여기서 한 번만
하고, 1세대(ES)와 2세대(pgvector)는 똑같은 chunks.jsonl을 각자의 저장 구조로
옮겨 담기만 한다. (0세대는 청킹조차 안 한다 — 그게 0세대의 정의다)

마크다운 헤딩 경계를 우선 지키고, 너무 긴 절만 문자 수로 자른다.
헤딩 경로를 청크에 함께 넣어 두는 건 Contextual Retrieval의 값싼 버전이다.
"""
import json
import re
import unicodedata

from common import CHUNKS, RAW

MAX_CHARS = 700
OVERLAP = 100
META = re.compile(r"^<!--meta (.*?) -->\n", re.S)
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def split_sections(text: str):
    """(헤딩 경로, 본문) 목록으로 자른다."""
    stack, buf, out = [], [], []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            out.append((" > ".join(stack), body))
        buf.clear()

    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            flush()
            level = len(m.group(1))
            del stack[level - 1:]
            stack.append(m.group(2).strip())
        else:
            buf.append(line)
    flush()
    return out


def window(body: str):
    """긴 본문을 문단 경계 우선으로 자르고, 넘치면 문자 수로 자른다."""
    if len(body) <= MAX_CHARS:
        return [body]
    pieces, cur = [], ""
    for para in body.split("\n\n"):
        if len(cur) + len(para) + 2 <= MAX_CHARS:
            cur = f"{cur}\n\n{para}" if cur else para
            continue
        if cur:
            pieces.append(cur)
        while len(para) > MAX_CHARS:
            pieces.append(para[:MAX_CHARS])
            para = para[MAX_CHARS - OVERLAP:]
        cur = para
    if cur:
        pieces.append(cur)
    return pieces


def main() -> None:
    n_doc = n_chunk = 0
    with CHUNKS.open("w", encoding="utf-8") as f:
        for path in sorted(RAW.glob("*.md")):
            text = unicodedata.normalize("NFC", path.read_text(encoding="utf-8"))
            m = META.match(text)
            source = json.loads(m.group(1))["source"] if m else path.name
            if m:
                text = text[m.end():]

            title = source.rsplit("/", 1)[-1].removesuffix(".md")
            n_doc += 1
            for heading, body in split_sections(text):
                for piece in window(body):
                    # 헤딩 경로를 본문 앞에 붙여 청크 혼자서도 맥락이 서게 한다.
                    prefix = f"{title} > {heading}" if heading else title
                    record = {
                        "id": f"{path.stem}#{n_chunk}",
                        "source": source,
                        "title": title,
                        "heading": heading,
                        "text": f"{prefix}\n\n{piece}",
                        "raw_text": piece,
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    n_chunk += 1

    print(f"청킹 완료: 문서 {n_doc}개 -> 청크 {n_chunk}개  ({CHUNKS})")


if __name__ == "__main__":
    main()
