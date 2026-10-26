# 개인 지식그래프 MCP 서버

Claude Code나 Claude 데스크톱 대화에서 "내 Redis 경험 정리해줘", "장애 대응 사례 보여줘" 같은 질문에
AI가 이 실습의 그래프·검색 인덱스를 직접 조회하게 하는 로컬 MCP 서버다.

- 코드: `src/mcp_server.py`(MCP 등록) + `src/kg_tools.py`(도구 로직)
- 테스트: `.venv/bin/python -m unittest tests/test_kg_tools.py` (DB 없이 돈다)

## 설계 원칙

| 원칙 | 구현 |
|---|---|
| 서버는 LLM을 부르지 않는다 | OpenAI 호출 경로 없음. Text2Cypher도 서버가 만들지 않고, `get_graph_schema`를 받은 AI가 Cypher를 직접 쓴다 |
| 모든 결과에 근거 | 결과마다 `chunk_id` · `document`(노션 문서 경로) · `heading` · `evidence` · `source_tier` |
| 읽기 전용 | Postgres는 `READ ONLY` 트랜잭션, Neo4j는 `READ_ACCESS` 세션 + `execute_read`. 쓰기 도구 없음 |
| 로컬 stdio | 네트워크 포트를 열지 않는다. 임베딩 모델은 `HF_HUB_OFFLINE=1`로 로컬 캐시만 쓴다 |
| 그래프는 1차 문서만 | 엣지의 `source_tier != 'secondary'`만 사용. 문서 검색은 전체 코퍼스 + 결과마다 tier 표시 |

> ⚠️ **"원문이 외부로 나가지 않는다"의 범위**: 서버 자체는 외부로 아무것도 보내지 않는다. 하지만 도구 결과는
> 대화 중인 AI(Claude)에게 전달되므로, 결과에 담긴 원문 일부(검색 600자, 그래프 회수 900자, evidence 300자)는
> 그 대화와 함께 Anthropic으로 간다. 길이 상한은 `kg_tools.py` 맨 위 상수로 조절한다.

## 도구

질문 모양별 선택 기준은 6·7주차 평가 결과(`results/w6_compare.md`, `results/week7_eval_compare.md`)를 따른다.

| 도구 | 언제 | 재사용한 코드 | 평가 근거 |
|---|---|---|---|
| `search_documents(query, top_k=5)` | 설명·과정·경험 서술 | `hybrid_search.hybrid_search` (BM25 top-50 + 벡터 top-50 → RRF k=60) | S01·M01: v1 correct |
| `explore_graph(query, top_k=5)` | 두 대상 사이 관계 | `graph_retriever.expand` + `assemble_v2`, 회수 순서는 `run_v21_x01.rank_candidates` | X01·X03: 7주차 전체 그래프에서 세 방식 모두 wrong → **교차 확인 필수** |
| `technology_experience(technology)` | 특정 기술의 프로젝트별 사용 | 새 SQL (그래프 테이블 직접 조회) | — |
| `list_issues(project, technology)` | 장애·트러블슈팅 사례 | 새 SQL | H01: 검색 partial, Cypher 0행 |
| `proposed_only(project)` | 과장 점검 ("써봤다고 하면 안 되는 목록") | 새 SQL | T02(Redis 제안만) |
| `get_graph_schema()` | `run_cypher` 전에 | 실제 Neo4j 집계 + `text2cypher.FEW_SHOTS` | — |
| `run_cypher(query)` | 개수·순위·상태 조건 | `text2cypher.guard` + `text2cypher.execute` | A1·A2: Cypher만 correct |

### 기존 코드와 다른 점

- **1차 문서 필터**: `graph_retriever.load_graph()`는 tier를 거르지 않는다. 서버는 같은 모양으로 읽되
  `WHERE source_tier IS DISTINCT FROM 'secondary'`를 건 `kg_tools.load_primary_graph()`를 쓴다.
  확장 알고리즘(`expand`, 이웃 20개 초과 노드 확장 중단)과 조립(`assemble_v2`, 5,000/800/2,200자 예산)은 그대로다.
- **v2.1 차수 기준**: 현재 `expand`의 차수는 노드의 서로 다른 이웃 IRI 수(Project 포함)다. Project만 따로 세는
  변형은 코드에 없어서 서버도 기존 방식을 그대로 쓴다.
- **기술 별칭**: 코드에 별칭표가 없어서(`extract_triples.py`의 추출 프롬프트 예시뿐) `kg_tools.TECH_ALIASES`를
  새로 뒀다. 한글 표기 → DB 라벨 매핑이고, DB에 라벨이 없으면 정규화 실패로 돌려준다(추측 안 함).
  DB에 `prometheus`와 `프로메테우스`가 별도 노드로 있어 둘 다 묶어 돌려준다. `redis`를 물으면
  `spring data redis` 같은 노드는 합치지 않고 `related_not_merged`로만 알린다.
- **`run_cypher`의 tier**: AI가 쓴 Cypher를 서버가 고치지 않는다. 대신 쿼리에 `source_tier` 조건이 없으면
  결과에 "2차 문서가 섞였을 수 있음"을 붙인다.
