"""로컬 Ollama 채팅(생성) 호출."""

import json
import urllib.error
import urllib.request

from search_common.embeddings import DEFAULT_OLLAMA_URL


DEFAULT_CHAT_MODEL = "exaone3.5:7.8b"


def chat(
    messages: list[dict],
    model: str = DEFAULT_CHAT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    temperature: float = 0.2,
) -> str:
    payload = json.dumps(
        {"model": model, "messages": messages, "stream": False, "options": {"temperature": temperature}}
    ).encode("utf-8")
    request = urllib.request.Request(f"{ollama_url}/api/chat", data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {ollama_url}/api/chat -> HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"{ollama_url}에 연결할 수 없습니다. `ollama serve`를 확인하세요: {error}") from error
    return result["message"]["content"]
