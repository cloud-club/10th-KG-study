"""Obsidian vault(dataset/vault)를 읽어 검색용 청크 JSONL로 바꾼다.

이 파서는 Obsidian 앱을 조작하거나 전용 API를 쓰지 않는다. 폴더의 `.md` 파일을
읽어 공통 형식으로 바꾸는 로컬 전처리 스크립트다. 문서 형식(프론트매터 유무,
`##` 소제목 유무, 날짜 출처)이 폴더마다 다르므로 특정 스키마를 필수로 가정하지
않는다 — 자세한 계약은 dataset/README.md 참고.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common import CHUNKS_PATH, VAULT_DIR

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
HEADING_SPLIT_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
INLINE_TAG_RE = re.compile(r"#([\w가-힣-]+)")
WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]")
FILENAME_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


@dataclass
class Chunk:
    chunk_id: str
    source_path: str
    doc_type: str
    title: str
    heading: str | None
    content: str
    date: str | None
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    frontmatter: dict[str, Any] = field(default_factory=dict)


def parse_scalar(raw: str) -> Any:
    """아주 작은 YAML 부분집합만 지원: 문자열, `[a, b]` 목록."""
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return [item.strip().strip("'\"") for item in raw[1:-1].split(",") if item.strip()]
    return raw.strip("'\"")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """`---` 블록을 `key: value` 단위로 읽는다. 블록이 없으면 빈 dict를 돌려준다."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, raw = stripped.partition(":")
        meta[key.strip()] = parse_scalar(raw)
    return meta, text[match.end():]


def extract_tags(frontmatter: dict[str, Any], body: str) -> list[str]:
    """프론트매터 `tags`와 본문 인라인 `#태그`를 합집합으로 모은다.

    인라인 태그 정규식은 `#` 뒤에 공백 없이 단어문자가 와야 매칭되므로
    `# 제목` 같은 마크다운 헤딩과는 겹치지 않는다.
    """
    tags: set[str] = set()
    fm_tags = frontmatter.get("tags")
    if isinstance(fm_tags, list):
        tags.update(fm_tags)
    tags.update(INLINE_TAG_RE.findall(body))
    return sorted(tags)


def build_stem_index(vault_dir: Path) -> dict[str, str]:
    """`[[문서명]]` 은 확장자 없는 파일명(stem)만 담고 있어서, 실제 상대경로로
    해석하려면 vault 전체를 먼저 훑어 stem → source_path 매핑이 필요하다."""
    return {path.stem: path.relative_to(vault_dir).as_posix() for path in vault_dir.rglob("*.md")}


def extract_links(body: str, stem_index: dict[str, str]) -> list[str]:
    resolved = set()
    for target in WIKILINK_RE.findall(body):
        resolved.add(stem_index.get(target, target))
    return sorted(resolved)


def resolve_title(frontmatter: dict[str, Any], body: str, path: Path) -> str:
    """프론트매터 title → 첫 `# ` 제목 → 파일명 순으로 폴백한다."""
    fm_title = frontmatter.get("title")
    if isinstance(fm_title, str) and fm_title.strip():
        return fm_title.strip()
    match = TITLE_RE.search(body)
    if match:
        return match.group(1).strip()
    return path.stem


def resolve_date(frontmatter: dict[str, Any], path: Path) -> str | None:
    """프론트매터 date → 파일명의 `YYYY-MM-DD` → None."""
    fm_date = frontmatter.get("date")
    if isinstance(fm_date, str) and fm_date.strip():
        return fm_date.strip()
    match = FILENAME_DATE_RE.search(path.name)
    return match.group(1) if match else None


def split_by_heading(body: str) -> list[tuple[str | None, str]]:
    """`## ` 단위로 나눈다. `##`이 없으면 문서 전체를 한 조각으로 돌려준다."""
    matches = list(HEADING_SPLIT_RE.finditer(body))
    if not matches:
        content = body.strip()
        return [(None, content)] if content else []

    sections: list[tuple[str | None, str]] = []
    lead = body[: matches[0].start()].strip()
    if lead:
        sections.append((None, lead))
    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections.append((heading, body[start:end].strip()))
    return sections


