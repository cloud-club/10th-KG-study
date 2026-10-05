---
title: LLM 위키의 한계와 비판 — 이 위키가 알고 있어야 할 것
type: concept
tags: [concept, rule]
status: draft
created: 2026-10-02
updated: 2026-10-02
members: [sese2204]
weeks: [3]
---

> 이 저장소의 `wiki/`가 따르는 패턴([[LLM-위키-패턴]], Karpathy 2026-04 gist)에 대한 2차 해석·비판·비용 구조를 모은 페이지. 원문 페이지는 편집하지 않으므로 여기에 둔다. 핵심은 둘 — **위키가 아끼는 것은 검색 비용이 아니라 advanced RAG의 추가 LLM 호출과 생성 입력의 밀도**이고, 원문 패턴에는 **모순 감지 절차와 provenance 로깅이 없다**(Joi Ito). 둘 다 이 저장소의 `CLAUDE.md`가 채워야 할 빈칸이었고, 일부는 채웠다.

## 정의

- 누적이 핵심: RAG는 매 질문마다 재발견해 아무것도 쌓이지 않고, 위키는 *persistent, compounding artifact*다. 3층(불변 소재 / LLM 소유 위키 / 스키마) · 3연산(Ingest · Query · Lint) · 2파일(`index.md` 재작성 / `log.md` append-only).
- 원문의 성격: 2026-04-04 gist 하나, 약 12KB, 이후 수정 없음, 스스로 "idea file". **논문도 라이브러리도 아니고 에이전트에게 주는 프롬프트에 가까운 패턴 문서**라 2차 해석과 구분해 읽어야 한다. 원문의 비유는 하나뿐 — *"Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase."* "재컴파일/실행파일" 비유는 2차 해석이다.
- 규모 임계: "~100 sources, ~hundreds of pages"까지는 index만으로 충분하고 임베딩 RAG 인프라가 불필요. 그 이상은 qmd(BM25 + 벡터 하이브리드, LLM 리랭킹). sese2204의 해석: **RAG의 대체가 아니라 RAG 앞단의 '정제된 코퍼스'.** *"The tedious part is not the reading or the thinking — it's the bookkeeping."* Memex(1945) 이래 못 푼 것은 "누가 유지보수하느냐".

## 비용 오해 (sese2204)

- 검색 단계만 보면 RAG가 싸다 — 벡터 검색은 LLM을 안 타지만 위키는 `index.md`를 LLM이 읽는다. **single-hop 단순 질문은 naive RAG가 호출·토큰 모두 적다.** 위키가 아끼는 것은 ① advanced RAG가 추가하는 LLM 호출(쿼리 재작성·리랭킹·멀티홉 루프) ② 생성 입력의 밀도(top-k 청크 대신 정리된 페이지 1장). **원문에 비용 주장은 없다.**

## 비판 일곱 가지

| 비판 | 요지 | 이 위키의 대응 |
|---|---|---|
| "그냥 RAG다" | 차이는 **write loop**과 lint | Ingest가 쓰고 Lint가 점검한다 |
| 2차 정보 오류 누적 | 환각이 구조화·영구화된다 | `> TODO: unverified`, "정리했다"와 "측정했다" 구분, 출처 필수 (`CLAUDE.md`) |
| Lint의 N² 스케일 | 페이지가 늘수록 모순 검사 비용이 제곱으로 | 2026-10-02 기준 50페이지, 아직 사람이 감당 |
| 유지보수 ≈ 절약 시간 | R&D World: 760페이지, 자동 갱신 안 됨 | 주간 자동 ingest 워크플로(`.github/workflows/wiki-ingest.yml`)로 유지보수를 기계에 |
| 사고의 외주 | "persistent brain gap" | 소재는 사람이 쓰고 위키는 합성만 한다 |
| 합의로의 수렴 | 위키가 "smoothing"한다 | `> ⚠️ Contradiction:`으로 양쪽을 남긴다 |
| 엔터프라이즈 | 권한·동시 쓰기·신선도 없음 | PR 기반, 단일 작성자(에이전트) |

- **가장 실용적인 지적 (Joi Ito)**: 패턴에는 모순 감지 절차와 provenance 로깅이 없다. lint가 모순을 "찾는다"까지만 있고 "**어느 쪽이 이기는가**"는 없다. 이 위키의 규칙은 양쪽을 드러내되 판정하지 않는 것이고, 소재가 스스로 고치면(예: sese2204의 RAGAS 보정, dldusgh318의 H01 재분류) 그걸 따른다. 판정이 필요한 모순은 [[10기-KG-스터디]] 의사결정으로.
- 생태계 (sese2204 조사, 미검증): 구현체 4종, 옵시디언 플러그인 10개 안팎, LangChain "Wiki Memory"(2026-06), Google Cloud OKF(2026-06). "DeepWiki가 Karpathy를 보고 만들어졌다"는 서사는 틀렸다 — 2025-04 출시로 1년 앞선다.

## 함정 · 주의

- sese2204의 노트 08은 이 위키의 **옛 폴더 구조(PARA)**를 설명하고 `wiki/3-resources/…` 경로를 안내한다. 2026-09-17에 `concepts/entities/comparisons/sources/inbox`로 바뀌었고 노트는 그 전에 쓰였다. `members/`는 불변이므로 위키가 고칠 수 없다 — 작성자가 갱신할 것. 노트의 "멤버 12명"도 `names.json` 13명·위키 14명과 다르다.

## 관련

- [[LLM-위키-패턴]] · [[10기-KG-스터디]] · [[현황판]] · [[데이터-수집과-출처-추적]] (provenance) · [[RAG-변천사]]

## 출처

- sese2204 · LLM 위키 — [members/sese2204/notes/08-llm-wiki.md](../../members/sese2204/notes/08-llm-wiki.md); readings 3주차 — [members/sese2204/readings.md](../../members/sese2204/readings.md)
- 외부: Karpathy, LLM Wiki gist https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f · HN 토론 https://news.ycombinator.com/item?id=47640875 · LangChain Wiki Memory https://www.langchain.com/blog/wiki-memory · R&D World, Is Karpathy's viral LLM wiki helpful? https://www.rdworldonline.com/is-karpathys-viral-llm-wiki-helpful-mostly-yes-one-month-in/ · Platformer https://www.platformer.news/karpathy-llm-wiki-journalism-productivity/ · Joi Ito gist https://gist.github.com/Joi/120f86eb39758ef75deb5e6145e5a717 · qmd https://github.com/tobi/qmd · 구현체 https://github.com/nashsu/llm_wiki · https://github.com/AgriciDaniel/claude-obsidian · https://github.com/inkeep/open-knowledge · https://github.com/lucasastorian/llmwiki
