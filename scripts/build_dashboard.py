#!/usr/bin/env python3
"""members/ 폴더와 git 히스토리를 읽어 dashboard/data.json 을 만든다.

사용법:
    python3 scripts/build_dashboard.py                          # LLM 없이 (규칙 기반 폴백)
    OPENAI_API_KEY=sk-... python3 scripts/build_dashboard.py    # GPT 요약/태그/소식 포함
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard_llm import enrich_with_llm  # noqa: E402
from mock_feed import mock_feed  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MEMBERS_DIR = ROOT / "members"
OUT_PATH = ROOT / "dashboard" / "data.json"
CACHE_PATH = ROOT / ".cache" / "llm-cache.json"

HEATMAP_DAYS = 84
ACTIVITY_LIMIT = 20
FEED_LIMIT = 12
STREAK_MILESTONE = 3
KIND_ORDER = {"level": 0, "streak": 1, "lab": 2, "note": 3}
XP_PER_NOTE = 40
XP_PER_LAB = 80
XP_PER_COMMIT = 5
XP_PER_LEVEL = 100
SKIP_DIRS = {"<github-id>", "_template"}
PLACEHOLDERS = {
    "NN. 주제",
    "NN. 실습 제목",
    "이 주제를 한 문장으로 정리합니다.",
    "이 실습으로 확인하려는 것을 적습니다.",
}

FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.S)
DATE_RE = re.compile(r"작성일\s*[:：]\s*(\d{4}-\d{2}-\d{2})")
NUMBER_PREFIX_RE = re.compile(r"^\d+[-_.\s]*")


# --------------------------------------------------------------------------- git

def git(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return result.stdout.strip()


def git_commits(rel_path: str) -> list[dict]:
    """rel_path 를 건드린 커밋 목록 (최신순)."""
    out = git(["log", "--format=%H%x1f%ad%x1f%s", "--date=short", "--", rel_path])
    commits = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            commits.append({"sha": parts[0], "date": parts[1], "message": parts[2]})
    return commits


def first_commit_date(rel_path: str) -> str:
    out = git(["log", "--diff-filter=A", "--format=%ad", "--date=short", "--", rel_path])
    lines = out.splitlines()
    return lines[-1] if lines else ""


def detect_repo() -> dict:
    slug = os.environ.get("GITHUB_REPOSITORY", "")
    if not slug:
        remote = git(["remote", "get-url", "origin"])
        match = re.search(r"github\.com[:/]([^/]+)/([^/\s]+?)(?:\.git)?$", remote)
        slug = f"{match.group(1)}/{match.group(2)}" if match else "cloud-club/10th-KG-study"
    owner, name = slug.split("/", 1)
    branch = os.environ.get("GITHUB_REF_NAME") or git(["rev-parse", "--abbrev-ref", "HEAD"]) or "main"
    return {"owner": owner, "name": name, "branch": branch, "url": f"https://github.com/{slug}"}


def file_url(repo: dict, path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return f"{repo['url']}/blob/{repo['branch']}/{rel}"


# ------------------------------------------------------------------- markdown

def parse_scalar(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return [s.strip().strip("'\"") for s in raw[1:-1].split(",") if s.strip()]
    return raw.strip("'\"")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """아주 작은 YAML 부분집합: `key: value`, `key: [a, b]`, `key:` + `- item` 목록."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict = {}
    current_list_key = None
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list_key:
            meta[current_list_key].append(stripped[2:].strip().strip("'\""))
            continue
        if ":" not in stripped:
            continue
        key, _, raw = stripped.partition(":")
        key = key.strip()
        if raw.strip() == "":
            meta[key] = []
            current_list_key = key
        else:
            meta[key] = parse_scalar(raw)
            current_list_key = None
    return meta, text[match.end():]


def first_heading(body: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    return match.group(1).strip() if match else ""


def section_text(body: str, heading: str, limit: int = 200) -> str:
    """`## heading` 아래 본문을 한 문단으로 합쳐 돌려준다 (코드블록, 인용, 표 제외)."""
    pattern = rf"^##\s+{re.escape(heading)}.*?$\n(.*?)(?=^#|\Z)"
    match = re.search(pattern, body, re.M | re.S)
    if not match:
        return ""
    text = re.sub(r"```.*?```", "", match.group(1), flags=re.S)
    lines = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith((">", "|", "<!--"))
    ]
    para = re.sub(r"\s+", " ", " ".join(lines)).strip()
    if para in PLACEHOLDERS:
        return ""
    return para[:limit]


def clean_title(raw: str) -> str:
    raw = (raw or "").strip()
    return "" if raw in PLACEHOLDERS else raw


def humanize(stem: str) -> str:
    return NUMBER_PREFIX_RE.sub("", stem).replace("-", " ").replace("_", " ").strip() or stem


