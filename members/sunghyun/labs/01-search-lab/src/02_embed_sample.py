#!/usr/bin/env python3
"""Week 2: embed only three existing chunks using local Ollama.

Standard library only. Does not edit the input or save vectors.
Document bodies are sent only to the fixed loopback endpoint, not printed.
API reference: https://docs.ollama.com/api/embed
Model: https://ollama.com/library/qwen3-embedding:0.6b
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MODEL = "qwen3-embedding:0.6b"
ENDPOINT = "http://127.0.0.1:11434/api/embed"
SAMPLE_SIZE = 3


class NoRedirect(HTTPRedirectHandler):
    """Do not follow redirects to another service with company document data."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_sample(path: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                raise ValueError(f"{line_number}행: 올바른 JSON이 아니야.") from None
            if not isinstance(chunk, dict):
                raise ValueError(f"{line_number}행: JSON 객체가 필요해.")
            for field in ("chunk_id", "embedding_text"):
                if not isinstance(chunk.get(field), str) or not chunk[field].strip():
                    raise ValueError(
                        f"{line_number}행: {field}가 없거나 비어 있어. "
                        "청킹 결과 파일을 선택했는지 확인해."
                    )
            chunks.append(chunk)
            if len(chunks) == SAMPLE_SIZE:
                break
    if len(chunks) != SAMPLE_SIZE:
        raise ValueError(f"테스트하려면 최소 {SAMPLE_SIZE}개 청크가 필요해.")
    if len({chunk["chunk_id"] for chunk in chunks}) != SAMPLE_SIZE:
        raise ValueError("샘플에서 중복 chunk_id가 발견됐어.")
    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    # Each list item is a separate model input. Do not join the three chunks.
    payload = {"model": MODEL, "input": texts, "truncate": False}
    request = Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # Ignore proxy settings and refuse redirects: local Ollama only.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=180) as response:
            result = json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        # Avoid echoing input text if an error message happens to include it.
        for text in texts:
            detail = detail.replace(text, "[입력 텍스트 생략]")
        raise RuntimeError(f"Ollama HTTP {error.code}: {detail[:700]}") from None
    except (URLError, TimeoutError) as error:
        raise RuntimeError(
            f"로컬 Ollama 연결 또는 응답 오류: {error}\n"
            "ollama list와 ollama --version 결과를 확인해."
        ) from None

    vectors = result.get("embeddings") if isinstance(result, dict) else None
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise ValueError("입력 개수와 반환된 벡터 개수가 일치하지 않아.")
    dimensions: set[int] = set()
    for vector in vectors:
        if not isinstance(vector, list) or not vector:
            raise ValueError("비어 있거나 형식이 잘못된 벡터가 반환됐어.")
        if any(type(value) not in (int, float) or not math.isfinite(value)
               for value in vector):
            raise ValueError("벡터에 숫자가 아닌 값 또는 NaN/무한대가 있어.")
        if not any(value != 0 for value in vector):
            raise ValueError("모든 좌표가 0인 벡터가 반환됐어.")
        dimensions.add(len(vector))
    if len(dimensions) != 1:
        raise ValueError("반환된 벡터들의 차원이 서로 달라.")
    return vectors


def main() -> int:
    parser = argparse.ArgumentParser(description="청크 3개 로컬 임베딩 테스트")
    parser.add_argument(
        "--input", type=Path,
        default=Path(__file__).resolve().parent / "outputs/chunked_documents_v1.jsonl",
    )
    args = parser.parse_args()
    try:
        chunks = read_sample(args.input)
        texts = [chunk["embedding_text"] for chunk in chunks]
        print(f"입력 청크 수: {len(texts)}", flush=True)
        print(f"사용 모델: {MODEL}", flush=True)
        print("로컬 Ollama에 임베딩 요청 중...", flush=True)
        vectors = embed_texts(texts)
        print(f"생성된 벡터 수: {len(vectors)}")
        print("벡터별 차원:", [len(vector) for vector in vectors])
        print("첫 벡터의 앞 5개 값:", vectors[0][:5])
        print("검증: 개수·차원 일치, 유효한 숫자 확인")
        print("샘플 테스트 완료. 원본 수정·벡터 파일 저장·DB 적재는 하지 않았어.")
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
