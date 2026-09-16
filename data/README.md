# data/

스터디원 각자가 받아온 데이터셋을 두는 곳입니다. **이 폴더는 `README.md` 만 빼고 git 에 올라가지 않습니다.**

컨테이너에 그대로 마운트되어 있어서 파일을 여기 넣으면 바로 DB 에서 읽을 수 있습니다.

| 서비스 | 컨테이너 경로 | 쓰는 법 |
|--------|--------------|---------|
| postgres | `/data` | `COPY t FROM '/data/<id>/x.csv' CSV HEADER;` |
| neo4j | `/import` | `LOAD CSV WITH HEADERS FROM 'file:///<id>/x.csv' AS row ...` |
| elasticsearch | (마운트 없음) | Python/curl 로 `_bulk` 적재 |

## 권장 구조

```
data/
├── README.md
└── <github-id>/          # 본인 아이디 폴더 아래에 두면 서로 안 섞임
    ├── raw/              # 원본 (다운로드 그대로)
    └── processed/        # 청킹·정제 결과
```

## 원본을 다시 받을 수 있게

용량 큰 원본은 커밋하지 않는 대신, 실습 README 나 `labs/NN-topic/src/download.sh` 에
다운로드 명령(URL, `huggingface-cli download ...`, `kaggle datasets download ...` 등)을 적어 두세요.