def normalize_tags(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    seen: list[str] = []
    for tag in raw:
        t = str(tag).strip().lower().lstrip("#")
        if t and t not in seen:
            seen.append(t)
    return seen


def find_date(meta: dict, body: str, rel_path: str) -> str:
    if meta.get("date"):
        return str(meta["date"])
    match = DATE_RE.search(body)
    if match:
        return match.group(1)
    return first_commit_date(rel_path)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ----------------------------------------------------------------- scanning

def parse_note(path: Path, member_id: str, repo: dict) -> dict:
    meta, body = parse_frontmatter(read_text(path))
    rel = path.relative_to(ROOT).as_posix()
    title = clean_title(meta.get("title")) or clean_title(first_heading(body)) or humanize(path.stem)
    return {
        "kind": "note",
        "id": f"{member_id}/notes/{path.stem}",
        "file": path.name,
        "title": title,
        "date": find_date(meta, body, rel),
        "summary": clean_title(meta.get("summary")) or section_text(body, "한 줄 요약"),
        "tags": normalize_tags(meta.get("tags")),
        "status": str(meta.get("status") or ""),
        "url": file_url(repo, path),
        "_excerpt": body[:3000],
    }


def parse_lab(lab_dir: Path, member_id: str, repo: dict) -> dict:
    readme = lab_dir / "README.md"
    meta, body = parse_frontmatter(read_text(readme)) if readme.exists() else ({}, "")
    rel = lab_dir.relative_to(ROOT).as_posix()
    src_dir = lab_dir / "src"
    src_files = [p for p in src_dir.rglob("*") if p.is_file() and not p.name.startswith(".")] if src_dir.exists() else []
    title = clean_title(meta.get("title")) or clean_title(first_heading(body)) or humanize(lab_dir.name)
    return {
        "kind": "lab",
        "id": f"{member_id}/labs/{lab_dir.name}",
        "file": lab_dir.name,
        "title": title,
        "date": find_date(meta, body, rel),
        "summary": clean_title(meta.get("summary")) or section_text(body, "목표"),
        "tags": normalize_tags(meta.get("tags")),
        "status": str(meta.get("status") or ""),
        "src_files": len(src_files),
        "url": f"{repo['url']}/tree/{repo['branch']}/{rel}",
        "_excerpt": body[:3000],
    }


def build_heatmap(dates: list[str], today: dt.date) -> list[dict]:
    counts = Counter(dates)
    start = today - dt.timedelta(days=HEATMAP_DAYS - 1)
    cells = []
    for i in range(HEATMAP_DAYS):
        day = (start + dt.timedelta(days=i)).isoformat()
        cells.append({"date": day, "count": counts.get(day, 0)})
    return cells


def current_streak(dates: list[str], today: dt.date) -> int:
    days = set()
    for d in dates:
        try:
            days.add(dt.date.fromisoformat(d))
        except ValueError:
            continue
    cursor = today if today in days else today - dt.timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= dt.timedelta(days=1)
    return streak


def progress(n_notes: int, n_labs: int, n_commits: int) -> dict:
    xp = n_notes * XP_PER_NOTE + n_labs * XP_PER_LAB + n_commits * XP_PER_COMMIT
    return {
        "xp": xp,
        "level": 1 + xp // XP_PER_LEVEL,
        "xp_in_level": xp % XP_PER_LEVEL,
        "xp_per_level": XP_PER_LEVEL,
    }


def scan_member(member_dir: Path, repo: dict, today: dt.date) -> dict:
    member_id = member_dir.name
    readme = member_dir / "README.md"
    meta, body = parse_frontmatter(read_text(readme)) if readme.exists() else ({}, "")
    notes_dir, labs_dir = member_dir / "notes", member_dir / "labs"

    notes = sorted(
        (parse_note(p, member_id, repo) for p in notes_dir.glob("*.md")) if notes_dir.exists() else [],
        key=lambda n: n["file"],
    )
    labs = sorted(
        (
            parse_lab(d, member_id, repo)
            for d in labs_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ) if labs_dir.exists() else [],
        key=lambda l: l["file"],
    )
    commits = git_commits(f"members/{member_id}")
    dates = [c["date"] for c in commits]
    tags = normalize_tags([t for item in notes + labs for t in item["tags"]])

    return {
        "id": member_id,
        "name": str(meta.get("name") or clean_title(first_heading(body)) or member_id),
        "avatar": f"https://github.com/{member_id}.png?size=160",
        "url": f"https://github.com/{member_id}",
        "folder_url": f"{repo['url']}/tree/{repo['branch']}/members/{member_id}",
        "intro": section_text(body, "소개", 300),
        "title": "",
        "summary": "",
        "highlights": [],
        "llm": False,
        "counts": {"notes": len(notes), "labs": len(labs), "commits": len(commits)},
        "progress": progress(len(notes), len(labs), len(commits)),
        "streak": current_streak(dates, today),
        "last_active": dates[0] if dates else "",
        "heatmap": build_heatmap(dates, today),
        "tags": tags,
        "notes": notes,
        "labs": labs,
        "_commits": commits,
    }


def scan_members(repo: dict, today: dt.date) -> list[dict]:
    if not MEMBERS_DIR.exists():
        return []
    members = []
    for d in sorted(MEMBERS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in SKIP_DIRS:
            continue
        members.append(scan_member(d, repo, today))
    return members


# --------------------------------------------------------------- assembling

def build_graph(members: list[dict]) -> dict:
    nodes, links, seen = [], [], set()
    for m in members:
        mid = f"m:{m['id']}"
        nodes.append({"id": mid, "type": "member", "label": m["name"], "member": m["id"], "avatar": m["avatar"]})
        for item in m["notes"] + m["labs"]:
            nid = f"{item['kind'][0]}:{item['id']}"
            nodes.append({"id": nid, "type": item["kind"], "label": item["title"], "member": m["id"], "url": item["url"]})
            links.append({"source": mid, "target": nid})
            for tag in item["tags"]:
                tid = f"t:{tag}"
                if tid not in seen:
                    seen.add(tid)
                    nodes.append({"id": tid, "type": "topic", "label": tag})
                links.append({"source": nid, "target": tid})
    return {"nodes": nodes, "links": links}


def build_activity(members: list[dict], repo: dict) -> list[dict]:
    seen, activity = set(), []
    for m in members:
        for c in m["_commits"]:
            if c["sha"] in seen:
                continue
            seen.add(c["sha"])
            activity.append({**c, "member": m["id"], "url": f"{repo['url']}/commit/{c['sha']}"})
    activity.sort(key=lambda c: c["date"], reverse=True)
    return activity[:ACTIVITY_LIMIT]


def build_feed_events(members: list[dict], today: dt.date) -> list[dict]:
    """중계 피드의 원재료: 노트/실습 추가, 연속 활동, 레벨 업."""
    events = []
    for m in members:
        for item in m["notes"] + m["labs"]:
            events.append({
                "id": f"{item['kind']}:{item['id']}",
                "date": item["date"] or today.isoformat(),
                "member": m["id"], "kind": item["kind"], "title": item["title"],
                "url": item["url"], "summary": item["summary"], "tags": item["tags"],
            })
        if m["streak"] >= STREAK_MILESTONE:
            events.append({
                "id": f"streak:{m['id']}:{m['streak']}", "date": m["last_active"],
                "member": m["id"], "kind": "streak", "title": f"{m['streak']}일 연속 활동",
                "url": m["folder_url"], "summary": "", "tags": [],
            })
        level = m["progress"]["level"]
        if level >= 2:
            events.append({
                "id": f"level:{m['id']}:{level}", "date": m["last_active"],
                "member": m["id"], "kind": "level", "title": f"Lv.{level} 달성",
                "url": m["folder_url"], "summary": "", "tags": [],
            })
    events.sort(key=lambda e: (e["date"], -KIND_ORDER.get(e["kind"], 9)), reverse=True)
    return events[:FEED_LIMIT]


def resolve_feed(feed: list[dict], source: str, today: dt.date) -> tuple[list[dict], str]:
    """DASHBOARD_MOCK_FEED: auto(기본, 비어 있으면 목데이터) | 1(항상 목데이터) | 0(절대 안 씀)."""
    flag = os.environ.get("DASHBOARD_MOCK_FEED", "auto").strip().lower()
    force = flag in {"1", "true", "yes", "on"}
    never = flag in {"0", "false", "no", "off"}
    if force or (not never and not feed):
        return mock_feed(today), "mock"
    return feed, source


def strip_private(members: list[dict]) -> list[dict]:
    cleaned = []
    for m in members:
        m = {k: v for k, v in m.items() if not k.startswith("_")}
        m["notes"] = [{k: v for k, v in n.items() if not k.startswith("_")} for n in m["notes"]]
        m["labs"] = [{k: v for k, v in l.items() if not k.startswith("_")} for l in m["labs"]]
        cleaned.append(m)
    return cleaned


def main() -> int:
    today = dt.date.today()
    repo = detect_repo()
    members = scan_members(repo, today)
    totals = {
        "members": len(members),
        "notes": sum(m["counts"]["notes"] for m in members),
        "labs": sum(m["counts"]["labs"] for m in members),
        "commits": len({c["sha"] for m in members for c in m["_commits"]}),
    }
    started = git(["log", "--reverse", "--format=%ad", "--date=short"]).splitlines()
    study = {"started_at": started[0] if started else today.isoformat()}

    events = build_feed_events(members, today)
    llm = enrich_with_llm(members, totals, CACHE_PATH, events)
    feed, feed_source = resolve_feed(llm.pop("feed"), llm.pop("feed_source"), today)
    study.update(llm)

    data = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "repo": repo,
        "study": study,
        "totals": totals,
        "feed": feed,
        "feed_source": feed_source,
        "members": strip_private(members),
        "graph": build_graph(members),
        "activity": build_activity(members, repo),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[dashboard] {OUT_PATH.relative_to(ROOT)} 생성: 멤버 {totals['members']}, "
        f"노트 {totals['notes']}, 실습 {totals['labs']}, 커밋 {totals['commits']}, "
        f"LLM={study.get('digest_source')}, 피드={feed_source}({len(feed)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
