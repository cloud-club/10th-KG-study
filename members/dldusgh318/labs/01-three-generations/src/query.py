"""같은 질문을 세 세대에 동시에 던져 비교하고, 승패 표를 만든다.

이 실습의 결론이 여기서 나온다. 표의 목적은 "어느 게 제일 좋은가"가 아니라
**어느 방식이 어떤 질문에서 이기고 지는가**를 보이는 것이다. 세 방식의
승리 구간이 서로 다르다는 사실이 곧 3주차 하이브리드(BM25+벡터 RRF)의 근거다.

    python src/query.py "지식그래프"     # 한 질문, 세 방식 나란히
    python src/query.py --all            # 질문 10개 전부 실행
    python src/query.py --table          # 결과를 마크다운 표로 results/에 저장
"""
import sys
import time
from pathlib import Path

import gen0_grep
import gen1_es
import gen2_pgvector

LIMIT = 3
RESULTS = Path(__file__).resolve().parent.parent / "results"

# 질문 10개. 유형을 고르게 섞어야 표가 의미를 갖는다 —
# 한쪽으로 몰면 "역시 벡터가 최고" 같은 뻔한 결론만 나온다.
# 실제 코퍼스를 보고 문구는 조정할 것.
QUESTIONS = [
    # --- 0세대가 이길 것으로 예상되는 구간: 정확 매칭 ---
    ("Q01", "HTTP 404", "정확 식별자", "의미 없는 문자열. 임베딩이 오히려 뭉갠다"),
    ("Q02", "OPENAI_API_KEY", "코드/설정 심볼", "정확·결정적이어야 한다"),
    # --- 1세대가 이길 것으로 예상되는 구간: 키워드 + 형태소 ---
    ("Q03", "학교", "조사 결합", "grep -w는 '학교에서'를 놓친다. nori는 잡는다"),
    ("Q04", "쿠버네티스 배포", "복합 키워드", "두 단어 다 있는 문서를 BM25가 위로 올린다"),
    ("Q05", "정처기", "고유 축약어", "사전에 없는 신조어. nori는 쪼개고 n-gram이 잡는다"),
    # --- 2세대가 이길 것으로 예상되는 구간: 표기 변이 + 개념 ---
    ("Q06", "엘라스틱서치", "한영 혼용", "본문이 Elasticsearch면 grep도 BM25도 0건"),
    ("Q07", "지식 그래프", "띄어쓰기 변이", "'지식그래프'와는 grep에겐 남남"),
    ("Q08", "검색이 왜 어려운가", "개념 질의", "문자열로 존재하지 않는 질문"),
    ("Q09", "면접에서 받은 피드백", "자연어 질의", "문서에 이 표현이 그대로 없을 가능성이 높다"),
    ("Q10", "성능을 개선한 경험", "의미 검색", "동의어가 여러 갈래로 흩어져 있다"),
]


def probe(query: str, limit: int = LIMIT):
    """세 방식의 결과를 (건수, 소요ms, 상위 히트) 로 모은다."""
    out = {}

    hits, total, elapsed = gen0_grep.search(query, limit)
    out["gen0"] = (total, elapsed * 1000,
                   [h.split(":", 2)[-1].strip() for h in hits])

    try:
        hits, total, took = gen1_es.search(query, limit)
        out["gen1"] = (total, float(took),
                       [h["_source"]["text"].replace("\n", " ") for h in hits])
    except Exception as e:
        out["gen1"] = (None, None, [f"오류: {e}"])

    try:
        t0 = time.perf_counter()
        rows = gen2_pgvector.search(query, limit)
        out["gen2"] = (len(rows), (time.perf_counter() - t0) * 1000,
                       [t.replace("\n", " ") for t, _ in rows])
    except Exception as e:
        out["gen2"] = (None, None, [f"오류: {e}"])

    return out


def show(qid: str, query: str, kind: str, note: str) -> None:
    print("=" * 78)
    print(f'{qid} [{kind}] "{query}"')
    print(f"    예상: {note}")
    print("=" * 78)
    res = probe(query)
    for key, label in (("gen0", "0세대 grep "), ("gen1", "1세대 BM25 "), ("gen2", "2세대 벡터 ")):
        total, ms, hits = res[key]
        head = f"  [{label}] " + ("건수 --" if total is None else f"{total}건 / {ms:.0f}ms")
        print(head)
        for h in hits or ["(없음)"]:
            print(f"      {h[:96]}")
    print()
    return res


def table() -> None:
    """승패 표를 마크다운으로 저장한다.

    승자 판정은 자동으로 못 한다 — 정답 레이블이 없기 때문이다.
    그래서 건수·지연만 채우고 '판정' 칸은 비워 둔 뒤, 아래에 각 질문의
    실제 상위 결과를 함께 적어서 눈으로 판정할 수 있게 한다.
    (이 한계 자체가 다음 단계인 '골든셋이 필요하다'로 이어진다)
    """
    RESULTS.mkdir(exist_ok=True)
    rows, details = [], []

    for qid, query, kind, note in QUESTIONS:
        res = probe(query)
        def cell(key):
            total, ms, _ = res[key]
            return "오류" if total is None else f"{total}건 / {ms:.0f}ms"
        rows.append(f"| {qid} | {query} | {kind} | {cell('gen0')} | {cell('gen1')} | {cell('gen2')} |  |")

        details.append(f"### {qid} — {query}  ({kind})\n\n> 예상: {note}\n")
        for key, label in (("gen0", "0세대 grep"), ("gen1", "1세대 BM25"), ("gen2", "2세대 벡터")):
            total, ms, hits = res[key]
            details.append(f"**{label}** — " + ("오류" if total is None else f"{total}건 / {ms:.0f}ms"))
            details.append("")
            for h in hits or ["(결과 없음)"]:
                details.append(f"- {h[:160]}")
            details.append("")

    md = [
        "# 질문 10개 × 세 방식 비교",
        "",
        "각 칸은 `히트 수 / 소요시간`. '판정'은 위 결과를 보고 직접 채운다.",
        "",
        "| # | 질문 | 유형 | 0세대 grep | 1세대 BM25 | 2세대 벡터 | 판정 |",
        "|---|------|------|-----------|-----------|-----------|------|",
        *rows,
        "",
        "## 상세 결과",
        "",
        *details,
    ]
    out = RESULTS / "comparison.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"표 저장: {out}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('사용법: python src/query.py "<질문>" | --all | --table')
    arg = sys.argv[1]
    if arg == "--table":
        table()
    elif arg in ("--all", "--demo"):
        for qid, query, kind, note in QUESTIONS:
            show(qid, query, kind, note)
    else:
        show("Q--", arg, "직접 입력", "-")


if __name__ == "__main__":
    main()
