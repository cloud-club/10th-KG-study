"""질문 12개 × v1·v2·v3 → 심판(claude-sonnet-5-5, 생성 모델과 다른 계열)이 gold 와 비교해 채점.

판정: correct | partial | wrong. 별도로 unsupported(gold·근거에 없는 사실을 단정했나)를 표시한다.
심판 판정은 1회 실행이다. 6주차 교훈(1회 실행은 결론을 뒤집는다)대로 결과표는 사람이 다시 본다.

실행: python eval.py [--only Q03,Q08]
"""
import argparse
import json
import time

import yaml

from ask import chat, loads_json, v1, v2, v3
from common import LAB, OUT

JUDGE_MODEL = "claude-sonnet-5-5"
JUDGE_SYS = """너는 채점자다. 질문, 정답(gold), 시스템 답을 보고 판정한다. JSON 으로만:
{"verdict": "correct|partial|wrong", "unsupported": true|false, "reason": "<한두 문장>"}
- correct: gold 의 핵심(사람·수치·결론)을 빠짐없이 맞혔다. 목록형은 gold 항목을 모두(또는 gold 가 허용한 기준 이상) 맞혔다.
- partial: 일부만 맞혔거나, 맞지만 핵심 조건·수치가 빠졌다.
- wrong: 핵심이 틀렸거나, 답할 수 있는데 "근거 없음"이라고 했다. gold 가 "없다"인데 누군가를 지목했으면 wrong.
- unsupported: gold 와 모순되거나 gold 에 없는 사실을 확정적으로 주장했으면 true (gold 에 없는 추가 정보가 사실로 보이면 false)."""


def judge(item, ans):
    out = chat(
        [{"role": "system", "content": JUDGE_SYS},
         {"role": "user", "content": f"질문: {item['q']}\n\n정답(gold): {item['gold']}\n\n시스템 답:\n{ans}"}],
        json_mode=True, model=JUDGE_MODEL,
    )
    return loads_json(out)


def main(only):
    items = yaml.safe_load((LAB / "src/questions.yaml").read_text())
    if only:
        items = [i for i in items if i["id"] in only]
    rows = []
    for it in items:
        for name, fn in (("v1", v1), ("v2", v2), ("v3", v3)):
            t = time.time()
            res = fn(it["q"])
            sec = round(time.time() - t, 1)
            j = judge(it, res["answer"])
            rows.append({"id": it["id"], "type": it["type"], "mode": res["mode"], "verdict": j["verdict"],
                         "unsupported": j["unsupported"], "reason": j["reason"], "answer": res["answer"],
                         "cypher": res.get("cypher"), "entities": res.get("entities"), "sources": res.get("sources"),
                         "pages": res.get("pages"), "rows": res.get("rows"), "sec": sec})
            print(f"{it['id']} {res['mode']:<14} {j['verdict']:<8} {'⚠unsupported' if j['unsupported'] else '':<13} {sec}s")
    (OUT / "eval.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    pts = {"correct": 1, "partial": 0.5, "wrong": 0}
    print("\n점수 (correct=1, partial=0.5)")
    for m in ("v1", "v2", "v3"):
        rs = [r for r in rows if r["mode"].startswith(m)]
        print(f"  {m}: {sum(pts[r['verdict']] for r in rs):.1f} / {len(rs)}   unsupported {sum(r['unsupported'] for r in rs)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    main([x for x in ap.parse_args().only.split(",") if x])
