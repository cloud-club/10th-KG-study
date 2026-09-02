#!/usr/bin/env python3
"""members/ 폴더와 git 히스토리를 읽어 dashboard/data.json 을 만든다.

사용법:
    python3 scripts/build_dashboard.py                          # LLM 없이 (규칙 기반 폴백)
    OPENAI_API_KEY=sk-... python3 scripts/build_dashboard.py    # GPT 요약/태그/중계 포함
    GITHUB_TOKEN=...                                            # (선택) 커밋 작성자를 GitHub 로그인으로 식별
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard_llm import enrich_with_llm, load_cache, save_cache  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MEMBERS_DIR = ROOT / "members"
OUT_PATH = ROOT / "dashboard" / "data.json"
CACHE_PATH = ROOT / ".cache" / "llm-cache.json"

HEATMAP_DAYS = 84
ACTIVITY_LIMIT = 20
COMMIT_FEED_LIMIT = 10          # 중계할 최근 커밋 수
FEED_LIMIT = 12                 # 커밋 + 마일스톤 합쳐 최대
DIFF_EXCERPT_CHARS = 2500       # GPT 에 넘길 diff 길이 (커밋당)
MAX_FILES_IN_EVENT = 12
STREAK_MILESTONE = 3
XP_PER_NOTE = 40
XP_PER_LAB = 80
XP_PER_COMMIT = 5
XP_PER_LEVEL = 100
KIND_ORDER = {"level": 0, "streak": 1, "lab": 2, "note": 3, "shared": 4, "commit": 5}
SKIP_DIRS = {"<github-id>", "_template"}
INFRA_PREFIXES = ("dashboard/", "scripts/", ".github/", "templates/", ".cache/")
INFRA_FILES = {"README.md", "CONTRIBUTING.md", ".gitignore"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".lock", ".ipynb", ".parquet", ".db"}
PLACEHOLDERS = {
    "NN. 주제",
    "NN. 실습 제목",
    "이 주제를 한 문장으로 정리합니다.",
    "이 실습으로 확인하려는 것을 적습니다.",
}

FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.S)
DATE_RE = re.compile(r"작성일\s*[:：]\s*(\d{4}-\d{2}-\d{2})")
NUMBER_PREFIX_RE = re.compile(r"^\d+[-_.\s]*")
MEMBER_PATH_RE = re.compile(r"^members/([^/]+)/")
NOREPLY_RE = re.compile(r"^(?:\d+\+)?([^@]+)@users\.noreply\.github\.com$", re.I)


# --------------------------------------------------------------------------- git

def git(args: list[str]) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return result.stdout.strip()


def parse_git_log(raw: str) -> list[dict]:
    """`--format=%x1e%H%x1f%ad%x1f%an%x1f%ae%x1f%s --name-only` 출력을 커밋 목록으로."""
    commits = []
    for block in raw.split("\x1e"):
        block = block.strip()
        if not block:
            continue
        head, _, rest = block.partition("\n")
        parts = head.split("\x1f")
        if len(parts) != 5:
            continue
        files = [ln.strip() for ln in rest.splitlines() if ln.strip()]
        commits.append({"sha": parts[0], "date": parts[1], "author": parts[2], "email": parts[3],
                        "message": parts[4], "files": files})
    return commits


def git_all_commits() -> list[dict]:
    return parse_git_log(git(["log", "--format=%x1e%H%x1f%ad%x1f%an%x1f%ae%x1f%s", "--date=short", "--name-only"]))


def first_commit_date(rel_path: str) -> str:
    out = git(["log", "--diff-filter=A", "--format=%ad", "--date=short", "--", rel_path])
    lines = out.splitlines()
    return lines[-1] if lines else ""


def commit_numstat(sha: str) -> dict:
    files = additions = deletions = 0
    for line in git(["show", "--format=", "--numstat", sha]).splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        files += 1
        if parts[0].isdigit():
            additions += int(parts[0])
        if parts[1].isdigit():
            deletions += int(parts[1])
    return {"files": files, "additions": additions, "deletions": deletions}


def commit_diff_excerpt(sha: str, files: list[str]) -> str:
    text_files = [f for f in files if Path(f).suffix.lower() not in BINARY_SUFFIXES][:MAX_FILES_IN_EVENT]
    if not text_files:
        return ""
    out = git(["show", "--format=", "--unified=1", "--no-color", sha, "--", *text_files])
    return out[:DIFF_EXCERPT_CHARS]


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


# ------------------------------------------------------------ commit 분류/귀속

def study_files(files: list[str]) -> list[str]:
    return [f for f in files
            if not f.startswith(INFRA_PREFIXES) and f not in INFRA_FILES and Path(f).name != ".gitkeep"]


def classify_commit(files: list[str]) -> str:
    kinds = set()
    for f in files:
        if re.match(r"^members/[^/]+/labs/", f):
            kinds.add("lab")
        elif re.match(r"^members/[^/]+/notes/", f):
            kinds.add("note")
        elif f.startswith("shared/"):
            kinds.add("shared")
    for kind in ("lab", "note", "shared"):
        if kind in kinds:
            return kind
    return "commit"


def github_login(repo: dict, sha: str, cache: dict) -> str:
    """커밋의 GitHub 작성자 로그인. 실패/없음은 "" 로 캐시해 재조회를 막는다."""
    key = f"author:{sha}"
    if key in cache:
        return cache[key]
    url = f"https://api.github.com/repos/{repo['owner']}/{repo['name']}/commits/{sha}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "kg-study-dashboard"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    login = ""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        login = str((data.get("author") or {}).get("login") or "")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        print(f"[dashboard] GitHub 작성자 조회 실패 {sha[:7]}: {exc}", file=sys.stderr)
        return ""  # 일시 오류는 캐시하지 않는다
    cache[key] = login
    return login


def attribute_commit(commit: dict, member_ids: set[str], repo: dict, cache: dict) -> str:
    """커밋을 멤버 id 에 귀속: 멤버 폴더 경로 → noreply 이메일 → GitHub API → 이메일/이름 매칭 → 작성자 이름."""
    for f in commit["files"]:
        match = MEMBER_PATH_RE.match(f)
        if match and match.group(1) in member_ids:
            return match.group(1)
    noreply = NOREPLY_RE.match(commit["email"] or "")
    if noreply:
        return noreply.group(1)
    login = github_login(repo, commit["sha"], cache)
    if login:
        return login
    local = (commit["email"] or "").split("@")[0].lower()
    for mid in member_ids:
        if mid.lower() in (local, (commit["author"] or "").lower()):
            return mid
    return commit["author"] or "unknown"


def collect_study_commits(repo: dict, member_ids: set[str], cache: dict) -> list[dict]:
    """인프라만 건드린 커밋은 빼고, 나머지를 분류·귀속해서 최신순으로."""
    commits = []
    for c in git_all_commits():
        files = study_files(c["files"])
        if not files:
            continue
        commits.append({**c, "files": files, "kind": classify_commit(files),
                        "member": attribute_commit({**c, "files": files}, member_ids, repo, cache)})
    return commits


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
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith((">", "|", "<!--"))]
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
        "_path": rel,
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
        "_path": rel + "/",
        "_excerpt": body[:3000],
    }


def build_heatmap(dates: list[str], today: dt.date) -> list[dict]:
    counts = Counter(dates)
    start = today - dt.timedelta(days=HEATMAP_DAYS - 1)
    return [{"date": (start + dt.timedelta(days=i)).isoformat(),
             "count": counts.get((start + dt.timedelta(days=i)).isoformat(), 0)} for i in range(HEATMAP_DAYS)]


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
    return {"xp": xp, "level": 1 + xp // XP_PER_LEVEL, "xp_in_level": xp % XP_PER_LEVEL, "xp_per_level": XP_PER_LEVEL}


def member_dirs() -> list[Path]:
    if not MEMBERS_DIR.exists():
        return []
    return [d for d in sorted(MEMBERS_DIR.iterdir())
            if d.is_dir() and not d.name.startswith(".") and d.name not in SKIP_DIRS]


def scan_member(member_dir: Path, repo: dict, today: dt.date, commits: list[dict]) -> dict:
    member_id = member_dir.name
    readme = member_dir / "README.md"
    meta, body = parse_frontmatter(read_text(readme)) if readme.exists() else ({}, "")
    notes_dir, labs_dir = member_dir / "notes", member_dir / "labs"

    notes = sorted((parse_note(p, member_id, repo) for p in notes_dir.glob("*.md")) if notes_dir.exists() else [],
                   key=lambda n: n["file"])
    labs = sorted((parse_lab(d, member_id, repo) for d in labs_dir.iterdir() if d.is_dir() and not d.name.startswith("."))
                  if labs_dir.exists() else [], key=lambda l: l["file"])
    dates = [c["date"] for c in commits]
    tags = normalize_tags([t for item in notes + labs for t in item["tags"]])

    return {
        "id": member_id,
        "name": str(meta.get("name") or clean_title(first_heading(body)) or member_id),
        "avatar": f"https://github.com/{member_id}.png?size=160",
        "url": f"https://github.com/{member_id}",
        "folder_url": f"{repo['url']}/tree/{repo['branch']}/members/{member_id}",
        "intro": section_text(body, "소개", 300),
        "title": "", "summary": "", "highlights": [], "llm": False,
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


def build_activity(commits: list[dict], repo: dict) -> list[dict]:
    return [{"sha": c["sha"], "date": c["date"], "message": c["message"], "member": c["member"],
             "kind": c["kind"], "url": f"{repo['url']}/commit/{c['sha']}"} for c in commits[:ACTIVITY_LIMIT]]


def linked_items(files: list[str], member: dict | None) -> list[dict]:
    if not member:
        return []
    return [item for item in member["notes"] + member["labs"]
            if any(f == item["_path"].rstrip("/") or f.startswith(item["_path"]) for f in files)]


def commit_events(commits: list[dict], members_by_id: dict, repo: dict) -> list[dict]:
    events = []
    for c in commits[:COMMIT_FEED_LIMIT]:
        items = linked_items(c["files"], members_by_id.get(c["member"]))
        events.append({
            "id": f"commit:{c['sha'][:12]}",
            "date": c["date"], "member": c["member"], "kind": c["kind"],
            "title": c["message"], "url": f"{repo['url']}/commit/{c['sha']}",
            "summary": "",
            "tags": normalize_tags([t for i in items for t in i["tags"]]),
            "items": [{"kind": i["kind"], "title": i["title"], "url": i["url"]} for i in items],
            "stats": commit_numstat(c["sha"]),
            "files": c["files"][:MAX_FILES_IN_EVENT],
            "_diff": commit_diff_excerpt(c["sha"], c["files"]),
        })
    return events


def milestone_events(members: list[dict]) -> list[dict]:
    events = []
    for m in members:
        base = {"member": m["id"], "date": m["last_active"], "url": m["folder_url"],
                "summary": "", "tags": [], "items": [], "stats": None, "files": [], "_diff": ""}
        if m["streak"] >= STREAK_MILESTONE:
            events.append({**base, "id": f"streak:{m['id']}:{m['streak']}", "kind": "streak",
                           "title": f"{m['streak']}일 연속 활동"})
        level = m["progress"]["level"]
        if level >= 2:
            events.append({**base, "id": f"level:{m['id']}:{level}", "kind": "level", "title": f"Lv.{level} 달성"})
    return events


def build_feed_events(commits: list[dict], members: list[dict], repo: dict) -> list[dict]:
    members_by_id = {m["id"]: m for m in members}
    events = commit_events(commits, members_by_id, repo) + milestone_events(members)
    events.sort(key=lambda e: (e["date"], -KIND_ORDER.get(e["kind"], 9)), reverse=True)
    return events[:FEED_LIMIT]


def strip_private(records: list[dict]) -> list[dict]:
    cleaned = []
    for r in records:
        r = {k: v for k, v in r.items() if not k.startswith("_")}
        for key in ("notes", "labs"):
            if key in r:
                r[key] = strip_private(r[key])
        cleaned.append(r)
    return cleaned


def write_step_summary(data: dict) -> None:
    """GitHub Actions 실행 요약 탭에 빌드 결과를 남긴다."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    s, t = data["study"], data["totals"]
    model = f" ({s['model']})" if s.get("model") else ""
    lines = [
        "## 현황판 빌드", "",
        f"- 멤버 {t['members']} · 노트 {t['notes']} · 실습 {t['labs']} · 커밋 {t['commits']}",
        f"- 요약/칭호: **{s['digest_source']}**{model}",
        f"- 중계 피드: **{data['feed_source']}** ({len(data['feed'])}건)",
        "", f"> {s['digest']}", "",
    ]
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    except OSError as exc:
        print(f"[dashboard] step summary 기록 실패: {exc}", file=sys.stderr)


