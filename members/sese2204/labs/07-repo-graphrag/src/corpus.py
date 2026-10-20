"""소재 수집과 청킹.

소재 범위는 CLAUDE.md 의 '소재 범위'를 따른다: members/<id>/ 의 notes/**·labs/**/*.md·readings.md·README.md.
실습 데이터(dataset/, note-templates/)와 가상환경은 소재가 아니라서 뺀다. 기준은 main 의 작업 트리다
(미머지 PR 은 넣지 않는다).
"""
import datetime as dt
import json
import re
import subprocess

import yaml

from common import REPO

EXCLUDE = re.compile(r"/(dataset|note-templates|\.venv|site-packages|node_modules)/")

# 경로에 주차 표시가 없을 때 쓰는 날짜 구간 (10기 허브 타임라인의 주차별 노트 몰림 기준)
WEEK_BINS = [
    ("2026-09-06", 1),
    ("2026-09-13", 2),
    ("2026-09-20", 3),
    ("2026-09-29", 4),
    ("2026-10-04", 5),
    ("2099-12-31", 6),
]
CHUNK_MAX = 1200


def kind_of(rel):
    parts = rel.split("/")
    if parts[-1] == "README.md" and len(parts) == 3:
        return "readme"
    if parts[-1] == "readings.md":
        return "readings"
    return "lab" if parts[2] == "labs" else "note"


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    try:
        _, fm, body = text.split("---", 2)
        return (yaml.safe_load(fm) or {}), body
    except (ValueError, yaml.YAMLError):
        return {}, text


def first_commit_date(rel):
    out = subprocess.run(
        ["git", "log", "--follow", "--diff-filter=A", "--format=%ad", "--date=short", "--", rel],
        cwd=REPO, capture_output=True, text=True,
    ).stdout.split()
    return out[-1] if out else None


def week_of(rel, date, title=""):
    # 몰아서 올린 노트가 있어 날짜보다 제목·경로의 주차 표시를 먼저 믿는다 (sunghyun 1~4주차 노트는 09-30 커밋)
    m = re.search(r"(\d)\s*주차|\bW(\d)\b|week\s*(\d)", title, re.I)
    if m:
        return int(next(g for g in m.groups() if g)), "title"
    m = re.search(r"week[_-]?(\d)", rel, re.I)
    if m:
        return int(m.group(1)), "path"
    if not date:
        return None, None
    for upper, w in WEEK_BINS:
        if date <= upper:
            return w, "date-bin"
    return None, None


def title_of(fm, body, rel):
    if fm.get("title"):
        return str(fm["title"])
    m = re.search(r"^#\s+(.+)$", body, re.M)
    return m.group(1).strip() if m else rel.rsplit("/", 1)[-1]


def chunk(body):
    """## 제목 단위로 나누고, 길면 문단 경계에서 CHUNK_MAX 이하로 자른다. 각 청크 앞에 소제목을 붙인다."""
    sections = re.split(r"(?m)^(?=#{1,3}\s)", body)
    chunks = []
    for sec in sections:
        sec = sec.strip()
        if len(sec) < 40:
            continue
        heading = sec.splitlines()[0].lstrip("# ").strip() if sec.startswith("#") else ""
        buf = ""
        for para in re.split(r"\n\s*\n", sec):
            if buf and len(buf) + len(para) > CHUNK_MAX:
                chunks.append((heading, buf.strip()))
                buf = (f"## {heading}\n" if heading else "")
            buf += para + "\n\n"
        if buf.strip() and buf.strip() != f"## {heading}":
            chunks.append((heading, buf.strip()))
    return [(h, t) for h, t in chunks if len(t) >= 40]


def collect():
    cohorts = json.loads((REPO / "members/cohorts.json").read_text())
    cohort_of = {}
    for c in cohorts if isinstance(cohorts, list) else cohorts.get("cohorts", []):
        for m in c.get("members", []):
            cohort_of[m] = c.get("id") or c.get("label")
    docs = []
    for p in sorted((REPO / "members").glob("*/**/*.md")):
        rel = p.relative_to(REPO).as_posix()
        if EXCLUDE.search(rel):
            continue
        text = p.read_text(errors="ignore")
        fm, body = parse_frontmatter(text)
        date = str(fm["date"]) if fm.get("date") else first_commit_date(rel)
        week, week_src = week_of(rel, date, title_of(fm, body, rel))
        tags = fm.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.strip("[]").split(",")]
        member = rel.split("/")[1]
        docs.append(
            {
                "path": rel,
                "member": member,
                "cohort": cohort_of.get(member),
                "kind": kind_of(rel),
                "title": title_of(fm, body, rel),
                "date": date,
                "week": week,
                "week_source": week_src,
                "tags": sorted({str(t).strip().lower() for t in tags if str(t).strip()}),
                "chunks": [
                    {"id": f"{rel}#{i}", "seq": i, "heading": h, "text": t}
                    for i, (h, t) in enumerate(chunk(body))
                ],
            }
        )
    return docs


if __name__ == "__main__":
    docs = collect()
    n = sum(len(d["chunks"]) for d in docs)
    chars = sum(len(c["text"]) for d in docs for c in d["chunks"])
    print(f"docs {len(docs)}, chunks {n}, chars {chars:,}")
    from collections import Counter

    print(Counter(d["kind"] for d in docs), Counter(d["week"] for d in docs), Counter(d["week_source"] for d in docs))
    print(Counter(d["member"] for d in docs).most_common())
