# Standard RAG Retriever: BM25 + Vector

`Data/Talk_*.txt` 파일을 대상으로 1차 후보군을 넓게 검색한 뒤, BM25와
다국어 dense vector 검색 결과를 **Reciprocal Rank Fusion (RRF)** 으로 합칩니다.
이 디렉터리는 RAG의 `R (Retrieve)` 단계만 담당하며, 결과 JSON의 `text`를
생성 모델의 context로 넘기면 됩니다.

## 실행

```powershell
cd members\sdunge\labs\02-rag-hybrid
python -m pip install -r requirements.txt
python rag_retriever.py "검색할 질문"
```

기본 입력 경로는 `members/sdunge/Data`이며, 다른 위치의 데이터는 다음처럼 지정합니다.

```powershell
python rag_retriever.py "환불 방법이 뭐야?" --data-dir C:\path\to\Data --top-k 8
```

첫 실행 시 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
모델을 다운로드합니다. 네트워크가 제한된 환경에서는 동일 모델을 미리 캐시해야
하며, `--model`로 로컬 모델 경로를 지정할 수 있습니다.

각 결과는 한 줄 JSON으로 출력됩니다.

- `score`: RRF 결합 점수
- `bm25_score`: BM25 원 점수
- `vector_score`: cosine similarity (정규화된 embedding)
- `source`, `text`: 생성 단계에 전달할 근거

`Talk_*.txt`는 빈 줄을 문단 경계로 사용하고, 긴 문단은 `--chunk-size`와
`--overlap`으로 겹쳐 자릅니다. BM25와 벡터 결과 각각 `--candidate-k`개를
후보로 만든 뒤 RRF로 최종 `--top-k`개를 선택합니다.
