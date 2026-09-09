# 로컬 인프라 (Docker Compose)

스터디 실습에 쓰는 DB 세 개를 한 번에 띄웁니다. 각자 자기 노트북에서 돌리고, 데이터는 도커 볼륨에 남습니다.

| 서비스 | 이미지 | 접속 | 용도 |
|--------|--------|------|------|
| PostgreSQL 17 + **pgvector** | `pgvector/pgvector:pg17` | `postgresql://kg:kg@localhost:5432/kg` | 청크·메타데이터·임베딩 저장, 벡터 검색 |
| Elasticsearch 9 + **nori** | `infra/elasticsearch/Dockerfile` | `http://localhost:9200` (인증 없음) | BM25 / 하이브리드 검색, 한국어 형태소 분석 |
| Neo4j 5.26 LTS + **APOC** | `neo4j:5.26-community` | `bolt://localhost:7687`, Browser `http://localhost:7474` (neo4j / kgstudy2026) | 지식그래프 저장·탐색 |
| Kibana (선택) | `kibana:9.1.0` | `http://localhost:5601` | ES 인덱스 탐색 |

## 준비물

- Docker Desktop (Mac/Windows) 또는 Docker Engine + Compose v2 (Linux)
- 메모리 여유 **4GB 이상** 권장 (ES 1GB + Neo4j 1.5GB + PG). Docker Desktop → Settings → Resources 에서 확인.

## 시작하기

```bash
git pull
cp .env.example .env          # 비밀번호·포트 바꾸고 싶으면 수정. 그대로 둬도 됨
docker compose up -d          # 최초 실행은 이미지 다운로드 + ES 플러그인 빌드로 몇 분 걸림
bash infra/check.sh           # 세 서비스 확인 (pgvector 연산, nori 토큰화, APOC 버전)
```

`check.sh` 가 "모두 정상입니다" 를 찍으면 끝입니다. Windows 는 Git Bash 나 WSL 에서 실행하세요.

Kibana 까지 띄우려면:

```bash
docker compose --profile ui up -d
```

## 자주 쓰는 명령

```bash
docker compose ps                      # 상태
docker compose logs -f neo4j           # 로그 (postgres / elasticsearch / neo4j)
docker compose stop                    # 잠깐 멈춤
docker compose down                    # 컨테이너 제거, 데이터는 볼륨에 유지
docker compose down -v                 # 데이터까지 초기화 (되돌릴 수 없음)
docker compose up -d --build           # .env 의 ES_VERSION 바꾼 뒤 재빌드
```

## 접속하기

```bash
# PostgreSQL
docker compose exec postgres psql -U kg -d kg
# Neo4j
docker compose exec neo4j cypher-shell -u neo4j -p kgstudy2026
# Elasticsearch
curl localhost:9200/_cat/indices?v
```

Python 에서:

```python
import os
from dotenv import load_dotenv; load_dotenv()      # 레포 루트의 .env 를 그대로 씀

# pip install psycopg[binary] pgvector
import psycopg
pg = psycopg.connect(f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@localhost:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}")

# pip install elasticsearch
from elasticsearch import Elasticsearch
es = Elasticsearch(f"http://localhost:{os.environ['ES_PORT']}")

# pip install neo4j
from neo4j import GraphDatabase
neo = GraphDatabase.driver(f"bolt://localhost:{os.environ['NEO4J_BOLT_PORT']}", auth=("neo4j", os.environ["NEO4J_PASSWORD"]))
```

## 데이터 넣기

레포 루트의 `data/` 폴더가 컨테이너에 마운트되어 있습니다. 자세한 건 [`data/README.md`](../data/README.md).

```sql
-- postgres: data/<id>/docs.csv →  /data/<id>/docs.csv
COPY docs(id, title, body) FROM '/data/<id>/docs.csv' CSV HEADER;
```

```cypher
// neo4j: data/<id>/edges.csv →  file:///<id>/edges.csv
LOAD CSV WITH HEADERS FROM 'file:///<id>/edges.csv' AS r
MERGE (a:Entity {name: r.head}) MERGE (b:Entity {name: r.tail})
MERGE (a)-[:REL {type: r.relation}]->(b);
```

## 설정 바꾸기

- 포트 충돌: `.env` 의 `*_PORT` 를 바꾸고 `docker compose up -d`.
- ES 메모리: `.env` 의 `ES_JAVA_OPTS`. 노트북 메모리가 8GB 면 `-Xms512m -Xmx512m` 로.
- Neo4j GDS(그래프 알고리즘) 도 필요하면 `.env` 에 `NEO4J_PLUGINS=["apoc","graph-data-science"]` 후 `docker compose up -d --force-recreate neo4j`.
- pgvector 외 확장이 더 필요하면 `infra/postgres/init/01-extensions.sql` 에 추가. 이미 만들어진 볼륨에는 자동 적용되지 않으니 psql 에서 직접 `CREATE EXTENSION` 하거나 `down -v` 후 다시 올리세요.

## 문제 해결

- **ES 가 계속 재시작** → 메모리 부족. `docker compose logs elasticsearch` 에 `OutOfMemory` 가 보이면 `ES_JAVA_OPTS` 를 줄이거나 Docker 메모리 한도를 올리세요. Linux 는 `sudo sysctl -w vm.max_map_count=262144` 도 필요합니다.
- **Neo4j 비밀번호 오류** → 볼륨에 이전 비밀번호가 남아 있는 상태. `.env` 를 원래대로 돌리거나 `docker compose down -v`.
- **`port is already allocated`** → 로컬에 이미 PG/ES/Neo4j 가 돌고 있음. `.env` 에서 포트 변경.
- **M1/M2 Mac** → 세 이미지 모두 arm64 지원. 별도 설정 없음.
- **pg_trgm 이 한글에 안 먹힘** (`select show_trgm('한글')` 이 `{}`) → DB 가 순수 `C` 로케일로 만들어진 것. `select datctype from pg_database where datname='kg'` 가 `C.UTF-8` 이어야 합니다. 예전 볼륨이면 `docker compose down -v` 후 다시 올리세요 (데이터 초기화됨).
