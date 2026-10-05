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

## [2026-09-17] refactor | 폴더 구조 PARA → 페이지 종류별 (concepts · entities · comparisons · sources · inbox)
- moved: 3-resources/ 27편 → concepts/ 18편 · comparisons/ 4편(검색의-세-세대, 임베딩-모델-선택, RAG-변천사, 실습-비교표) · entities/ 3편(PostgreSQL과-pgvector-함정, Elasticsearch-운영-함정, OpenViking-컨텍스트-데이터베이스) · sources/ 2편(스터디-노트-지도, LLM-위키-패턴). 2-areas/ 로컬-인프라·현황판 → entities/. 1-projects/10기-KG-스터디/10기-KG-스터디.md → entities/10기-KG-스터디.md. 0-pending/ → inbox/. 4-archives/ 삭제(보관은 `status: archived` + index Archived 절로)
- updated: 전 페이지 frontmatter `type` = 폴더명(concept · entity · comparison · source). 10기-KG-스터디 정의문의 `3-resources/` 언급, LLM-위키-패턴 푸터 링크(`../../CLAUDE.md`), index(폴더별 재편), CLAUDE.md(디렉터리 구조·종류 판별·frontmatter·본문 형태·Ingest·Archive·index 형식·log 예시·훅 절), README.md, .claude/hooks/check-bookkeeping.py(CONTENT_ROOTS)·session-rules.sh·README.md
- templates: resource.md → concept.md, project.md+area.md → entity.md(타임라인 절은 선택), comparison.md 신설, note.md는 inbox/ 용
- verified: 위키링크 32페이지 전부 해결(basename 유일), 깨진 상대 링크는 미머지 PR #6·#11 소재뿐(이전과 동일)
- note: members/sese2204/notes/08-llm-wiki.md 가 PARA 구조를 설명하고 있음 — 소재라 위키 작업에서 안 고침, 작성자가 갱신할 것

## [2026-10-02] lint | 머지된 PR #12·#15 의 미머지 표시 제거
- updated: 출처의 `(PR #12 미머지)`·`(PR #15 미머지)` 표시를 뗐다 — 임베딩-모델-선택, grep-문자열-매칭, 멀티홉-질문과-Bridge-Entity, 저장-구조-LSM과-B-tree, RAG-평가-지표, 역색인과-BM25, 청킹-전략, 하이브리드-검색과-RRF, RAG-루프와-근거-인용, 한국어-토크나이징-nori와-n-gram, 데이터-수집과-출처-추적, HNSW와-pgvector-인덱스, RAG-실패-유형. #12(heebindev 공용 인프라 이전)·#15(lys0611 W1~W3)는 2026-09-16 머지됨 (`gh pr list --state merged`). 실습-비교표·10기-KG-스터디·스터디-노트-지도·index 의 같은 표시는 이어지는 ingest 에서 페이지를 다시 쓰며 정리한다.
- note: 2026-09-17 이후 밀린 소재 81건(약 9만 단어)의 ingest 를 주차별로 나눠 진행 중. 주간 자동 ingest(`.github/workflows/wiki-ingest.yml`, `scripts/wiki_backlog.py`) 도입.

