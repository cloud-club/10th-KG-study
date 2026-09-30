"""이 랩의 공용 설정: 레포 루트 공용 인프라(.env) 로드, 3~4주차 청크 로드, OpenAI 호출."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

LAB_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = LAB_ROOT.parents[3]
load_dotenv(REPO_ROOT / ".env")

# 3~4주차 실습(03-04-personal-data-agent)에서 이미 적재한 청크를 그대로 재사용한다.
CHUNKS_PATH = REPO_ROOT / "members" / "e0ng" / "labs" / "03-04-personal-data-agent" / "data" / "processed" / "documents.jsonl"

API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4.1-mini"


def get_env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def postgres_dsn() -> str:
    user = get_env("POSTGRES_USER", "kg")
    password = get_env("POSTGRES_PASSWORD", "kg")
    port = get_env("POSTGRES_PORT", "5432")
    db = get_env("POSTGRES_DB", "kg")
    return f"postgresql://{user}:{password}@localhost:{port}/{db}"


def neo4j_uri() -> str:
    return f"bolt://localhost:{get_env('NEO4J_BOLT_PORT', '7687')}"


def neo4j_auth() -> tuple[str, str]:
    return ("neo4j", get_env("NEO4J_PASSWORD", "kgstudy2026"))


def load_documents(path: Path = CHUNKS_PATH) -> list[dict]:
    if not path.exists():
        raise SystemExit(
            f"{path} 가 없습니다. 03-04-personal-data-agent 랩에서 "
            "parse_export.py를 먼저 돌려 청크를 만들어야 합니다."
        )
    documents = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                documents.append(json.loads(line))
    return documents


def _extract_text(payload: dict) -> str:
    parts = [
        part["text"]
        for item in payload.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") == "output_text" and part.get("text")
    ]
    text = "\n".join(parts).strip()
    if not text:
        raise RuntimeError("OpenAI API가 텍스트 응답을 반환하지 않았습니다.")
    return text


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()


def call_openai_json(instructions: str, input_text: str, api_key: str, model: str, max_output_tokens: int = 2000):
    payload = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
        "max_output_tokens": max_output_tokens,
        "store": False,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        try:
            detail = json.load(error).get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detail = ""
        raise RuntimeError(f"OpenAI API 오류 ({error.code}): {detail or error.reason}") from error

    text = _strip_code_fence(_extract_text(body))
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"OpenAI 응답이 JSON이 아닙니다: {text[:200]}") from error
