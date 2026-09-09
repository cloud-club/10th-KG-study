## Grep vs BM25 vs Vector Search

> 자원 사용량, 정확도, 속도를 기반으로 확인



| Grep | BM25 | Vector Search |
|---|---|---|
| 동일한 문자열 | 가까운 문자열 | 유의미한 문자열 |


## 실습
> 정답을 만들어 놓고, 얼마나 목적에 맞게 문자열을 찾을 수 있는지 확인
> 목적 : 자원 사용량↓ , 정확도↑, 속도↑


                 카카오톡 원본
                      │
                      ▼
             prepare_dataset.py (대화 단위 Chunking)
              > Gap Hours : 4      #4시간 단위 (4시간 동안 말이 없다면 다른 주제일 확률 ↑) 
              > Max Message : 30   #30개의 대화 메시지로 Cuunking
              > OverLap : # 5      #경계 구분
                      │
                      ▼
             documents.jsonl (753개 chunk 생성)
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
        GREP        BM25       Vector
          │           │           │
       Python      Elasticsearch  pgvector
       문자열       단어 기반       의미 기반
       검색          검색           검색
          │           │           │
          └───────────┼───────────┘
                      ▼
                 benchmark.py
                      │
                정답과 비교
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       Hit@1       Hit@5      Precision/Recall
                      │
                      ▼
                 CSV 결과

##결과
| 검색 방식  |                         평균 검색시간 | Hit@1 | Hit@5 |
| ------ | ------------------------------: | ----: | ----: |
| GREP   |                         4.37 ms |    0% |    0% |
| BM25   |                         7.07 ms |   30% |   45% |
| Vector | DB 3.21 ms + embedding 20.46 ms |  2.5% |  2.5% |