def main() -> int:
    today = dt.date.today()
    repo = detect_repo()
    cache = load_cache(CACHE_PATH)

    dirs = member_dirs()
    member_ids = {d.name for d in dirs}
    commits = collect_study_commits(repo, member_ids, cache)
    by_member: dict[str, list[dict]] = defaultdict(list)
    for c in commits:
        by_member[c["member"]].append(c)
    members = [scan_member(d, repo, today, by_member.get(d.name, [])) for d in dirs]

    totals = {
        "members": len(members),
        "notes": sum(m["counts"]["notes"] for m in members),
        "labs": sum(m["counts"]["labs"] for m in members),
        "commits": len(commits),
    }
    started = git(["log", "--reverse", "--format=%ad", "--date=short"]).splitlines()
    study = {"started_at": started[0] if started else today.isoformat()}

    events = build_feed_events(commits, members, repo)
    llm = enrich_with_llm(members, totals, cache, events)
    save_cache(CACHE_PATH, cache)
    feed, feed_source = llm.pop("feed"), llm.pop("feed_source")
    study.update(llm)

    data = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "repo": repo,
        "study": study,
        "totals": totals,
        "feed": strip_private(feed),
        "feed_source": feed_source,
        "members": strip_private(members),
        "graph": build_graph(members),
        "activity": build_activity(commits, repo),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_step_summary(data)
    print(
        f"[dashboard] {OUT_PATH.relative_to(ROOT)} 생성: 멤버 {totals['members']}, "
        f"노트 {totals['notes']}, 실습 {totals['labs']}, 커밋 {totals['commits']}, "
        f"LLM={study.get('digest_source')}, 피드={feed_source}({len(feed)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
