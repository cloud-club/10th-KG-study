"""추출 결과 정확도 채점 — 추출한 Finding·Pitfall 하나하나를 원문 청크와 대조한다 (심판: claude-sonnet-5-5).

판정 항목: faithful(원문이 그 사실을 실제로 말하나), kind_ok(measured/cited 구분), direction_ok(COMPARED_WITH 승패 방향),
pitfall_ok(실제로 부딪힌 함정인가). 추출 모델끼리 비교할 때 쓴다.

실행: python judge_extract.py ../outputs/extract_sample.json ../outputs/extract_sample_gpt-5.6-terra.json
     python judge_extract.py --n 60 ../outputs/extract.json ../outputs/extract_gpt-5.6-terra.json   (무작위 표본, seed 고정)
"""
import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ask import chat, loads_json
from common import OUT

JUDGE = "claude-sonnet-5-5"
SYS = """너는 지식그래프 추출 결과를 원문과 대조하는 검수자다. JSON 으로만 답한다.
Finding 이면: {"faithful": true|false, "kind_ok": true|false, "direction_ok": true|false|null, "note": "<한 줄>"}
  - faithful: claim·value·about 이 원문이 실제로 말하는 내용과 맞나 (과장·왜곡·다른 대상 혼동이면 false)
  - kind_ok: kind=measured 면 작성자가 직접 돌린 실험이 맞나, cited 면 남의 결과 인용이 맞나
  - direction_ok: compared_with 가 있으면 outcome(about 쪽 기준 win/lose/tie)이 원문과 맞나. 없으면 null
Pitfall 이면: {"faithful": true|false, "pitfall_ok": true|false, "note": "<한 줄>"}
  - pitfall_ok: 작성자가 실제로 부딪힌 실패·오류·한계인가 (일반론·안전장치·해석상 단서면 false)"""


def chunk_texts():
    docs = json.loads((OUT / "corpus.json").read_text())
    return {c["id"]: c["text"] for d in docs for c in d["chunks"]}


def judge_one(kind, item, text):
    fields = {k: v for k, v in item.items() if k not in ("unlisted",)}
    out = chat([{"role": "system", "content": SYS},
                {"role": "user", "content": f"## 원문 청크\n{text}\n\n## 추출된 {kind}\n{json.dumps(fields, ensure_ascii=False)}"}],
               json_mode=True, model=JUDGE)
    return loads_json(out)


def score(path, texts, n=0, cw_only=False):
    r = json.loads(Path(path).read_text())
    finds, pits = r["findings"], r["pitfalls"]
    if cw_only:  # 승패 방향만 따로 본다 — COMPARED_WITH 가 있는 Finding 은 전체의 1할 남짓이라 무작위 표본에 잘 안 걸린다
        finds, pits = [f for f in finds if f.get("compared_with")], []
    if n:  # Finding n건 · Pitfall 2n/3건 무작위 (같은 seed)
        finds = random.Random(42).sample(finds, min(n, len(finds)))
        pits = random.Random(42).sample(pits, min(n * 2 // 3, len(pits)))
    jobs = [("Finding", f) for f in finds] + [("Pitfall", p) for p in pits]
    with ThreadPoolExecutor(8) as pool:
        verdicts = list(pool.map(lambda j: judge_one(j[0], j[1], texts[j[1]["chunk"]]), jobs))
    F = [v for (k, _), v in zip(jobs, verdicts) if k == "Finding"]
    P = [v for (k, _), v in zip(jobs, verdicts) if k == "Pitfall"]
    D = [v["direction_ok"] for v in F if v.get("direction_ok") is not None]

    def rate(xs):
        return f"{sum(xs)}/{len(xs)}" + (f" ({100 * sum(xs) / len(xs):.0f}%)" if xs else "")

    summary = {"file": Path(path).name, "n": n, "cw_only": cw_only,
               "finding_faithful": rate([v["faithful"] for v in F]), "finding_kind_ok": rate([v["kind_ok"] for v in F]),
               "direction_ok": rate(D), "pitfall_faithful": rate([v["faithful"] for v in P]),
               "pitfall_ok": rate([v["pitfall_ok"] for v in P])}
    log = OUT / "judge_extract.json"
    rows = [r for r in (json.loads(log.read_text()) if log.exists() else [])
            if (r["file"], r["n"], r["cw_only"]) != (summary["file"], n, cw_only)]
    log.write_text(json.dumps(rows + [summary], ensure_ascii=False, indent=1))

    print(f"\n{Path(path).name}")
    print(f"  Finding  faithful {rate([v['faithful'] for v in F])}  kind_ok {rate([v['kind_ok'] for v in F])}  direction_ok {rate(D)}")
    print(f"  Pitfall  faithful {rate([v['faithful'] for v in P])}  pitfall_ok {rate([v['pitfall_ok'] for v in P])}")
    bad = [(k, i, v) for (k, i), v in zip(jobs, verdicts)
           if not v["faithful"] or v.get("direction_ok") is False or v.get("pitfall_ok") is False or v.get("kind_ok") is False]
    for k, i, v in bad[:12]:
        print(f"   ✗ {k} {i['chunk'].split('/')[1]} · {(i.get('claim') or i.get('name'))[:60]} — {v['note'][:90]}")
    return verdicts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--cw-only", action="store_true", help="COMPARED_WITH 가 있는 Finding 만")
    a = ap.parse_args()
    texts = chunk_texts()
    for p in a.files:
        score(p, texts, a.n, a.cw_only)
