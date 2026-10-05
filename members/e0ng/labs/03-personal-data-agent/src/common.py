import json
import os
import urllib.request
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = LAB_ROOT / "data" / "processed"
DOCUMENTS_PATH = PROCESSED_DIR / "documents.jsonl"


def load_documents(path: Path = DOCUMENTS_PATH) -> list[dict]:
    documents = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                documents.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"JSONL {line_number}행을 읽을 수 없습니다: {error}") from error
    return documents


def get_env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def read_local_setting(name: str, default: str = "") -> str:
    """쉘 환경변수를 우선하고, 없으면 이 랩의 .env에서 읽는다."""
    if os.environ.get(name):
        return os.environ[name]

    path = LAB_ROOT / ".env"
    if not path.exists():
        return default
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == name:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value or default
    return default


def embed(texts: list[str]) -> list[list[float]]:
    base_url = get_env("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model = get_env("EMBEDDING_MODEL", "bge-m3")
    payload = json.dumps({"model": model, "input": texts}).encode()
    request = urllib.request.Request(
        f"{base_url}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["embeddings"]
