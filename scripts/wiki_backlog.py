#!/usr/bin/env python3
"""위키 ingest 밀린 소재 목록.

마지막 ingest(= `wiki/log.md`를 마지막으로 건드린 커밋) 이후 바뀐 `members/` 소재, 아직
[[스터디-노트-지도]]에 없는 소재, 열린 PR의 소재를 한 장의 마크다운으로 뽑는다. 주간 자동 ingest
워크플로가 이 출력을 프롬프트에 넣고, 사람이 "뭐가 밀렸나" 볼 때도 쓴다.

실행:
  python3 scripts/wiki_backlog.py                 # 마지막 ingest 커밋 기준
  python3 scripts/wiki_backlog.py --base a5e4f87  # 기준 커밋 지정
  python3 scripts/wiki_backlog.py --no-prs        # gh 없이 (CI 외부)
  python3 scripts/wiki_backlog.py --json          # 기계용
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTE_MAP = ROOT / "wiki" / "sources" / "스터디-노트-지도.md"
LOG = "wiki/log.md"

# CLAUDE.md "소재 범위": notes/**·note/**·labs/**의 md, readings.md, README.md (소개·목표).
SOURCE_RE = re.compile(r"^members/(?P<member>[^/]+)/(?:README\.md|readings\.md|(?:notes?|labs)/.+\.md)$")
EXCLUDE_RE = re.compile(r"/(?:dataset/vault|note-templates)/")  # 합성 데이터·템플릿은 소재가 아니다
MEMBER_HEADING_RE = re.compile(r"^###\s+(?P<member>[A-Za-z0-9_.-]+)\b")
BACKTICK_PATH_RE = re.compile(r"`((?:notes?|labs)/[^`]+\.md|README\.md|readings\.md)`")
BARE_NAME_RE = re.compile(r"`([^`/\s][^`\s]*\.md)`")  # 같은 줄 앞 경로의 폴더를 생략한 `WEEK5_result.md`, `data_sample/README.md`


def git(args: list[str], check: bool = True) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=check).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        if check:
            raise SystemExit(f"git {' '.join(args)} 실패: {exc}") from exc
        return ""


def is_source(path: str) -> bool:
    return bool(SOURCE_RE.match(path)) and not EXCLUDE_RE.search(path)


def member_of(path: str) -> str:
    m = SOURCE_RE.match(path)
    return m.group("member") if m else ""


def last_ingest_commit() -> str:
    """wiki/log.md 를 마지막으로 바꾼 커밋. 없으면 빈 문자열(= 전체가 밀림)."""
    return git(["log", "-1", "--format=%H", "--", LOG], check=False).strip()


def changed_sources(base: str, head: str = "HEAD") -> list[dict]:
    """base..head 사이 추가·수정된 소재. 삭제(D)는 뺀다 — 위키 쪽은 린트가 잡는다."""
    if not base:
        return [{"status": "A", "path": p, "member": member_of(p)} for p in tree_sources(head)]
    raw = git(["diff", "--name-status", "-M", f"{base}..{head}", "--", "members"])
    out = []
    for line in raw.splitlines():
        parts = line.split("\t")
        status, path = parts[0][0], parts[-1]
        if status == "D" or not is_source(path):
            continue
        out.append({"status": status, "path": path, "member": member_of(path)})
    return out


def tree_sources(ref: str = "HEAD") -> list[str]:
    raw = git(["ls-tree", "-r", "--name-only", ref, "--", "members"])
    return [p for p in raw.splitlines() if is_source(p)]


def mapped_paths(map_text: str) -> set[str]:
    """스터디-노트-지도의 `### <member>` 절 아래 백틱 경로를 `members/<id>/…` 로 복원.

    전체 경로(`notes/x.md`, `labs/a/b.md`)는 그대로, 폴더를 생략한 이름(`b.md`, `sub/README.md`)은
    `members/<id>/*<이름>` 꼴의 접미 패턴으로 돌려준다 — 같은 줄의 앞 경로와 폴더를 공유한다는 뜻."""
    mapped: set[str] = set()
    member = ""
    for line in map_text.splitlines():
        heading = MEMBER_HEADING_RE.match(line)
        if heading:
            member = heading.group("member")
            continue
        if line.startswith("## "):
            member = ""
            continue
        if not member:
            continue
        for rel in BACKTICK_PATH_RE.findall(line):
            mapped.add(f"members/{member}/{rel}")
        for bare in BARE_NAME_RE.findall(line):
            if bare.startswith(("notes/", "note/", "labs/")) or bare in ("README.md", "readings.md"):
                continue
            mapped.add(f"members/{member}/*{bare}")
    return mapped


def is_mapped(path: str, mapped: set[str]) -> bool:
    if path in mapped:
        return True
    member = member_of(path)
    return any(m.startswith(f"members/{member}/*") and path.endswith("/" + m.split("*", 1)[1]) for m in mapped)


MEMBER_ROOT_DOC_RE = re.compile(r"^members/[^/]+/(?:README|readings)\.md$")  # 소개·읽을거리는 지도에 개별로 안 싣는다


def unmapped_sources(ref: str = "HEAD") -> list[str]:
    """트리에 있지만 노트 지도에 없는 소재 = 아직 증류 안 된 것."""
    try:
        mapped = mapped_paths(NOTE_MAP.read_text(encoding="utf-8"))
    except OSError:
        return []
    return sorted(p for p in tree_sources(ref) if not is_mapped(p, mapped) and not MEMBER_ROOT_DOC_RE.match(p))


def open_prs() -> list[dict]:
    """열린 PR 과 그 안의 소재. gh 가 없거나 실패하면 빈 목록."""
    try:
        raw = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--limit", "50", "--json", "number,title,headRefName,files,updatedAt"],
            cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    prs = []
    for pr in json.loads(raw or "[]"):
        files = [f["path"] for f in pr.get("files") or [] if is_source(f["path"])]
        if files:
            prs.append({"number": pr["number"], "title": pr["title"], "branch": pr["headRefName"],
                        "updated": (pr.get("updatedAt") or "")[:10], "files": files})
    return prs


def word_count(path: str, ref: str = "HEAD") -> int:
    text = git(["show", f"{ref}:{path}"], check=False)
    return len(text.split())


def build_report(base: str, head: str = "HEAD", with_prs: bool = True) -> dict:
    changed = changed_sources(base, head)
    for c in changed:
        c["words"] = word_count(c["path"], head)
    return {
        "base": base,
        "base_date": git(["log", "-1", "--format=%cs", base], check=False).strip() if base else "",
        "head": git(["rev-parse", "--short", head]).strip(),
        "changed": changed,
        "unmapped": unmapped_sources(head),
        "prs": open_prs() if with_prs else [],
    }


def render(report: dict) -> str:
    lines = ["# 위키 ingest 밀린 소재", ""]
    base = report["base"][:7] if report["base"] else "(없음 — 전체)"
    lines.append(f"기준: 마지막 ingest 커밋 `{base}` ({report['base_date'] or '-'}) → `{report['head']}`")
    lines.append("")
    changed = report["changed"]
    lines.append(f"## 바뀐 소재 ({len(changed)}건, {sum(c['words'] for c in changed):,} 단어)")
    lines.append("")
    if not changed:
        lines.append("- 없음")
    by_member: dict[str, list[dict]] = {}
    for c in changed:
        by_member.setdefault(c["member"], []).append(c)
    for member in sorted(by_member, key=str.lower):
        items = by_member[member]
        lines.append(f"### {member} ({len(items)}건)")
        for c in items:
            lines.append(f"- `{c['status']}` {c['path']} ({c['words']:,} 단어)")
        lines.append("")
    lines.append(f"## 노트 지도에 없는 소재 ({len(report['unmapped'])}건)")
    lines.append("")
    lines.extend([f"- {p}" for p in report["unmapped"]] or ["- 없음"])
    lines.append("")
    lines.append(f"## 열린 PR 의 소재 ({len(report['prs'])}건)")
    lines.append("")
    for pr in report["prs"]:
        lines.append(f"### PR #{pr['number']} · {pr['title']} (`{pr['branch']}`, {pr['updated']})")
        lines.extend(f"- {p}" for p in pr["files"])
        lines.append("")
    if not report["prs"]:
        lines.append("- 없음")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--base", help="기준 커밋 (기본: wiki/log.md 를 마지막으로 바꾼 커밋)")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--no-prs", action="store_true", help="열린 PR 조회 생략")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    base = args.base or last_ingest_commit()
    report = build_report(base, args.head, with_prs=not args.no_prs)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        sys.stdout.write(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
