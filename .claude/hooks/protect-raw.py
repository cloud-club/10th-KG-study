#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write|MultiEdit|NotebookEdit): members/ 소재 층을 보호한다.

- `members/<id>/…` 편집은 <id> 가 현재 GitHub 로그인과 같을 때만 허용한다 (자기 폴더는 스터디 작업).
- 다른 멤버 폴더는 막는다 (CONTRIBUTING "다른 사람 폴더는 수정하지 않습니다" + CLAUDE.md "members/ 는 불변").
- `members/names.json`·`members/cohorts.json` 처럼 폴더 밖 공용 파일은 통과.

로그인 판별: 환경변수 KG_MEMBER_ID → .cache/gh-login 캐시 → `gh api user --jq .login` (5초, 결과 캐시).
셋 다 실패하면 막지 않고 stderr 에 경고만 남긴다 (fail-open: gh 가 없는 멤버의 작업을 막지 않기 위해).
차단은 exit 2 + stderr 메시지 (Claude Code 가 도구 호출을 취소하고 메시지를 모델에 보여준다).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
CACHE = REPO / ".cache" / "gh-login"
MEMBER_RE = re.compile(r"^members/([^/]+)/")


def current_login() -> str:
    env = os.environ.get("KG_MEMBER_ID", "").strip()
    if env:
        return env
    try:
        cached = CACHE.read_text(encoding="utf-8").strip()
        if cached:
            return cached
    except OSError:
        pass
    try:
        out = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True, timeout=5)
        login = out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        login = ""
    if login:
        try:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(login + "\n", encoding="utf-8")
        except OSError:
            pass
    return login


def target_path(data: dict) -> str:
    tool_input = data.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not raw:
        return ""
    p = Path(raw)
    if not p.is_absolute():
        p = REPO / p
    try:
        return p.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return ""  # 저장소 밖


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    rel = target_path(data)
    match = MEMBER_RE.match(rel)
    if not match:
        return 0
    owner = match.group(1)
    login = current_login()
    if not login:
        print(f"[protect-raw] GitHub 로그인을 알 수 없어 members/{owner}/ 편집을 막지 못했다. "
              "gh auth login 또는 KG_MEMBER_ID=<github-id> 를 설정하라.", file=sys.stderr)
        return 0
    if owner.lower() == login.lower():
        return 0
    print(f"[protect-raw] 차단: members/{owner}/ 는 다른 멤버의 소재 층이다 (현재 로그인 {login}). "
          "위키 페이지는 wiki/ 에 쓰고, 소재 수정은 그 멤버가 PR 로 한다 (CLAUDE.md '세 층').", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
