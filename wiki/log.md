---
title: Log
type: resource
tags: [methodology]
status: maintained
created: 2026-09-16
updated: 2026-09-16
---

# Log

Append-only, 최신이 아래. 항목은 `## [YYYY-MM-DD] verb | title` 로 시작한다:
`grep "^## \[" wiki/log.md | tail -5`.

동사: `setup` · `ingest` · `query` · `lint` · `refactor` · `archive`.

---

## [2026-09-16] setup | LLM 위키 방법론 도입 (sese2204/dev-docs 방식 이식)
- created: 루트 CLAUDE.md(스키마·운영 지침), wiki/index.md, wiki/log.md, wiki/_templates/{project,area,resource,note}, wiki/0-pending/, wiki/4-archives/, wiki/.obsidian/(볼트 = wiki/)
- created: .claude/settings.json + hooks/{session-rules.sh, protect-raw.py, check-bookkeeping.py, README.md}. protect-raw는 dev-docs에 없던 훅 — 이 저장소는 members/가 불변 소재 층이라 도입. 본인 폴더(gh 로그인)는 허용, 다른 멤버 폴더는 차단(exit 2), 로그인 불명이면 경고 후 통과
- created: 3-resources/LLM-위키-패턴.md (dev-docs의 원문 복사, frontmatter만 이 저장소용)
- updated: .gitignore(옵시디언 개인 상태, settings.local.json), README.md("스터디 위키" 절, 구조 트리), CONTRIBUTING.md(wiki/ 직접 편집 금지, ingest 절차), scripts/build_dashboard.py(wiki/·.claude/·CLAUDE.md를 인프라 커밋으로 분류 — 현황판 중계에서 제외, 테스트 51개 통과)
- note: 세 층 = members/(불변 소재) · wiki/(에이전트 소유, PARA) · CLAUDE.md(스키마). 위키링크는 wiki/ 안에서만, members/ 소재는 `## 출처`의 저장소 상대경로 링크. 머지 대기 PR 소재도 ingest하되 `(PR #n 미머지)` 표시. 브랜치 sese2204/llm-wiki (origin/main 0664c4c 기준), 커밋은 요청 시

## [2026-09-16] ingest | 소재 전체 초기 증류 — origin/main 0664c4c + PR #6·#11·#12·#15
- read: 멤버 14명의 노트 27편·실습 문서 22편·README·readings (약 11,200줄). 읽기 전용 서브에이전트 7개가 추출 시트를 만들고 페이지는 직접 작성
- created: 1-projects/10기-KG-스터디/10기-KG-스터디.md (허브 — 타임라인·주차 재구성·멤버 표·의사결정·남은 일)
- created: 2-areas/로컬-인프라.md, 2-areas/현황판.md
- created: 3-resources/ 26편 — 검색의-세-세대, grep-문자열-매칭, 역색인과-BM25, 한국어-토크나이징-nori와-n-gram, 임베딩과-벡터-검색, HNSW와-pgvector-인덱스, 청킹-전략, 임베딩-모델-선택, 하이브리드-검색과-RRF, 리랭커, 쿼리-재작성, RAG-루프와-근거-인용, RAG-실패-유형, 멀티홉-질문과-Bridge-Entity, RAG-평가-지표, RAG-변천사, 지식그래프와-온톨로지, OpenViking-컨텍스트-데이터베이스, 데이터-수집과-출처-추적, 카카오톡-대화-내보내기-파싱, 개인-데이터-가명화와-공개-범위, PostgreSQL과-pgvector-함정, Elasticsearch-운영-함정, 저장-구조-LSM과-B-tree, 실습-비교표, 스터디-노트-지도
- updated: index
- flagged (⚠️ Contradiction, 페이지에 표시): Adaptive RAG 시기(sese2204 2025~26 vs kdyann 2024) · BEIR 결론 강도 · 리랭커 상시(e0ng) vs 조건부(sese2204) · 인용 검증 문자열 포함(dldusgh318) vs 의미 비교(e0ng) · dldusgh318 05/06의 실패 유형 5종 vs 4종 · 멀티홉 예제 인물·정답 불일치 · 청킹 의미 단위(sunghyun) vs 고정 분할(sese2204) · 정본 단일+projection(kungbi) vs 병렬(sunghyun) · 세 방식의 검색 단위 통일(ur2e·dldusgh318) vs 방식별 단위(do-dop·heebindev·yujeong430) · 방식별 다른 질의(yujeong430) · n-gram 오타 강함 vs 형태소 우연 겹침(dldusgh318 내부) · lys0611 GUIDE/RUNBOOK의 OpenAI 기본값 vs 실제 로컬 KURE-v1 · 벡터 "의미 검색" 전제(e0ng·do-dop) vs 실측 반증(ur2e·jjinthung)
- note: 실측 수치가 있는 곳은 dldusgh318(Notion 1,562청크, Recall@5/10), lys0611(카카오톡 1,922청크, 27문항 R@k·34문항 생성), e0ng(P@5·지연), ur2e(Hit@3·MRR), jjinthung(Hit@k), do-dop·heebindev·kdyann(히트 수). 리랭커·쿼리 재작성·트리플 추출은 아직 아무도 실측하지 않음. 대화 원문·이름·장소는 옮기지 않고 통계만 기록
- next: PR #6·#11·#12·#15 머지 시 출처 표시 갱신 · 4주차 그래프 실습 결과 ingest · 공용 골든셋 결정되면 프로젝트 페이지

## [2026-09-16] lint | 초기 ingest 중 발견한 소재 문제 (수정은 각 멤버 몫)
- flagged: `members/sunghyun/note/`(단수), `members/dldusgh318/notes/week2|week3/`, `labs/01-three-generations/WEEK*.md`는 현황판 스캐너(notes/*.md, labs/*/README.md)에 안 잡힘. dldusgh318 README가 링크한 `WEEK3.md`는 없음
- flagged: `members/names.json`에 do-dop·ur2e 없음. cohorts.json은 A반 7명만
- flagged: 빈 파일·스텁 — jjinthung `02_BM25.md`·`Readme.md`("test"), sdunge notes/labs/readings/Data 전부 빈 파일, Yeongeunn README 빈 파일, main의 lys0611 `notes/W-01`·`labs/W-01`(빈 파일, PR #15가 대체)
- flagged: frontmatter 없음 — dldusgh318 노트 6편·실습 문서, jjinthung, yujeong430 실습 README(status 없음). heebindev 02는 개요 문장이 본문에 남아 있고 n-gram 절이 비어 있음
- flagged: 소재 태그 표기 불일치 — `vector-search`/`embedding`/`hnsw`, `search`/`information-retrieval`, `bm25`/`keyword-search-bm25`, `rag`는 거의 모든 노트에. 위키 개념 페이지 파일명을 정본 슬러그로 삼는 것을 제안(현황판 태그와 맞추는 건 별도 결정)
- flagged: 문서 내부 불일치 — sese2204 02 README의 청킹 기본값(30분/166자 vs 예시 60분/300자), dldusgh318 WEEK2 청크 스키마 vs data_sample README, lys0611 노트 05의 생성 실패 유형 10건 vs failures.md 12건, 채점 주체 표기("내가" vs "Claude가 1차")
