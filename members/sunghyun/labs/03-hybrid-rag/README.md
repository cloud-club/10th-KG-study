---
title: 3주차 - 하이브리드 검색, RAG와 Recall 평가
date: 2026-10-01
tags: [rag, hybrid-search, rrf, recall]
status: done
---

# 03. 하이브리드 검색, RAG와 Recall 평가

관련 노트: [3주차 실습과 결과](../../notes/03-hybrid-rag-and-evaluation.md).
[2주차 실습](../02-search-lab/README.md)의 청크 생성, 전체 임베딩, Elasticsearch·pgvector 적재와 HNSW 인덱스 준비를 마친 뒤 실행한다. 저장소 루트에서 `cd members/sunghyun/labs/03-hybrid-rag`로 이동한다. 검색 모듈과 입력 데이터는 2주차 폴더를 재사용하고, 3주차 실행 결과는 이 폴더의 `src/outputs/`에 저장한다.

| 코드 | 역할 |
|---|---|
| [05_hybrid_rrf.py](src/05_hybrid_rrf.py) | BM25·벡터 후보를 chunk_id 기준 RRF로 결합 |
| [06_rag_answer.py](src/06_rag_answer.py) | 지정한 청크 ID의 본문·출처로 답변 생성 |
| [07_hybrid_rag.py](src/07_hybrid_rag.py) | 질문 하나로 검색·RRF·컨텍스트·LLM 답변 연결 |
| [08_evaluate_recall.py](src/08_evaluate_recall.py) | Q1~Q6의 고정 정답 청크로 세 검색 방식 평가 |

```bash
# HNSW 후보 검색과 RRF Top-5 확인
python3 src/05_hybrid_rrf.py \
  --query 'URM 서버 등록하는 방법' \
  --operator or --mode hnsw --candidates 20 --top-k 5

# 선택한 청크 본문으로 컨텍스트 조립만 확인
python3 src/06_rag_answer.py \
  --query 'URX에서 서로 다른 ALM에 아이템 어떻게 보내?' \
  --chunk-id '<실제 청크 ID>' --preview

# 로컬 답변 모델 준비 후 통합 흐름 실행
ollama pull qwen2.5:7b
python3 src/07_hybrid_rag.py --mode local \
  --query 'URX에서 서로 다른 ALM에 아이템 어떻게 보내?'

# OPENROUTER_API_KEY 환경변수를 설정한 터미널에서 실행
python3 src/07_hybrid_rag.py --mode openrouter \
  --query 'URX에서 서로 다른 ALM에 아이템 어떻게 보내? 그리고 CB가 뭐야?'

# LLM 호출 없이 BM25/HNSW/RRF Recall 비교
python3 src/08_evaluate_recall.py --ks 1 3 5 10
python3 src/08_evaluate_recall.py --question Q6 --ks 1 3 5 10
```

07의 기본값은 BM25 OR, HNSW, 후보 각 20개, 최종 Top-5다. 기존 2주차 BM25 단독 실습의 기본 AND와 구분한다. `--preview`는 07에서도 사용할 수 있으며 답변 모델 호출을 생략한다. OpenRouter 모드는 질문과 선택된 본문·출처를 API로 전송하므로 전송 가능한 자료로 실행한다.

05·07·08의 기본 캐시는 실습 당시 `../02-search-lab/src/outputs/vectors_qwen3_2685.json`이다. 다른 캐시는 세 명령에 `--cache ../02-search-lab/src/outputs/vectors_qwen3_<실제 청크 수>.json`을 지정한다. 08의 청크 파일도 다르면 `--input <청크 파일>`을 지정한다. 코드의 `CACHE` 상수를 수정할 필요는 없다. 08의 `CASES`에는 이번 비공개 데이터의 정답 청크 ID만 들어 있다. 다른 데이터로 실행하려면 원문을 읽고 질문과 정답 ID를 바꿔야 하며, 임의의 데이터에서는 그대로 재현되지 않는다.

인용 번호 검사는 번호 범위만 검사한다. 문장과 근거가 일치하는지는 직접 확인한다. 결과 JSON/CSV, 원문·임베딩 캐시, API 키는 업로드하지 않는다.

## 결과와 다음 단계

답변 예시와 Recall 평가 결과는 [3주차 노트](../../notes/03-hybrid-rag-and-evaluation.md)에 기록했다. 비공개 데이터의 정답셋을 사용하므로 다른 데이터에는 질문과 정답 ID를 맞춰야 한다. 관계 질문은 [4주차 지식 그래프 학습](../04-knowledge-graph/README.md)으로 이어간다.
