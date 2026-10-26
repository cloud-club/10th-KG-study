"""개인 지식그래프 MCP 서버 — 로컬 stdio, 읽기 전용, LLM 호출 없음.

    .venv/bin/python src/mcp_server.py        # 보통은 Claude Code / Claude 데스크톱이 직접 띄운다

도구 로직은 kg_tools.py에 있고 여기서는 MCP에 등록만 한다. 설명은 MCP_SERVER.md 참고.
"""
import io
import logging
import os
import sys
import threading
from pathlib import Path

# stdout은 MCP JSON-RPC 전용이다. 기존 모듈의 print()와 라이브러리 진행바가 섞이면 프로토콜이 깨지므로
# 진짜 stdout은 복제해 MCP에만 넘기고, fd 1은 stderr로 돌린다. 다른 import보다 먼저 해야 한다.
_MCP_STDOUT = os.fdopen(os.dup(1), "wb")
os.dup2(2, 1)
sys.stdout = sys.stderr

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="[my-kg] %(levelname)s %(message)s")

import anyio  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

import kg_tools as kg  # noqa: E402

# gen2_pgvector.embedder()는 락 없이 전역 모델을 만든다. 사전 로딩 스레드와 첫 검색이 동시에 부르면
# 두 스레드가 모델을 동시에 초기화하다 깨지므로(meta tensor 오류) 로딩을 한 번에 하나로 묶는다.
_EMBED_LOCK = threading.Lock()


def _ensure_embedder() -> None:
    with _EMBED_LOCK:
        from gen2_pgvector import embedder
        embedder()


READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

mcp = FastMCP(
    "my-kg",
    instructions=(
        "연호의 개인 노션 기록으로 만든 지식그래프·검색 서버다. 도구는 데이터와 근거만 돌려준다. "
        "답할 때는 도구 결과에 있는 사실만 쓰고, 주요 주장마다 chunk_id와 문서 경로를 근거로 붙인다. "
        "결과에 없는 내용은 추측하지 말고 '기록에서 찾지 못했다'고 말한다. "
        "질문 모양으로 도구를 고른다: 설명·과정 → search_documents, 두 대상 사이 관계 → explore_graph, "
        "개수·순위·상태 조건 → get_graph_schema 후 run_cypher, 특정 기술 → technology_experience, "
        "장애 사례 → list_issues, 과장 점검 → proposed_only. "
        "그래프 도구는 1차 문서 근거만 쓴다. status=proposed는 '구현했다'고 말하면 안 된다."
    ),
)


def _call(fn, *args, **kwargs) -> dict:
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:   # 입력·정규화 문제는 AI가 고쳐서 다시 부를 수 있게 그대로 알린다
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001  DB 연결 등. 접속 비밀번호는 메시지에 포함되지 않는다
        logging.exception("tool failed: %s", fn.__name__)
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "hint": "docker 컨테이너(gen1-es, gen2-pgvector, kg-neo4j-v1-inc1)가 떠 있는지 확인"}


@mcp.tool(annotations=READ_ONLY, description=(
    "설명·과정·경험 서술 질문에 먼저 쓴다 (예: '내 Redis 경험 정리해줘', '배포 파이프라인 어떻게 했지?'). "
    "BM25(nori)+벡터(bge-m3)를 RRF로 합친 기존 v1 검색으로 청크를 찾아 chunk_id·문서 경로·원문 일부를 준다. "
    "7주차 평가에서 설명형 질문(S01·M01)은 이 방식이 맞혔다. 개수·목록 집계는 약하다(A1·A2 실패) → run_cypher. "
    "전체 코퍼스 대상이며 결과마다 source_tier(primary/secondary)를 표시한다."))
def search_documents(query: str, top_k: int = 5) -> dict:
    _ensure_embedder()
    return _call(kg.search_documents, query, top_k)


@mcp.tool(annotations=READ_ONLY, description=(
    "두 대상 사이 관계 질문에 쓴다 (예: 'A 프로젝트에서 X 용도로 쓴 기술을 B에서도 썼나?'). "
    "기존 v2.1: v1 검색 top-k 청크의 엣지로 그래프에 진입해 같은 기술을 쓴 다른 사용례까지 2홉 확장하고, "
    "그래프 사실과 회수 원문(chunk_id·문서 경로)을 준다. 그래프는 1차 문서 근거만. "
    "주의: 7주차 1,925청크 평가에서 교차 질문 X01·X03은 v1·v2.1·Cypher 모두 wrong이었다. "
    "결과를 확정 답으로 쓰지 말고 search_documents·technology_experience로 교차 확인할 것."))