def split_fixed(body: str, size: int, overlap: int) -> list[tuple[str | None, str]]:
    """`##` 구조를 무시하고 글자 수 기준 고정 크기로 자른다 (겹침 `overlap`자).

    청크 크기가 검색 품질에 미치는 영향을 실험하기 위한 비교용 전략이다.
    소제목 경계를 무시하므로 문장이 중간에서 잘릴 수 있다는 게 `heading`
    전략과의 트레이드오프.
    """
    content = body.strip()
    if not content:
        return []
    if size <= overlap:
        raise ValueError("size는 overlap보다 커야 합니다.")

    sections: list[tuple[str | None, str]] = []
    start = 0
    index = 0
    while start < len(content):
        end = min(start + size, len(content))
        piece = content[start:end].strip()
        if piece:
            sections.append((f"chunk-{index}", piece))
            index += 1
        if end == len(content):
            break
        start = end - overlap
    return sections


def parse_file(
    path: Path,
    vault_dir: Path,
    stem_index: dict[str, str],
    mode: str = "heading",
    size: int = 800,
    overlap: int = 100,
) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)

    source_path = path.relative_to(vault_dir).as_posix()
    doc_type = source_path.split("/", 1)[0]
    title = resolve_title(frontmatter, body, path)
    date = resolve_date(frontmatter, path)
    tags = extract_tags(frontmatter, body)
    links = extract_links(body, stem_index)

    # `# 제목` 줄은 title로 이미 뽑았으니 청크 본문에서는 제거한다. 안 지우면
    # `##` 구조가 있는 문서마다 "제목 한 줄짜리" 청크가 매번 앞에 하나씩 붙는다.
    chunk_body = TITLE_RE.sub("", body, count=1)

    sections = split_by_heading(chunk_body) if mode == "heading" else split_fixed(chunk_body, size, overlap)

    chunks: list[Chunk] = []
    for heading, content in sections:
        if not content:
            continue
        chunk_id = f"{source_path}#{heading}" if heading else source_path
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                source_path=source_path,
                doc_type=doc_type,
                title=title,
                heading=heading,
                content=content,
                date=date,
                tags=tags,
                links=links,
                frontmatter=frontmatter,
            )
        )
    return chunks


def chunk_config_key(mode: str = "heading", size: int = 800, overlap: int = 100) -> str:
    """청크 설정을 파일명/인덱스명에 쓸 수 있는 짧은 문자열로 바꾼다."""
    return "heading" if mode == "heading" else f"fixed_{size}_{overlap}"


def chunks_path_for(mode: str = "heading", size: int = 800, overlap: int = 100) -> Path:
    key = chunk_config_key(mode, size, overlap)
    return CHUNKS_PATH.parent / f"chunks_{key}.jsonl"


def parse_vault(
    vault_dir: Path = VAULT_DIR,
    mode: str = "heading",
    size: int = 800,
    overlap: int = 100,
) -> list[Chunk]:
    stem_index = build_stem_index(vault_dir)
    chunks: list[Chunk] = []
    for path in sorted(vault_dir.rglob("*.md")):
        chunks.extend(parse_file(path, vault_dir, stem_index, mode, size, overlap))
    return chunks


def to_dicts(chunks: list[Chunk]) -> list[dict[str, Any]]:
    """검색 함수들은 전부 dict(JSON 한 줄) 형태를 기대한다. CLI는 chunks.jsonl을
    다시 읽어서 항상 dict였지만, 메모리에서 바로 넘길 때(GUI 등)는 이 변환이 필요하다."""
    return [asdict(chunk) for chunk in chunks]


def write_chunks(chunks: list[Chunk], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for chunk in to_dicts(chunks):
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["heading", "fixed"], default="heading")
    parser.add_argument("--size", type=int, default=800, help="fixed 모드일 때 청크 글자 수")
    parser.add_argument("--overlap", type=int, default=100, help="fixed 모드일 때 겹치는 글자 수")
    args = parser.parse_args()

    chunks = parse_vault(mode=args.mode, size=args.size, overlap=args.overlap)
    out_path = chunks_path_for(args.mode, args.size, args.overlap)
    write_chunks(chunks, out_path)

    docs = {chunk.source_path for chunk in chunks}
    no_heading = sum(1 for chunk in chunks if chunk.heading is None)
    lengths = [len(chunk.content) for chunk in chunks]
    print(f"[parse_vault] mode={args.mode} 문서 {len(docs)}개 → 청크 {len(chunks)}개")
    if args.mode == "heading":
        print(f"  헤딩 없이 문서 전체를 한 청크로 처리한 것: {no_heading}개")
    print(f"  청크 길이(글자수): 평균 {sum(lengths) / len(lengths):.0f}, 최소 {min(lengths)}, 최대 {max(lengths)}")
    print(f"저장: {out_path.relative_to(out_path.parents[3])}")


if __name__ == "__main__":
    main()