- **보안 검사 함정**: `text2cypher.guard`는 단어 단위·대소문자 무시라 `AS use` 같은 별칭도 막는다.
  `get_graph_schema`의 notes에 적어 AI가 피하게 했다.

### 데이터 위치 (활성 런타임 기준)

`data/processed/active_corpus.json`을 따른다. 현재 `run=v1-full-inc1`.

| 대상 | 위치 |
|---|---|
| 그래프 테이블 | Postgres `localhost:5433`, 스키마 `kg_v1_full_inc1` (`entities`, `edges`) |
| 벡터 | `kg_v1_full_inc1.search_vectors` (bge-m3, 1024차원) |
| BM25 | Elasticsearch `localhost:9200`, 인덱스 `notion-gen1` |
| Neo4j | `bolt://localhost:7689` (브라우저 `localhost:7476`), 컨테이너 `kg-neo4j-v1-inc1` |

> 서버는 **활성 런타임의 `neo4j_uri`를 우선**한다. `.env`의 `OLD_NEO4J_URI`(7687)는 v0 그래프용이라 서버가 읽지 않는다.
> 다른 그래프를 보려면 환경변수 `KG_NEO4J_URI`로 덮어쓴다. 비밀번호는 `.env`의 `NEO4J_PASSWORD`에서 읽는다.

> **한계**: 새로 클론하면 gitignore된 `data/`·`output/`(활성 런타임 설정·코퍼스·별칭)이 없어서, 서버는 옛 `public` 테이블(`notion_gen2`, `entities`, `edges`)로 동작한다.

## 설치

```bash
cd members/dldusgh318/labs/01-three-generations
.venv/bin/python -m pip install -r requirements.txt     # mcp 패키지 추가됨
docker start gen1-es gen2-pgvector kg-neo4j-v1-inc1
.venv/bin/python -m unittest tests/test_kg_tools.py
```

임베딩 모델 `BAAI/bge-m3`는 이미 로컬 캐시에 있어야 한다(오프라인 모드라 서버가 받지 않는다).
첫 검색은 모델 로딩 때문에 10초 안팎 걸린다. 서버가 시작하면서 백그라운드로 미리 올린다.

## Claude Code에 등록

이 디렉터리의 `.mcp.json`이 프로젝트 범위 설정이다. 경로가 상대경로라 **이 디렉터리에서 `claude`를 실행**해야 한다.

```bash
cd members/dldusgh318/labs/01-three-generations
claude
```

처음 실행하면 프로젝트 MCP 서버 승인을 묻는다. `/mcp`로 `my-kg` 연결 상태와 도구 7개를 확인한다.

다른 디렉터리에서도 쓰려면 사용자 범위로 절대경로 등록한다 (`<LAB>` = 이 디렉터리의 절대경로):

```bash
claude mcp add my-kg --scope user -- <LAB>/.venv/bin/python <LAB>/src/mcp_server.py
```

## Claude 데스크톱 앱에 등록

macOS 설정 파일 `~/Library/Application Support/Claude/claude_desktop_config.json`
(앱의 설정 → 개발자 → 설정 편집으로도 열린다)에 추가하고 앱을 재시작한다.
데스크톱 앱은 작업 디렉터리가 정해져 있지 않으므로 **반드시 절대경로**를 쓴다.

```json
{
  "mcpServers": {
    "my-kg": {
      "command": "<LAB>/.venv/bin/python",
      "args": ["<LAB>/src/mcp_server.py"]
    }
  }
}
```

비밀번호는 여기 적지 않는다. 서버가 `<LAB>/.env`를 직접 읽는다.

## 써볼 질문

| 질문 | 예상 도구 |
|---|---|
| 내 Redis 경험 정리해줘 | `technology_experience` → 필요하면 `search_documents` |
| 장애 대응 사례 보여줘 | `list_issues` → 서술 보강은 `search_documents` |
| 포트폴리오에 '써봤다'고 쓰면 안 되는 기술은? | `proposed_only` |
| 가장 많은 프로젝트에서 쓴 기술은? | `get_graph_schema` → `run_cypher` |
| SeCause 작업 큐에 쓴 기술을 다른 프로젝트에서도 썼어? | `explore_graph` + 교차 확인 |

## 문제 해결

| 증상 | 원인 / 조치 |
|---|---|
| `/mcp`에 failed | 터미널에서 `.venv/bin/python src/mcp_server.py`를 직접 실행해 stderr 확인 |
| `ModuleNotFoundError: mcp` | `pip install -r requirements.txt`를 `.venv`에서 안 했음 |
| 도구 결과 `ok: false`, 연결 오류 | 컨테이너 3개(gen1-es, gen2-pgvector, kg-neo4j-v1-inc1) 확인 |
| 임베딩 모델 로드 실패 | 캐시에 bge-m3 없음. 오프라인 모드라 자동으로 받지 않는다 |
| `run_cypher`가 읽기 쿼리를 막음 | 별칭에 예약어(`use`, `set`, `load` …)를 썼는지 확인 |
