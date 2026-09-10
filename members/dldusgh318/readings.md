# 읽을거리

## 2주차 · 검색의 세 세대 (grep → BM25 → 벡터)

- 『Introduction to Information Retrieval』 (Manning, Raghavan, Schütze, Cambridge UP, 2008) Ch.1 불리언 검색 / Ch.6 스코어링·TF-IDF·BM25 — grep의 한계 3가지와 "미리 색인한다"는 아이디어의 출발점
- [Furnas et al., The Vocabulary Problem in Human-System Communication (CACM 1987)](https://dl.acm.org/doi/10.1145/32206.32212) — 두 사람이 같은 대상을 같은 단어로 부를 확률이 20% 미만. 표현 불일치를 처음 정량화한 고전
- [Zhao & Callan, Automatic Term Mismatch Diagnosis for Selective Query Expansion (SIGIR 2012)](https://dl.acm.org/doi/10.1145/2348283.2348405) — 평균적인 쿼리 용어가 관련 문서의 30~40%에 아예 안 나타난다
- [Nori: 공식 Elasticsearch 한국어 분석 플러그인 (Elastic)](https://www.elastic.co/blog/nori-the-official-elasticsearch-plugin-for-korean-language-analysis) — "나라의 말이" 색인 후 "나라"로 검색하면 No Hit. 형태소 분석이 왜 필요한지의 결정적 예시
- [ripgrep is faster than {grep, ag, git grep, ucg, pt, sift} (BurntSushi, 2016)](https://blog.burntsushi.net/ripgrep/) — 스캔을 더 빠르게 만든 것이지 스캔을 없앤 게 아니다. 0세대의 최적화판
- [Malkov & Yashunin, HNSW (2016)](https://arxiv.org/abs/1603.09320) — 2세대 벡터 검색이 정확도를 속도와 맞바꾸는 방식
- [pgvector](https://github.com/pgvector/pgvector) — Postgres에 vector 타입과 HNSW 인덱스를 얹는다. 이번 실습 2세대 저장소
- [BGE-M3 (BAAI, 2024)](https://arxiv.org/abs/2402.03216) — 이번 실습에서 쓰는 임베딩 모델. 다국어·1024차원
