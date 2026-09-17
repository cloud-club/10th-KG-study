#!/usr/bin/env bash
# SessionStart hook: 매 세션 이 저장소의 위키 규칙을 컨텍스트에 주입한다.
cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "## 10th-KG-study 스터디 LLM 위키 — 운영 규칙 (강제)\n\n이 저장소의 wiki/ 는 에이전트가 유지하는 스터디 지식베이스(옵시디언 볼트, 페이지 종류별 폴더)다. 루트 CLAUDE.md 를 그대로 따른다. 핵심 규칙:\n1. members/<id>/ 는 소재이며 불변이다. 에이전트는 읽기만 한다. 다른 멤버 폴더 편집은 protect-raw 훅이 막는다. 자기 노트는 스터디 작업으로 쓰되 위키 작업 중에는 건드리지 않는다.\n2. wiki/concepts/ entities/ comparisons/ sources/ 의 페이지는 에이전트가 소유한다(폴더 = type). 새 페이지는 wiki/_templates/ 에서 시작한다. 비슷한 페이지가 있으면 새로 만들지 말고 갱신한다 — wiki/index.md 와 스터디-노트-지도 를 먼저 본다.\n3. 모든 페이지: YAML frontmatter(title·type·tags·status·created·updated, 선택 members·weeks) + 한 줄 정의 + 본문 + ## 관련 + ## 출처. 파일명은 한국어, 띄어쓰기는 -, basename 유일.\n4. [[위키링크]](basename만)를 아낌없이 건다. members/ 소재는 ## 출처에 저장소 상대경로 링크로. 사실을 지어내지 않는다 — 모르면 '> TODO: unverified', 노트끼리 다르면 '> ⚠️ Contradiction:'. 수치·주장에는 어느 멤버가 어떤 조건에서 확인했는지 붙인다.\n5. ingest 마다: 영향받는 페이지 갱신 + 양방향 링크 + 스터디-노트-지도 갱신 + wiki/index.md 갱신 + wiki/log.md append.\n6. 질문에 답할 때 wiki/index.md 를 먼저 읽는다. 좋은 답은 페이지로 되돌려 넣는다.\n7. 개인 대화 원문(카카오톡·노션 내용)·토큰은 위키에 적지 않는다. 멤버는 github id로 부른다. 커밋·푸시는 요청이 있을 때만, main 직접 푸시 금지(PR).\n\nIngest / Query / Lint / Archive 절차와 전체 스키마는 CLAUDE.md 에 있다. 위키를 고치기 전에 읽는다."
  }
}
JSON
