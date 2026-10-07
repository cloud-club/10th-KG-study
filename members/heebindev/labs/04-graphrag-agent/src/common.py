import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


LAB_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = LAB_DIR.parents[3]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def neo4j_query(cypher: str, parameters: dict | None = None) -> list[dict]:
    load_env_file(REPO_ROOT / ".env")
    url = os.getenv(
        "NEO4J_HTTP_URL",
        "http://127.0.0.1:7474/db/neo4j/tx/commit",
    )
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "kgstudy2026")
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    body = json.dumps(
        {"statements": [{"statement": cypher, "parameters": parameters or {}}]}
    ).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Neo4j에 연결하지 못했습니다. 저장소 루트에서 "
            "`docker compose up -d neo4j`를 먼저 실행해 주세요."
        ) from exc

    if payload.get("errors"):
        message = payload["errors"][0].get("message", "알 수 없는 Neo4j 오류")
        raise RuntimeError(f"Neo4j 질의 실패: {message}")

    result = payload.get("results", [{}])[0]
    columns = result.get("columns", [])
    return [dict(zip(columns, item.get("row", []))) for item in result.get("data", [])]


def openai_response(payload: dict) -> dict:
    load_env_file(REPO_ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("저장소 루트의 .env에 OPENAI_API_KEY를 넣어 주세요.")

    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"OpenAI API 호출 실패 ({exc.code}): {detail}") from exc


def response_text(response: dict) -> str:
    texts = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                texts.append(content.get("text", ""))
    text = "\n".join(texts).strip()
    if not text:
        raise RuntimeError(f"응답에 본문이 없습니다. 상태: {response.get('status')}")
    return text
