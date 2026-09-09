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

# 프로브 쿼리 10개. 부류를 정해두고 개수를 맞춘다 —
# 한쪽으로 몰면 "역시 벡터가 최고" 같은 뻔한 결론만 나오고
# 정작 알고 싶은 **경계선**이 안 보인다.
#   A 정확 키워드·고유명사·ID  4개  → 0세대가 이길 것으로 예상
#   B 표현 불일치·의미 검색     3개  → 2세대가 이길 것으로 예상
#   C 오타·띄어쓰기 파괴        3개  → 0·1세대가 무너지는 지점
QUESTIONS = [
    # --- A. 정확 키워드·고유명사·ID ---
    ("Q01", "SeCause", "A 고유명사", "프로젝트명. 의미가 없어 임베딩이 오히려 뭉갠다"),
    ("Q02", "@Transactional", "A 코드 심볼", "정확·결정적이어야 한다"),
    ("Q03", "Write-Behind", "A 기술 용어", "하이픈 복합어. nori가 어떻게 쪼개는지가 갈림길"),
    ("Q04", "청바지", "A 고유명사(함정)", "내 프로젝트명이지만 일반명사라 벡터가 의류로 끌려갈 수 있다"),
    # --- B. 표현 불일치·의미 검색 ---
    ("Q05", "성능을 개선한 경험", "B 의미 검색", "동의어가 여러 갈래로 흩어져 있다"),
    ("Q06", "면접에서 받은 피드백", "B 자연어 질의", "이 표현이 문서에 그대로 없을 가능성이 높다"),
    ("Q07", "검색이 왜 어려운가", "B 개념 질의", "문자열로 존재하지 않는 질문"),
    # --- C. 오타·띄어쓰기 파괴 ---
    ("Q08", "트러블 슈팅", "C 띄어쓰기 파괴", "원문은 '트러블슈팅'(14건). 띄어쓴 건 1건뿐"),
    ("Q09", "엘라스틱 서치", "C 띄어쓰기+한영", "원문은 '엘라스틱서치'(4건). 띄어쓴 형태는 0건"),
    ("Q10", "쿠버네티즈", "C 오타", "원문은 '쿠버네티스'(9건). 오타는 0건 — grep·BM25 둘 다 무너진다"),
]


def warmup() -> None:
    """임베딩 모델을 미리 올려둔다.

    이걸 안 하면 첫 벡터 검색에 모델 로딩(수 초)이 섞여 들어가서
    "벡터 검색은 10초 걸린다"는 엉뚱한 수치가 표에 박힌다.
    """
    try:
        gen2_pgvector.embedder()
    except Exception:
        pass


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
    """비교 결과를 순위 기록으로 저장한다.

    점수는 방식마다 척도가 달라서(BM25 점수 vs 코사인 유사도 vs 없음) 나란히
    놓으면 비교가 안 된다. 그래서 **무엇이 몇 위로 나왔는지**만 적는다.
    순위는 척도가 달라도 비교가 된다.

    승자 판정은 자동으로 못 한다 — 정답 레이블이 없기 때문이다.
    이 한계가 그대로 다음 단계('골든셋이 필요하다')의 이유가 된다.
    """
    RESULTS.mkdir(exist_ok=True)
    summary, blocks = [], []

    for qid, query, kind, note in QUESTIONS:
        res = probe(query)

        def hits(key):
            return res[key][2] or []

        found = {k: ("없음" if not res[k][0] else f"{res[k][0]}건") for k in res}
        summary.append(f"| {qid} | `{query}` | {kind} | {found['gen0']} | {found['gen1']} | {found['gen2']} |  |")

        blocks.append(f"### {qid} — `{query}`  ({kind})\n")
        blocks.append(f"> {note}\n")
        blocks.append("| 순위 | 0세대 grep | 1세대 BM25 | 2세대 벡터 |")
        blocks.append("|------|-----------|-----------|-----------|")
        for i in range(LIMIT):
            def cell(key):
                h = hits(key)
                if i >= len(h):
                    return "—"
                return h[i][:70].replace("|", "\\|").strip()
            blocks.append(f"| {i+1} | {cell('gen0')} | {cell('gen1')} | {cell('gen2')} |")
        blocks.append("")

    md = [
        "# 프로브 쿼리 10개 × 세 방식 비교",
        "",
        "온톨로지 스터디 2주차 실습. 같은 질문을 grep / Elasticsearch BM25 / pgvector에",
        "똑같이 던지고 **무엇이 몇 위로 나왔는지**를 기록한다.",
        "",
        "점수를 안 쓰고 순위를 쓰는 이유: BM25 점수와 코사인 유사도는 척도가 달라",
        "나란히 놓으면 비교가 되지 않는다. 순위는 척도가 달라도 비교된다.",
        "",
        "## 요약",
        "",
        "| # | 쿼리 | 부류 | grep | BM25 | 벡터 | 판정 |",
        "|---|------|------|------|------|------|------|",
        *summary,
        "",
        "## 쿼리별 순위",
        "",
        *blocks,
    ]
    out = RESULTS / "compare.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"비교 결과 저장: {out}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('사용법: python src/query.py "<질문>" | --all | --table')
    arg = sys.argv[1]
    warmup()
    if arg == "--table":
        table()
    elif arg in ("--all", "--demo"):
        for qid, query, kind, note in QUESTIONS:
            show(qid, query, kind, note)
    else:
        show("Q--", arg, "직접 입력", "-")


if __name__ == "__main__":
    main()