## [2026-10-02] ingest | 3~5주차 밀린 소재 전체 (origin/main a5e4f87 → ddf52f6, PR #19·#34·#36 미머지 포함)
- 범위: 2026-09-17 이후 머지된 PR #28~#41 + 그 전에 지도에 빠져 있던 #17·#18·#20~#26 소재. 멤버 문서 110여 건, 약 10만 단어. 읽기는 opus 서브에이전트 7개(3주차 실습 / 3주차 노트 / Yeongeunn·yujeong430 / 4주차 dldusgh318 / 4주차 나머지 / 5주차 / 4·5주차 kdyann·Yeongeunn·kungbi)로 나눠 보고받고 쓰기는 직접 했다.
- created (concepts 9): 시맨틱-웹에서-지식그래프까지(comparison), RDF와-트리플, 온톨로지와-추론, SPARQL, RDF와-프로퍼티-그래프(comparison), 기업-지식그래프-사례(comparison), 폐쇄-스키마-설계, LLM-트리플-추출, 엔티티-신원해소, 그래프-적재-Postgres와-Neo4j, RAG-vs-그래프-질의(comparison), 챗봇-평가-층위와-심판, LLM-위키의-한계와-비판, 모델-역할-분담(comparison), 생성-모델-선택(comparison)
- created (entities 4): Wikidata와-DBpedia, Palantir-Foundry-Ontology, RAGAS, BEIR
- updated (전면 재작성): 지식그래프와-온톨로지(KG 허브로 — "그래프를 만든 멤버 없음"·"RDFS/OWL 미정의" 삭제, 다섯 멤버 결과 표), 하이브리드-검색과-RRF(열한 평가셋 성적표, 정규화 융합 반례 ⚠️, "다른 k 실험 없음" 삭제), RAG-평가-지표(누가 정답을 정했나 축, 열세 멤버 현황, 추출 층 추가), 실습-비교표(스물여섯 실습 + 그래프 실습 표), 10기-KG-스터디(타임라인 5주차까지, 멤버 진행, 남은 일), 스터디-노트-지도(14명 전부, 기준 ddf52f6), index
- updated (절 추가·수정): 멀티홉-질문과-Bridge-Entity(X01–X03, H01 재분류, 스키마 예고 교체, 다섯 멤버 처방 실측, 5칸 템플릿, 세 반례), RAG-실패-유형(X01–X03 Oracle 표, 융합 탈락·귀속 오류·연결 실패·라벨 누락, 7유형 귀속 주의, OWA 절), RAG-루프와-근거-인용(Citation 3단계, 검증 강도 5단계 표, 여덟 멤버 생성 실측, "do-dop 미구현" 삭제), 쿼리-재작성(분해·재검색 실측, Self-RAG/CRAG 구분), 데이터-수집과-출처-추적(수집 대상 선정, Citation vs Provenance, 5주차 근거·검토 표, 정본 3단으로 모순 해소 방향), 검색의-세-세대(sdunge·sunghyun·Yeongeunn·do-dop 03, 질의 통일 모순에 시점), HNSW와-pgvector-인덱스(10.2배·일치율 1.0·기준선 만들기·recall 두 뜻), 청킹-전략(일곱 행 추가, 경로 프리픽스 부작용, 창 평균), 역색인과-BM25(OR/AND vs 점수, 제목 vs 본문 색인, 동기화), grep-문자열-매칭(네 행), 임베딩-모델-선택(일곱 행, 평가셋≠벤치마크, 고정 7항목), 임베딩과-벡터-검색, 한국어-토크나이징(bigram 혼동), 저장-구조-LSM과-B-tree(Yeongeunn·DDIA 2장), 리랭커(nDCG), 개인-데이터-가명화와-공개-범위(임베딩 로컬·추출 외부, 평가셋 공개 가능성), RAG-변천사(BEIR 판정, GraphRAG 자리, 패턴 정밀화), 로컬-인프라(sunghyun·dldusgh318 Neo4j·e0ng 05 공용, Neo4j 첫 실사용, infra README는 main에 있음), Elasticsearch-운영-함정(버전 여섯, 재색인 삭제 미반영), PostgreSQL과-pgvector-함정(기준선, 재귀 CTE 절), OpenViking(kungbi 02 경계)
- flagged (모순, 페이지에 ⚠️로 남김): RRF가 평균을 올리는가(승 2·동률 3·패 4+), 정규화 융합 실효성(do-dop 실측 반례), "경로 없음"은 답인가 모름인가(do-dop vs 열린 세계 가정), 닫힌 스키마의 효과(통과율 99.38% vs 의미 오류 3/8 — 다른 것을 잼), RDF vs PG 표의 단정 강도, Neo4j vs Postgres 시작(sunghyun vs dldusgh318 — 5주차에 자기 확장), Adaptive RAG vs Self-RAG 귀속, BEIR 결론 강도(원문 기준 완화로 판정), RAGAS는 reference-free인가(소재가 자기 보정), 정직한 거절의 채점(lys0611 실측 vs RAGAS 설계)
- flagged (낡아서 교체한 위키 주장): H01 "3-hop" → "3-hop 후보/Retrieval 질문"(저자 재분류), dldusgh318 4주차 스키마 예고(caused_by 등) → 실제 4관계·X01, "e0ng 실측 없이" → 5주차 그래프, "do-dop RAG 미구현" → 구현, "sunghyun 열린 질문만" → 실측, kdyann·heebindev·e0ng·Yeongeunn 평가셋 행, "열한 실습" → 스물여섯, lys0611 "PR #15 미머지"·heebindev "PR #12" 제거, 노트 지도의 "do-dop names.json 미등재"·"Yeongeunn 전부 비어 있음"·"sdunge 전부 빈 파일"
- flagged (소재 정정 요청 — members는 불변): dldusgh318 README 깨진 링크(06-failure-to-kg-design.md), do-dop kg-build-plan.md 부재, jjinthung labs/02 README가 sdunge 경로 참조, e0ng 04-2 mermaid 중복·캡처 부재, sese2204 08 옛 PARA 경로, yujeong430 PR #19의 rag_limitations.md 부재·README 10·11 누락, Yeongeunn readings www-prod URL, status: complete 4건, frontmatter 없음(dldusgh318 week4·5, Yeongeunn 전부, do-dop labs/03, jjinthung, sdunge), 태그 표기 불일치(multi-hop question 공백, evaluation/rag-evaluation/retrieval-evaluation 등)
- flagged (현황판 스캐너): 미포착 — sunghyun note/, dldusgh318 notes/week*·WEEK*·SCHEMA, do-dop labs/03의 README 외 md, sdunge labs/readme.md, Yeongeunn labs/README.md·schemas/, jjinthung labs/*/README 없음. 과대 집계 — sunghyun labs/01·04 껍데기, note/01·02와 notes/01·02 중복 주제
- flagged (민감 정보 — 위키에 옮기지 않음): 멤버 실명·소속 기관을 RDF 예시 주어로 쓴 노트 여럿(ex:person으로 치환), dldusgh318 자체 compose·공용 Neo4j 비밀번호 평문, kdyann 게시물 ID·permalink, Yeongeunn 사내 업무 정책·거래 상품명, sunghyun 사내 제품 약어, yujeong430 공지 질문 문장, e0ng 04-2 취업 지원 관련 절. CLAUDE.md 소재 범위에 Yeongeunn schemas/*.ttl 같은 보조 자료를 넣을지는 미결(지도에만 적음)
- note: Palantir·RAGAS·BEIR·Wikidata 등 고유명사는 CLAUDE.md "도구는 entity" 규칙대로 entities/에. SPARQL은 질의 언어(일반명사)라 concepts/에. 새 페이지는 전부 _templates 구조를 따랐고 상태는 maintained(소재 3명 이상) 또는 draft(1~2명)
- note: 주간 자동 ingest 도입 — `.github/workflows/wiki-ingest.yml`(월 09:00 KST, claude-code-action, PR 생성), `.github/prompts/wiki-ingest.md`, `scripts/wiki_backlog.py` + 테스트. CLAUDE.md·CONTRIBUTING·README에 한 줄씩. 시크릿(CLAUDE_CODE_OAUTH_TOKEN 또는 ANTHROPIC_API_KEY)과 "Allow GitHub Actions to create and approve pull requests" 설정은 저장소 관리자가 해야 한다
