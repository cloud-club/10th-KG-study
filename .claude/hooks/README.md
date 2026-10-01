# .claude/hooks — 강제 장치

이 훅들은 하네스가 실행한다(모델이 아니라). 이 저장소에서 열리는 모든 Claude Code 세션이 규칙을 기억에
의존하지 않고 위키 관리자로 동작하게 한다. 연결은 `../settings.json`. 규칙 본문은 루트 `CLAUDE.md`.

| 훅 | 이벤트 | 강제하는 것 |
|---|---|---|
| `session-rules.sh` | `SessionStart` | 핵심 규칙을 세션 시작 시 컨텍스트에 주입 |
| `protect-raw.py` | `PreToolUse` (Edit·Write·MultiEdit·NotebookEdit) | `members/<다른 멤버>/` 편집 차단. 본인 폴더(`gh api user` 로그인, `.cache/gh-login`에 캐시)는 허용. 로그인을 알 수 없으면 경고만 하고 통과(fail-open) |
| `check-bookkeeping.py` | `Stop` | 위키 페이지가 바뀌었는데 `wiki/log.md`가 안 바뀌었거나, 새 페이지가 생겼는데 `wiki/index.md`가 안 바뀌었으면 한 번 멈춤. `inbox/`·`_templates/`·`_attachments/`는 면제 |

`protect-raw.py`는 dev-docs 개인 위키에는 없던 훅이다. 그 볼트에는 불변 `raw/` 층이 없었지만, 이
저장소는 `members/`가 그 층이라 들여왔다. 본인 폴더 판별은 `KG_MEMBER_ID` 환경변수로도 고정할 수 있다.

훅을 고친 뒤에는 `/hooks`를 한 번 열거나 재시작해야 반영된다. 수동 테스트:

```bash
export CLAUDE_PROJECT_DIR="$(git rev-parse --show-toplevel)"
echo '{}' | python3 .claude/hooks/check-bookkeeping.py
echo '{"tool_name":"Edit","tool_input":{"file_path":"members/kdyann/notes/x.md"}}' | python3 .claude/hooks/protect-raw.py; echo "exit=$?"
```
