"""고정 Cypher로 조회한 그래프 근거를 Gemini에 전달한다."""
import json
import sys

from preview import ROOT, QUESTION, retrieve

sys.path.insert(
    0,
    str(ROOT / "members/Yeongeunn/labs/03-notion-ingest/src"),
)
from rag import config, generate, redact


def main():
    rows = retrieve()
    if not rows:
        print("조회된 근거가 없어 Gemini를 호출하지 않았습니다.")
        return

    settings = config()
    key = settings.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("저장소 루트 .env의 GEMINI_API_KEY를 확인하세요.")

    # 외부에는 관계와 필요한 근거만 전달한다.
    # 청크 ID는 아래에서 로컬 출처 확인용으로 출력한다.
    evidence = [
        {
            "number": row["number"],
            "content": redact(json.dumps({
                "relation": row["relation"],
                "quotes": [
                    {"field": item["field"], "quote": item["quote"]}
                    for item in row["evidence"]
                ],
            }, ensure_ascii=False)),
        }
        for row in rows
    ]

    question = QUESTION + """
답변에서 '호출 대상 서비스'와 '그 서비스가 제공하는 API'를 구분하라.
제공 관계만으로 해당 API가 직접 호출된다고 단정하지 마라.
호출 순서는 이 근거만으로 알 수 없다.
문서에 기록된 경로를 임의로 수정하지 마라.
"""

    model = "gemini-3.1-flash-lite"
    print(f"모델: {model}")
    print(f"그래프 근거 {len(evidence)}개를 Gemini에 전달합니다.", flush=True)
    answer, reason, usage = generate(key, model, question, evidence)

    print("\n" + answer)
    if reason != "STOP":
        print("\n종료 상태 확인 필요:", reason)

    print("\n출처 확인용 청크 ID:")
    for row in rows:
        ids = sorted({item["chunk_id"] for item in row["evidence"]})
        print(f'[{row["number"]}] {", ".join(ids)}')

    print("\n토큰 사용량:", json.dumps(usage, ensure_ascii=False))


if __name__ == "__main__":
    main()
