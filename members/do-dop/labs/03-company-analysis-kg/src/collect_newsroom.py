#!/usr/bin/env python3
"""공식 뉴스룸 페이지에서 기사 본문을 수집한다."""

import html
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[5]
SOURCE = Path(__file__).resolve().parents[1] / "config" / "newsroom_sources.json"
OUTPUT = ROOT / "data" / "do-dop" / "company-analysis-kg" / "raw" / "newsroom" / "documents.jsonl"
TARGET_CLASSES = {"single_contents", "post-contents"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class ArticleParser(HTMLParser):
    """뉴스룸의 본문 컨테이너 안에 있는 텍스트만 모은다."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if self.depth == 0 and classes & TARGET_CLASSES:
            self.depth = 1
            return
        if self.depth:
            if tag in VOID_TAGS:
                if not self.ignored_depth and tag == "br":
                    self.parts.append("\n")
                return
            self.depth += 1
            if tag in {"script", "style", "noscript", "figure"}:
                self.ignored_depth += 1
            if not self.ignored_depth and tag in {"p", "h2", "h3", "li", "br"}:
                self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if not self.depth:
            return
        if tag in {"script", "style", "noscript", "figure"} and self.ignored_depth:
            self.ignored_depth -= 1
        if not self.ignored_depth and tag in {"p", "h2", "h3", "li"}:
            self.parts.append("\n")
        self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.depth and not self.ignored_depth:
            self.parts.append(data)


def download_article(url: str) -> str:
    """공식 페이지를 내려받고 기사 본문을 문단 단위 텍스트로 바꾼다."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 KG-study educational collector", "Accept-Language": "ko-KR,ko;q=0.9"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8", errors="replace")

    parser = ArticleParser()
    parser.feed(page)
    lines = [re.sub(r"\s+", " ", html.unescape(line)).strip() for line in "".join(parser.parts).splitlines()]
    text = "\n".join(line for line in lines if line)
    if len(text) < 300:
        raise ValueError(f"기사 본문을 충분히 추출하지 못했습니다: {url}")
    return text


def main() -> None:
    documents = json.loads(SOURCE.read_text(encoding="utf-8"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as file:
        for document in documents:
            print(f"수집 중: {document['title']}")
            document["text"] = download_article(document["url"])
            file.write(json.dumps(document, ensure_ascii=False) + "\n")
    print(f"뉴스룸 {len(documents)}건 저장: {OUTPUT}")


if __name__ == "__main__":
    main()
