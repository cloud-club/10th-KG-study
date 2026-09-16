import json
import os
import urllib.request
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = LAB_ROOT / "data" / "processed"
JSON_PATH = PROCESSED_DIR / "chat.json"
TSV_PATH = PROCESSED_DIR / "chat.tsv"


def load_messages(path: Path = JSON_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def get_env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def embed(texts: list[str]) -> list[list[float]]:
    base_url = get_env("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model = get_env("EMBEDDING_MODEL", "bge-m3")
    payload = json.dumps({"model": model, "input": texts}).encode()
    request = urllib.request.Request(
        f"{base_url}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)["embeddings"]
