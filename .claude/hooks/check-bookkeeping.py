#!/usr/bin/env python3
"""Stop hook: wiki/index.md 와 wiki/log.md 를 최신으로 유지하도록 한 번 멈춰 세운다.

- log.md   — 위키 내용 페이지가 하나라도 바뀌면(생성·수정·이동) 날짜 항목이 필요하다.
- index.md — 카탈로그는 페이지 목록이므로 **새 페이지**가 생겼을 때만 항목이 필요하다.

면제: index/log/CLAUDE.md, wiki/_templates/, wiki/0-pending/(소재), _attachments/, 동기화 원본 폴더(SYNC_DIRS).
members/ 는 위키가 아니라 소재 층이라 애초에 대상이 아니다.
stop_hook_active 가드로 무한 루프를 막는다 — 정지당 최대 한 번만 요구한다.
"""
import json
import os
import subprocess
import sys

REPO = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
CONTENT_ROOTS = ("wiki/1-projects/", "wiki/2-areas/", "wiki/3-resources/", "wiki/4-archives/")
SYNC_DIRS: tuple[str, ...] = ()  # 스크립트가 관리하는 동기화 원본 폴더가 생기면 여기 추가
INDEX = "wiki/index.md"
LOG = "wiki/log.md"

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

if data.get("stop_hook_active"):
    sys.exit(0)

try:
    out = subprocess.run(
        ["git", "-C", REPO, "status", "--porcelain", "-uall", "--", "."],
        capture_output=True, text=True, timeout=10,
    ).stdout
except Exception:
    sys.exit(0)

changed = set()
new_pages = set()
for line in out.splitlines():
    status, path = line[:2], line[3:].strip().strip('"')
    if "->" in path:
        path = path.split("->", 1)[1].strip()
    if not path.endswith(".md"):
        continue
    changed.add(path)
    if "?" in status or "A" in status:
        new_pages.add(path)


def is_content(p: str) -> bool:
    if not p.startswith(CONTENT_ROOTS):
        return False
    if "/_templates/" in p or "/_attachments/" in p:
        return False
    if p.startswith(SYNC_DIRS):
        return False
    return True


content_changed = any(is_content(p) for p in changed)
new_content = any(is_content(p) for p in new_pages)
index_touched = INDEX in changed
log_touched = LOG in changed

missing = []
if new_content and not index_touched:
    missing.append("wiki/index.md (새 페이지를 카탈로그에 추가)")
if content_changed and not log_touched:
    missing.append("wiki/log.md (날짜 항목 append)")

if missing:
    print(json.dumps({
        "decision": "block",
        "reason": (
            "위키 페이지가 바뀌었는데 장부가 덜 됐다. CLAUDE.md 에 따라 갱신할 것: "
            + "; ".join(missing)
            + ". 지금 하고 멈춰라. 의도적으로 index/log 갱신이 필요 없는 변경이면 한 번 더 멈추면 통과한다."
        ),
    }, ensure_ascii=False))
    sys.exit(0)

sys.exit(0)