def explore_graph(query: str, top_k: int = 5) -> dict:
    _ensure_embedder()
    return _call(kg.explore_graph, query, top_k)


@mcp.tool(annotations=READ_ONLY, description=(
    "특정 기술 하나를 프로젝트별로 어떻게 썼는지 볼 때 쓴다 (예: 'Redis 어디에 썼어?'). "
    "redis/Redis/레디스 같은 별칭을 kg:tech-redis로 정규화한 뒤 프로젝트별 사용례의 purpose·status·근거를 준다. "
    "정확히 맞는 노드가 없으면 추측하지 않고 related_not_merged 후보만 알린다. 1차 문서 근거만. "
    "status=proposed는 써봤다고 말하면 안 되고, '상태 미기재'는 구현 여부를 모르는 것이다."))
def technology_experience(technology: str) -> dict:
    return _call(kg.technology_experience, technology)


@mcp.tool(annotations=READ_ONLY, description=(
    "장애·트러블슈팅 사례 질문에 쓴다 (예: '장애 대응 사례 보여줘', 'Redis 쓰다 생긴 문제'). "
    "Issue별 원인·해결·검증과 발생한 사용례(프로젝트·기술), 근거를 준다. project(SeCause/팀피셜/직행/청바지/모앤디)나 "
    "technology로 거를 수 있다. 빈 항목은 문서에 명시되지 않은 것이니 채워 넣지 말 것. "
    "7주차 H01(장애 원인·수정)은 검색이 부분 정답, Cypher는 0행이었다 → 서술이 더 필요하면 search_documents도 함께."))
def list_issues(project: str | None = None, technology: str | None = None) -> dict:
    return _call(kg.list_issues, project, technology)


@mcp.tool(annotations=READ_ONLY, description=(
    "'써봤다고 하면 안 되는 목록'을 볼 때 쓴다. status=proposed(제안·검토만)인 사용례와 근거를 준다. "
    "포트폴리오·면접 답변을 쓰기 전 과장 점검용. project로 거를 수 있다. 같은 기술을 다른 사용례에서 "
    "구현했을 수 있으니 same_technology_implemented_in을 보고 기술 전체를 '안 써봤다'로 일반화하지 말 것."))
def proposed_only(project: str | None = None) -> dict:
    return _call(kg.proposed_only, project)


@mcp.tool(annotations=READ_ONLY, description=(
    "run_cypher를 쓰기 전에 반드시 먼저 호출한다. Neo4j 그래프의 라벨·관계 방향·속성(값이 있는 개수)·"
    "실제 값(프로젝트 id와 한글 이름, status 분포, 자주 쓰인 기술 id)·작성 주의사항·검증된 예시 쿼리를 준다."))
def get_graph_schema() -> dict:
    return _call(kg.get_graph_schema)


@mcp.tool(annotations=READ_ONLY, description=(
    "개수·순위·상태 조건 질문에 쓴다 (예: '가장 많은 프로젝트에서 쓴 기술은?', '제안만 한 기술은 몇 종류?'). "
    "get_graph_schema를 본 뒤 Cypher를 직접 작성해 실행한다. 7주차 평가에서 집계형 질문(A1·A2)은 이 방식만 맞혔다. "
    "읽기 전용: 정적 검사(쓰기·CALL·APOC·LOAD CSV·주석·다중 문장 차단) → EXPLAIN으로 읽기 쿼리 확인 → "
    "execute_read, 10초 제한, 최대 200행. 0건은 '없다'가 아니라 '이 조건으로 0건'이며 쿼리와 함께 돌려준다. "
    "1차 문서만 보려면 관계마다 coalesce(r.source_tier,'primary') <> 'secondary'를 건다."))
def run_cypher(query: str) -> dict:
    return _call(kg.run_cypher, query)


def _warmup() -> None:
    """임베딩 모델(로컬 캐시)을 미리 올려 첫 검색 지연을 줄인다. 실패해도 첫 호출 때 다시 시도된다."""
    try:
        _ensure_embedder()
    except Exception:  # noqa: BLE001
        logging.warning("임베딩 모델 사전 로딩 실패 — 첫 검색 때 다시 시도", exc_info=True)


async def _serve() -> None:
    stdout = anyio.wrap_file(io.TextIOWrapper(_MCP_STDOUT, encoding="utf-8"))
    async with stdio_server(stdout=stdout) as (read_stream, write_stream):
        server = mcp._mcp_server   # FastMCP.run_stdio_async와 같은 동작. stdout만 위에서 떼어둔 것으로 바꿨다
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    threading.Thread(target=_warmup, daemon=True).start()
    anyio.run(_serve)


if __name__ == "__main__":
    main()
