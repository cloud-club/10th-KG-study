# 읽을거리

## 2주차 · 고전 RAG 훑기

- [Lewis et al., Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks (2020)](https://arxiv.org/abs/2005.11401) — RAG라는 이름의 출발점. 검색기+생성기 결합의 원형
- [Karpukhin et al., Dense Passage Retrieval (2020)](https://arxiv.org/abs/2004.04906) — BM25를 dense 검색이 처음 제대로 이긴 논문
- [Thakur et al., BEIR (2021)](https://arxiv.org/abs/2104.08663) — 도메인 밖에서는 dense가 BM25에 지기도 한다는 걸 보여준 벤치마크
- [Khattab & Zaharia, ColBERT (2020)](https://arxiv.org/abs/2004.12832) — late interaction. 리랭커와 bi-encoder 사이의 절충
- [Gao et al., RAG for LLMs: A Survey (2023)](https://arxiv.org/abs/2312.10997) — Naive → Advanced → Modular RAG 흐름을 한 번에 보는 서베이
- [Anthropic, Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) — 청크마다 문서 맥락을 앞에 붙여 검색 실패율을 줄이는 방법
- [Jina, Late Chunking](https://jina.ai/news/late-chunking-in-long-context-embedding-models/) — 임베딩 먼저, 청킹 나중에
- 『AI 에이전트 엔지니어링』 (마이클 알바다 저 / 강민혁 역, 한빛미디어, 2026.01) — RAG 변천사 장을 참고
- [zg(zvec-grep) — 키워드를 넘어서는 로컬 검색 인프라 (GeekNews)](https://news.hada.io/topic?id=33183) — Qwen 팀의 ripgrep 확장. 벡터 + BM25 하이브리드를 RRF로 합치고 16M 온디바이스 임베딩으로 코드·문서를 의미 검색. 하이브리드 검색 노트의 실전 사례

## 4주차 · LLM 위키와 챗봇 평가

- [Karpathy, LLM Wiki (gist, 2026-04-04)](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — 소재/위키/스키마 3층, ingest·query·lint 3연산. 우리 `wiki/`가 따르는 패턴의 원문
- [LangChain, Wiki Memory: File-Based Memory for AI Agents (2026-06)](https://www.langchain.com/blog/wiki-memory) — 위키를 에이전트 메모리로 보는 관점. RAG는 원문 청크, 위키는 미리 계산한 합성
- [R&D World, Is Karpathy's viral LLM wiki helpful? Mostly yes (2026-06)](https://www.rdworldonline.com/is-karpathys-viral-llm-wiki-helpful-mostly-yes-one-month-in/) — 한 달 운영 후기. 유지보수 시간 ≈ 절약 시간, 자동 갱신 안 됨
- [HN: LLM Wiki – example of an "idea file"](https://news.ycombinator.com/item?id=47640875) — "이건 그냥 RAG다" vs "write loop과 lint가 다르다" 논쟁
- [Zheng et al., Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (2023)](https://arxiv.org/abs/2306.05685) — LLM 심판이 사람과 80%+ 일치한다는 근거이자 위치·장황함·자기선호 편향을 처음 정리한 논문
- [Chen et al., Benchmarking LLMs in RAG (RGB, 2023)](https://arxiv.org/abs/2309.01431) — RAG가 갖춰야 할 4가지 능력: 노이즈 견디기, 거부, 정보 통합, 반사실 견디기
- [Ru et al., RAGChecker (2024)](https://arxiv.org/abs/2408.08067) — 클레임 단위 함의 판정으로 검색기/생성기 실패를 분해하는 진단 지표
- [Katsis et al., MTRAG (2025)](https://arxiv.org/abs/2501.03468) — 멀티턴 RAG 벤치마크. 후반 턴·비독립 질문·답 없는 질문을 강제
- [Es et al., RAGAS: Automated Evaluation of Retrieval Augmented Generation (2023, EACL 2024)](https://arxiv.org/abs/2309.15217) — 응답을 진술로 쪼개 근거와 대조하는 방식의 원 논문. 사람 판단과 일치도 faithfulness 0.95
- [RAGAS 문서 — Available metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/) — 검색·생성·범용·에이전트 지표 카탈로그. 지표마다 필요한 정답 필드가 다름
- [RAGAS 문서 — RAG testset generation](https://docs.ragas.io/en/stable/concepts/test_data_generation/rag/) — 문서 → 지식그래프 → 페르소나·시나리오 → single/multi-hop 질문 합성. KG 스터디와 직결
- [RAGAS 문서 — Align LLM-as-judge](https://docs.ragas.io/en/stable/howtos/applications/align-llm-as-judge/) — 사람 라벨 100~200개로 심판 일치율을 먼저 확인. 기본 프롬프트 75.6% → 개선 86.9%
