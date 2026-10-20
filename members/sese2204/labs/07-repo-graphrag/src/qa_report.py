"""정성평가용 질의–답변 문서 생성 — outputs/eval.json → ../QA.md

질문 12개는 정답률을 비교하기엔 적다. 그래서 세 방식의 답변 원문을 질문별로 나란히 놓고 사람이 읽는다.
심판 판정은 참고로만 접어 둔다.

실행: python qa_report.py [eval 파일 이름]   (기본 eval_run4_terra.json — outputs/ 에 없으면 snapshot/results/ 에서 찾는다)
"""
import json
import sys
from collections import Counter

import yaml

from common import LAB, OUT

MODE_NAME = {"v1": "v1 · 청크 하이브리드", "v2": "v2 · GraphRAG", "v3": "v3 · LLM 위키"}
MARK = {"correct": "✅", "partial": "△", "wrong": "❌"}


def quote(text):
    return "\n".join("> " + line if line.strip() else ">" for line in text.strip().splitlines())


def evidence_line(r):
    m = r["mode"]
    if m.startswith("v1"):
        docs = Counter(r.get("sources") or [])
        return "근거 청크의 문서: " + ", ".join(f"`{p.split('/', 2)[2] if p.count('/') >= 2 else p}`" + (f" ×{n}" if n > 1 else "")
                                           for p, n in docs.items())
    if m.startswith("v3"):
        return "검색된 위키 페이지: " + ", ".join(f"[[{p}]]" for p in r.get("pages") or [])
    parts = [f"경로 `{m.replace('v2/', '')}`"]
    if r.get("entities"):
        parts.append("진입 엔티티 " + ", ".join(r["entities"]))
    if r.get("cypher"):
        parts.append(f"Cypher 결과 {r.get('rows', '?')}행")
    return " · ".join(parts)


def main(path):
    rows = json.loads(path.read_text())
    items = {q["id"]: q for q in yaml.safe_load((LAB / "src/questions.yaml").read_text())}
    by_q = {}
    for r in rows:
        by_q.setdefault(r["id"], {})[r["mode"][:2]] = r
    out = [
        "# 질의–답변 모음 (정성평가용)",
        "",
        f"> `src/qa_report.py`가 `{path.name}`에서 생성한다. 손으로 고치지 말고 다시 생성한다.",
        "> 생성 `gpt-5.4-mini` · 추출 `gpt-5.6-terra` · 판정 `claude-sonnet-5-5`(1회, 참고용).",
        "> 답변 속 `[C·G·S·W번호]`는 각 방식이 받은 근거 번호다. C 원문 청크, G 그래프 사실, S 커뮤니티 요약, W 위키.",
        "",
        "## 읽는 법",
        "",
        "질문마다 정답(gold)과 세 방식의 답을 나란히 둔다. 판정 표시는 참고용이고, 다음을 보며 읽는다.",
        "",
        "- **누가 확인했나**를 맞게 붙였나 (멤버 id, 측정 vs 정리)",
        "- 근거에 없는 것을 **단정**했나, 모르면 \"근거 없음\"이라고 했나",
        "- 수치에 **조건**(데이터·문항 수·지표)이 따라왔나",
        "- 여러 멤버를 **모았나**, 한 문서에 머물렀나",
        "",
        "| # | 유형 | v1 | v2 | v3 |",
        "|---|---|---|---|---|",
    ]
    for qid in sorted(by_q):
        d = by_q[qid]
        out.append(f"| [{qid}](#{qid.lower()}) | {items[qid]['type']} | "
                   + " | ".join(MARK[d[m]["verdict"]] + ("⚠" if d[m]["unsupported"] else "") for m in ("v1", "v2", "v3")) + " |")
    out += ["", "✅ 정답 · △ 부분 · ❌ 오답 · ⚠ 근거 없는 단정 (심판 1회 판정)", ""]
    for qid in sorted(by_q):
        it, d = items[qid], by_q[qid]
        out += ["---", "", f"## {qid}", "", f"**{it['type']}** — {it['q']}", "",
                f"**정답(gold)**: {it['gold']}", "", f"<sub>gold 근거: {it['gold_source']}</sub>", ""]
        for m in ("v1", "v2", "v3"):
            r = d[m]
            out += [f"### {MODE_NAME[m]}", "", f"<sub>{evidence_line(r)}</sub>", "", quote(r["answer"]), ""]
            if r.get("cypher"):
                out += ["<details><summary>생성된 Cypher</summary>", "", "```cypher", r["cypher"].strip(), "```", "", "</details>", ""]
            out += [f"<details><summary>판정 {MARK[r['verdict']]}{' ⚠' if r['unsupported'] else ''}</summary>", "",
                    r["reason"], "", "</details>", ""]
    target = LAB / "QA.md"
    target.write_text("\n".join(out))
    print(f"wrote {target} ({len(by_q)} questions)")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "eval_run4_terra.json"
    main(next(p for p in (OUT / name, LAB / "snapshot/results" / name) if p.exists()))
