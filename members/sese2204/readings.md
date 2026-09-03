# 읽을거리

## 1주차 · 고전 RAG 훑기

- [Lewis et al., Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks (2020)](https://arxiv.org/abs/2005.11401) — RAG라는 이름의 출발점. 검색기+생성기 결합의 원형
- [Karpukhin et al., Dense Passage Retrieval (2020)](https://arxiv.org/abs/2004.04906) — BM25를 dense 검색이 처음 제대로 이긴 논문
- [Thakur et al., BEIR (2021)](https://arxiv.org/abs/2104.08663) — 도메인 밖에서는 dense가 BM25에 지기도 한다는 걸 보여준 벤치마크
- [Khattab & Zaharia, ColBERT (2020)](https://arxiv.org/abs/2004.12832) — late interaction. 리랭커와 bi-encoder 사이의 절충
- [Gao et al., RAG for LLMs: A Survey (2023)](https://arxiv.org/abs/2312.10997) — Naive → Advanced → Modular RAG 흐름을 한 번에 보는 서베이
- [Anthropic, Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) — 청크마다 문서 맥락을 앞에 붙여 검색 실패율을 줄이는 방법
- [Jina, Late Chunking](https://jina.ai/news/late-chunking-in-long-context-embedding-models/) — 임베딩 먼저, 청킹 나중에
- 『AI 에이전트 엔지니어링』 (마이클 알바다 저 / 강민혁 역, 한빛미디어, 2026.01) — RAG 변천사 장을 참고
- [zg(zvec-grep) — 키워드를 넘어서는 로컬 검색 인프라 (GeekNews)](https://news.hada.io/topic?id=33183) — Qwen 팀의 ripgrep 확장. 벡터 + BM25 하이브리드를 RRF로 합치고 16M 온디바이스 임베딩으로 코드·문서를 의미 검색. 하이브리드 검색 노트의 실전 사례
