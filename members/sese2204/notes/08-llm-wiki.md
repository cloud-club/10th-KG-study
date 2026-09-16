---
title: LLM 위키 — 검색 대신 컴파일하는 지식 베이스
date: 2026-09-16
tags: [llm-wiki, knowledge-base, rag, obsidian, agent-memory, karpathy]
status: done
---

# 08. LLM 위키 — 검색 대신 컴파일하는 지식 베이스

> 참고 자료:
> - [Karpathy, LLM Wiki (gist, 2026-04-04)](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — 원문. 이 레포 `wiki/3-resources/LLM-위키-패턴.md`에 전문 보존
> - [HN 원문 스레드 (296pt / 95 comments)](https://news.ycombinator.com/item?id=47640875) — "이건 그냥 RAG다" 논쟁
> - [LangChain, Wiki Memory: File-Based Memory for AI Agents (2026-06-30)](https://www.langchain.com/blog/wiki-memory) — 에이전트 메모리 관점의 정식화
> - [R&D World, Is Karpathy's viral LLM wiki helpful? Mostly yes (2026-06-11)](https://www.rdworldonline.com/is-karpathys-viral-llm-wiki-helpful-mostly-yes-one-month-in/) — 한 달 운영 후기
> - [Platformer, An LLM wiki changed how I work](https://www.platformer.news/karpathy-llm-wiki-journalism-productivity/) — 1,440페이지 규모 운영 후기
> - [Joi Ito의 응답 gist](https://gist.github.com/Joi/120f86eb39758ef75deb5e6145e5a717) — 모순 감지·provenance 부재 지적
> - 우리 스터디의 구현: 루트 [`CLAUDE.md`](../../../CLAUDE.md)(스키마) + [`wiki/`](../../../wiki/) (PR #16, 2026-09-16)

## 한 줄 요약

RAG가 질문할 때마다 원문 조각을 다시 찾아 조립한다면, LLM 위키는 **소스가 들어올 때 한 번 읽어 위키에 통합해 두고(compile), 질문은 그 위키에 대고 한다.** 사람은 소스를 고르고 질문하고, LLM이 요약·상호참조·정리라는 잡무(bookkeeping)를 전담한다.

## 핵심 개념

- **누적(accumulation)**: RAG는 "매 질문마다 처음부터 재발견"이라 아무것도 쌓이지 않는다. 위키는 소스와 질문이 더해질 때마다 부유해지는 **영속적이고 복리로 쌓이는 산출물(persistent, compounding artifact)**.
- **3층**: 불변 소재(raw sources) / LLM이 전적으로 소유하는 위키(wiki) / 위키 운영 규칙을 담은 스키마(schema, 예: `CLAUDE.md`).
- **3연산**: Ingest(소스 → 위키 통합) / Query(위키에 질문, 좋은 답은 다시 위키에 파일링) / Lint(모순·낡은 주장·고아 페이지 점검).
- **2파일**: `index.md`(내용 카탈로그, ingest마다 재작성) / `log.md`(시간순 append-only 로그).
- **역할 분담**: 사람 = 소싱·탐색·질문·의미 부여. LLM = 그 외 전부.
- 원문은 의도적으로 추상적이다. **명명 규칙, 인용 포맷, 페이지 템플릿, 모순 해결 정책은 원문에 없다.** 팀이 스키마로 정해야 한다.

## 상세 정리

### 1. 원문의 위치와 성격

- 2026년 4월 4일(UTC) 공개된 gist 한 개, 약 12KB, 이후 수정 없음. 포크 9,800개 이상(2026-09-16 기준).
- 스스로를 **"idea file"**이라고 부른다. "여러분의 LLM 에이전트(Codex, Claude Code, OpenCode 등)에 복사해 붙여 넣도록 설계됐다. 목적은 상위 아이디어를 전달하는 것이고, 세부는 에이전트가 여러분과 함께 만든다."
- 마지막 절: "이 문서는 의도적으로 추상적이다. 아이디어를 설명하지 특정 구현을 설명하지 않는다. … 전부 선택적이고 모듈식이다."

즉 **논문도 라이브러리도 아니고, 에이전트에게 주는 프롬프트에 가까운 패턴 문서**다. 그래서 그 위에 쌓인 2차 해석(비유, 수치, 계보)을 원문과 구분해서 읽어야 한다.

### 2. RAG와 무엇이 다른가 (원문 인용)

> "Most people's experience with LLMs and documents looks like RAG: … the LLM retrieves relevant chunks at query time, and generates an answer. This works, but **the LLM is rediscovering knowledge from scratch on every question. There's no accumulation.**"

> "The knowledge is **compiled once and then kept current**, not re-derived on every query."

> "This is the key difference: **the wiki is a persistent, compounding artifact.** The cross-references are already there. The contradictions have already been flagged. The synthesis already reflects everything you've read."

정리하면:

| | RAG | LLM 위키 |
|---|---|---|
| 지식이 만들어지는 시점 | 질문 시(query time) | 소스 투입 시(ingest time) |
| 매 질문의 작업 | 청크 검색 → 조립 → 답 | 위키 페이지 읽기 → 답 |
| 5개 문서를 합쳐야 답하는 질문 | 매번 5개 조각을 다시 찾아 합성 | 이미 합성된 페이지가 있음 |
| 모순 발견 | 그때그때, 운 좋으면 | ingest·lint 때 미리 표시 |
| 질문의 결과 | 채팅 히스토리에서 사라짐 | 좋은 답은 새 페이지로 되돌려 넣음 |
| 코퍼스 | 정적 | LLM이 계속 고쳐 씀 (write loop) |

**비용 오해 주의.** 검색 단계만 보면 RAG가 더 싸다. 벡터 유사도 검색은 LLM을 안 타지만 위키는 `index.md`를 LLM이 읽어야 한다. single-hop 단순 질문은 naive RAG(청크 몇 개 + 생성 1회)가 위키(index 읽기 + 페이지 읽기 + 생성)보다 호출도 토큰도 적다. 위키가 아끼는 건 **여러 문서를 합쳐야 하는 질문에서 advanced RAG가 추가하는 LLM 호출**(쿼리 재작성, 리랭킹, 멀티홉 루프 — [06번 노트](06-query-rewriting.md))과 **생성 입력의 밀도**(원문 청크 top-k 대신 정리된 페이지 1장)다. 원문에 비용 주장은 없고, 강조점은 비용이 아니라 축적이다.

원문이 쓰는 비유는 하나뿐이다: **"Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase."** 블로그에 흔한 "RAG는 매번 재컴파일, 위키는 실행파일" 비유는 2차 해석이지 원문 표현이 아니다.

### 3. 3층 구조

| 층 | 원문 정의 | 우리 레포 |
|---|---|---|
| **Raw sources** | "curated collection of source documents. **These are immutable** — the LLM reads from them but never modifies them. This is your source of truth." | `members/<id>/` 노트·실습 README·readings. `protect-raw.py` 훅이 다른 멤버 폴더 편집을 막음 |
| **The wiki** | "a directory of LLM-generated markdown files. … **The LLM owns this layer entirely.** … You read it; the LLM writes it." | `wiki/` (옵시디언 볼트, PARA 4폴더) |
| **The schema** | "a document (e.g. CLAUDE.md for Claude Code or AGENTS.md for Codex) that tells the LLM how the wiki is structured … **it's what makes the LLM a disciplined wiki maintainer rather than a generic chatbot.** You and the LLM co-evolve this over time." | 루트 `CLAUDE.md` |

핵심은 **소재 불변**과 **위키 소유권이 LLM에 있다**는 두 원칙이다. 사람이 위키를 직접 고치기 시작하면 LLM이 다음 ingest 때 덮어쓰거나 정합성을 잃는다. 고칠 게 있으면 소재를 고치고 재-ingest한다.

### 4. 3연산

**Ingest** — 소스 하나를 넣으면: 읽고 → 핵심을 사람과 논의하고 → 요약 페이지 작성 → index 갱신 → 관련 개체·개념 페이지 갱신 → log에 append. "**A single source might touch 10-15 wiki pages.**" Karpathy 본인은 한 번에 하나씩 붙어서 감독하는 쪽을 선호하지만 배치 ingest도 가능하다고 명시.

**Query** — index를 먼저 읽고 관련 페이지로 내려가 **인용과 함께** 합성. 답의 형태는 마크다운·비교표·Marp 슬라이드·matplotlib 차트 등 자유. 가장 중요한 통찰:

> "**good answers can be filed back into the wiki as new pages.** A comparison you asked for, an analysis, a connection you discovered — these are valuable and shouldn't disappear into chat history."

**Lint** — 주기적 건강 점검. 원문이 나열한 점검 항목 6개: 페이지 간 모순 / 새 소스가 대체한 낡은 주장 / 들어오는 링크 없는 고아 페이지 / 언급만 되고 자기 페이지가 없는 개념 / 빠진 상호참조 / 웹 검색으로 메울 수 있는 데이터 공백.

### 5. index.md와 log.md는 갱신 방식이 다르다

| 파일 | 축 | 갱신 | 용도 |
|---|---|---|---|
| `index.md` | 내용 | ingest마다 **재작성** | 페이지별 링크 + 한 줄 요약. 질문 때 **가장 먼저 읽는 탐색 표면** |
| `log.md` | 시간 | **append-only** | `## [2026-04-02] ingest \| 제목` 접두를 맞추면 `grep "^## \[" log.md \| tail -5`로 최근 활동 조회 |

원문이 주는 규모 수치: "**~100 sources, ~hundreds of pages**"까지는 index 파일만으로 충분하고 **임베딩 RAG 인프라가 필요 없다.** 그 이상이면 [qmd](https://github.com/tobi/qmd)(BM25+벡터 하이브리드, LLM 리랭킹, CLI+MCP) 같은 로컬 검색을 붙이라고 권한다.

→ 재밌는 지점: 위키가 커지면 결국 위키 위에 하이브리드 검색(4번 노트)이 다시 필요해진다. **RAG의 대체가 아니라 RAG 앞단의 "정제된 코퍼스"**로 보는 게 정확하다.

### 6. 왜 작동하는가

> "The tedious part of maintaining a knowledge base is not the reading or the thinking — **it's the bookkeeping.** … **Humans abandon wikis because the maintenance burden grows faster than the value.** LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass."

Vannevar Bush의 Memex(1945)를 계보로 든다. "Bush가 못 푼 부분은 **누가 유지보수를 하느냐**였다. LLM이 그걸 맡는다."

### 7. 2026년 4~9월 생태계

- **구현체**: [nashsu/llm_wiki](https://github.com/nashsu/llm_wiki)(데스크톱 앱, 19k★), [AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian)(`wiki-ingest`·`wiki-lint` 슬래시 커맨드), [inkeep/open-knowledge](https://github.com/inkeep/open-knowledge)(마크다운 IDE), [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki)(gist 당일 공개, MCP)
- **옵시디언 플러그인**: Karpathy LLM Wiki, Auto LLM Wiki, AI RAG + LLM Wiki(RAG와 병행) 등 공식 레지스트리에 10개 안팎
- **기관 차원**: LangChain "Wiki Memory"(2026-06) — "RAG는 질문 시 원문 청크를 가져오지만, 위키는 **상위 수준 합성을 미리 계산해 유지**하므로 에이전트가 구조를 매번 재발견하지 않아도 된다." Google Cloud **Open Knowledge Format(OKF, 2026-06)** — 프론트매터 있는 마크다운 디렉터리를 에이전트 간 교환 포맷으로 규격화.
- **주의**: "Cognition DeepWiki가 Karpathy를 보고 만들어졌다"는 서사는 틀렸다. DeepWiki는 2025년 4월 출시로 **1년 앞선다**. 같은 아이디어로 독립 수렴한 사례.

### 8. 비판과 한계

| 비판 | 내용 | 반론 / 대응 |
|---|---|---|
| "이건 그냥 RAG다" | 벡터 DB 대신 index 파일과 폴더 구조를 쓰는 검색일 뿐 | 차이는 **write loop**. 바닐라 RAG는 코퍼스가 정적, 여기선 LLM이 코퍼스를 고쳐 쓴다. lint는 RAG에 없는 연산 |
| 2차 정보의 오류 누적 | 위키를 읽는 건 원문 대신 LLM 요약을 읽는 것. 환각이 **구조화·영구화**됨 (DeepWiki도 사실 오류 사례 있음) | 소재를 불변으로 두고 출처 링크 강제. 검증 안 된 주장은 `TODO: unverified` 표시. 중요한 답은 소재로 내려가 확인 |
| Lint의 스케일 | N페이지 간 모순 탐색은 N² 비교. 어느 임계점 넘으면 에이전트도 사람도 못 따라감 | 원문도 ~100 소스 스코프. 그 이상은 검색 도구 + 부분 lint |
| 유지보수 ≈ 절약 시간 | R&D World 한 달 후기: 760페이지, 자동 갱신 안 됨, 이미 온라인에 잘 정리된 주제엔 가치 낮음 | 자기만 가진 소재(대화, 회의록, 실험 기록)에 쓸 때 가치가 큼 |
| 사고의 외주 | "정리하는 동안 아이디어가 떠오른다" — 잡무를 넘기면 자기 멘탈 모델이 안 바뀜. 실제 도입자가 "persistent brain gap"이라는 새로운 기술 부채 보고 | 사람이 ingest에 붙어서 논의하는 Karpathy 방식이 이 손실을 줄임 |
| 합의로의 수렴 | LLM은 읽은 것의 평균으로 수렴하는 중력이 있어 위키가 "smoothing"이 됨 (jonadas, cognitive governance) | 스키마에 "반대 의견 명시, 마찰 지점 추출" 같은 능동 제약을 넣음 |
| 엔터프라이즈 | 마크다운 폴더엔 권한 제어·동시 쓰기 충돌 방지·실시간 신선도 전파가 없음 | 원문 스코프는 "personal knowledge bases". 다중 작성자·권한 분리 환경은 RAG/DB가 여전히 우위 |

Joi Ito의 지적이 가장 실용적이다: Karpathy 패턴에는 **모순 감지 절차와 provenance 로깅이 없다.** lint가 모순을 "찾는다"까지만 있고 "어느 쪽이 이기는가"는 없다. 이건 스키마가 채워야 할 빈칸이다.

### 9. 우리 스터디 위키는 어떻게 채웠나

원문이 비워 둔 빈칸을 루트 `CLAUDE.md`가 어떻게 메웠는지가 이번 주 발표의 실물 예시다.

| 원문의 빈칸 | 우리 결정 |
|---|---|
| 위키 폴더 구조 | PARA: `0-pending / 1-projects / 2-areas / 3-resources / 4-archives`. 스터디 지식은 대부분 resource |
| 명명 | 한국어 자연어 파일명, 띄어쓰기는 `-`, 약어(BM25·RRF·HNSW)는 그대로. basename 유일 |
| 링크 | 옵시디언 `[[basename]]`. 소재(`members/`)는 볼트 밖이라 `## 출처`에 상대경로 링크 |
| 프론트매터 | `title/type/tags/status/created/updated` 필수, `members/weeks/source` 선택 |
| 페이지 본문 | 한 줄 정의 → 정의·원리·강점약점 → **멤버들이 확인한 것(누가 어떤 데이터로)** → 함정 → 열린 질문 |
| 인용과 정직 | 출처 없는 주장은 `> TODO: unverified`. 노트끼리 다르면 `> ⚠️ Contradiction:`으로 양쪽 병기. "X가 정리했다"와 "X가 측정했다" 구분 |
| 소재 보호 | `protect-raw.py` PreToolUse 훅: 본인 폴더 외 `members/` 편집 차단 |
| bookkeeping 강제 | `check-bookkeeping.py` Stop 훅: 위키를 바꾸고 `log.md`를 안 건드리면 멈춤 |
| 머지 대기 소재 | 미머지 PR도 ingest하되 출처에 `(PR #n 미머지)` 표시, 머지되면 지움 |
| 민감 정보 | 카톡·노션 대화 원문은 옮기지 않음. 통계만 |

현재 상태(PR #16): 페이지 30장(프로젝트 1, 에어리어 2, 리소스 27). 멤버 12명이 각자 쓴 "검색의 세 세대"·"RAG 변천사"·"하이브리드 검색과 RRF" 노트가 주제별 한 페이지로 합쳐졌고, 누가 어떤 조건에서 뭘 측정했는지가 한 표에 모인다. 사일로화된 노트를 **주제별로 합성**하는 것이 이 위키의 존재 이유다.

### 10. 언제 위키, 언제 RAG

| 상황 | 권장 |
|---|---|
| 소스 수십~수백, 나만/우리 팀만 가진 자료, 몇 달간 계속 파는 주제 | 위키 |
| 소스 수만 건, 실시간 변경, 권한 분리, 다중 작성자 동시 편집 | RAG (+DB) |
| 둘 다 | 위키를 **정제된 코퍼스**로 두고 그 위에 하이브리드 검색. 원문도 qmd를 권함 |

## 예시 / 코드

`log.md` 접두 규약 덕에 최근 활동을 셸로 볼 수 있다:

```bash
grep "^## \[" wiki/log.md | tail -5
# ## [2026-09-16] setup | 위키 초기화
# ## [2026-09-16] ingest | PR #6 sese2204 인프라·카카오톡 실습
# ...
```

위키 규모 확인:

```bash
ls wiki/3-resources/*.md | wc -l   # 개념·비교·함정 페이지 수 (2026-09-16: 27)
```

## 궁금한 점 / 더 알아볼 것

- [ ] 위키 페이지가 100장을 넘으면 index만으로 Query가 버티는지 실측 (qmd를 붙이는 시점 판단)
- [ ] lint를 주 1회 돌렸을 때 모순 표시가 몇 건 나오는지, 그중 실제 오류 비율
- [ ] 위키 Query 응답을 [RAGAS](10-ragas.md)로 평가해 "소재 직접 RAG" 대비 faithfulness가 어떻게 다른지

## 스터디에서 나눌 이야기

- 각자 자기 노트를 위키가 어떻게 합성했는지 `wiki/3-resources/`에서 찾아보고, 잘못 옮긴 곳이 있으면 노트를 고쳐 재-ingest 요청
- 모순이 났을 때 "어느 쪽이 이기는가" 정책을 스키마에 넣을지 (최신 소재 우선? 측정치 우선? 병기만?)
- 위키를 발표 자료(Marp)로 뽑아 쓰는 실험을 해볼지
