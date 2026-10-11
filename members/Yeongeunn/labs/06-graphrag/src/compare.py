"""고정된 입력으로 문서 RAG와 그래프 결합 RAG의 답변을 비교한다."""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(
    0,
    str(ROOT / "members/Yeongeunn/labs/03-notion-ingest/src"),
)
from rag import config, generate


def main():
    # 1. 두 방식에 사용할 질문·모델·근거를 읽는다.
    folder = ROOT / "data/Yeongeunn/graphrag-v1"
    input_bytes = (folder / "comparison-input.json").read_bytes()
    payload = json.loads(input_bytes)

    # 입력이 달라지면 다른 결과 파일에 저장한다.
    fingerprint = hashlib.sha256(input_bytes).hexdigest()
    output = folder / ("comparison-" + fingerprint[:12])
    output.mkdir(parents=True, exist_ok=True)

    # 2. 같은 생성 함수에 v1, v2의 근거를 각각 전달한다.
    for method in ("v1", "v2"):
        target = output / f"{method}.json"

        # 성공적으로 저장된 결과는 재호출하지 않는다.
        if target.exists():
            result = json.loads(target.read_text())
            if result["input_sha256"] != fingerprint:
                raise RuntimeError("저장된 결과의 입력이 다릅니다.")
            print(f"\n{method}: 저장된 결과 사용")
        else:
            key = config().get("GEMINI_API_KEY")
            if not key:
                raise RuntimeError("루트 .env의 GEMINI_API_KEY를 확인하세요.")

            print(f"\n{method}: Gemini 호출 중...", flush=True)
            started = time.perf_counter()
            answer, reason, usage = generate(
                key,
                payload["model"],
                payload["question"],
                payload[method],
            )
            elapsed = time.perf_counter() - started

            # 3. 답변과 실행 정보를 로컬에 저장한다.
            result = {
                "method": method,
                "input_sha256": fingerprint,
                "model": payload["model"],
                "question": payload["question"],
                "evidence_count": len(payload[method]),
                "answer": answer,
                "finish_reason": reason,
                "usage": usage,
                "generation_seconds": round(elapsed, 2),
            }
            target.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        # 4. 두 답변을 직접 비교할 수 있게 출력한다.
        print(result["answer"])
        print("근거 개수:", result["evidence_count"])
        print("생성 요청 시간:", result["generation_seconds"], "초")
        print("토큰:", json.dumps(result["usage"], ensure_ascii=False))
        print("저장:", target)

        if result["finish_reason"] != "STOP":
            print("정상 종료가 아닙니다. 종료 상태:", result["finish_reason"])


if __name__ == "__main__":
    main()
