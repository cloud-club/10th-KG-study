"""의미 층 추출 — 닫힌 스키마로 Finding · Pitfall · Dataset 을 뽑는다.

LLM 이 정하지 않는 것:
  - 누가 썼나: Chunk → Document → Member 경로로 정해진다
  - 엔티티 이름: entities.yaml 의 정규 이름만 쓴다. 사전 밖 이름은 버리지 않고 candidates 로 모은다
  - MENTIONS · PART_OF: 사전 매칭·사람이 정한 분류 (load_semantic.py)

검증: evidence 가 해당 청크 원문에 실제로 있어야 채택한다(공백 정규화 후 부분 문자열).
스키마에 안 맞는 사실은 억지로 넣지 말고 review_queue 로 (5주차 heebindev 처방).

실행: python extract.py --sample 6   (표본)   /   python extract.py   (전체, note·lab 문서)
"""
import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor

import yaml

from common import CHAT_MODEL, LAB, OUT, JsonCache, llm

ENTS = yaml.safe_load((LAB / "src/entities.yaml").read_text())
TECHNIQUES = list(ENTS["Technique"])
TOOLS = list(ENTS["Tool"])
BATCH_CHARS = 3500
PROMPT_VERSION = "v2"
METRIC_LIKE = {"Recall@k", "MRR", "nDCG", "RAG 평가"}  # about 이 이것뿐이면 평가 대상이 빠진 것

SYSTEM = f"""너는 스터디 노트에서 지식그래프용 사실을 뽑는 추출기다. 반드시 JSON 객체 하나만 출력한다.

## 뽑는 것 (이것 외에는 뽑지 않는다)
1. findings — 실험·비교의 **결론**. 노트 작성자가 **직접 돌린 실험**이면 kind="measured", 논문·블로그·다른 사람의 결과를
   옮긴 것이면 kind="cited". 수치가 없어도 "A보다 B가 나았다"처럼 비교 결론이 명시돼 있으면 뽑는다.
   - 표나 여러 문항의 결과는 **문항별로 쪼개지 말고** 하나로 묶는다. value 에 요약한다 (예: "다중 홉 4문항 v1 0.33·0.50·0.00·0.00 → v2 1.00").
   - 실험 설정·절차·기록 방법("시간은 합산해 기록했다", "조회 예산은 5회")은 결론이 아니다. condition 에만 쓰고 따로 뽑지 않는다.
   - 계획·의견·일반 설명은 뽑지 않는다. 한 청크에서 findings 는 많아야 3개.
2. pitfalls — 작성자가 **실제로 부딪힌** 실패·오류·한계 (무엇이 틀렸거나 막혔나). 교과서식 일반론,
   일부러 둔 안전장치("평가 ID 를 쓰지 않았다"), 결과 해석상의 단서("벤치마크로 보지 말라")는 pitfall 이 아니다.

## 엔티티 이름 (닫힌 목록 — 철자 그대로)
Technique: {", ".join(TECHNIQUES)}
Tool: {", ".join(TOOLS)}
목록에 맞는 게 없으면 억지로 고르지 말고 unlisted 에 원문 표현을 적는다.

## 형식
{{"findings": [{{"chunk": "<청크 id>", "kind": "measured|cited",
   "about": ["<엔티티>"], "dataset": "<데이터 유형 — 예: 인스타그램 캡션, Notion 노트, 카카오톡 대화, 회사 기술 문서, 공개 판례. 없으면 null>",
   "metric": "<지표 — 예: Recall@5, 정답 수, 지연 시간. 없으면 null>", "value": "<값 원문 그대로. 없으면 null>",
   "condition": "<비교 조건·설정 한 줄>",
   "compared_with": [{{"entity": "<엔티티>", "outcome": "win|lose|tie"}}],
   "claim": "<결론 한 문장, 원문 의미 그대로>", "evidence": "<청크 원문에서 그대로 복사한 30~150자>",
   "unlisted": ["<목록에 없던 대상 표현>"]}}],
 "pitfalls": [{{"chunk": "<청크 id>", "name": "<함정 이름 10~30자>", "description": "<무엇이 왜 문제였나 한두 문장>",
   "occurs_in": ["<엔티티>"], "mitigated_by": ["<엔티티 — 처방이 문서에 적혀 있을 때만>"], "mitigation": "<처방 한 줄 또는 null>",
   "evidence": "<청크 원문에서 그대로 복사한 30~150자>", "unlisted": []}}],
 "review_queue": [{{"chunk": "<청크 id>", "fact": "<스키마에 안 맞지만 중요해 보이는 사실>", "reason": "<왜 안 맞나>"}}]}}

## 규칙
- about 은 **평가 대상인 기법·도구**다. Recall@k·MRR·nDCG 같은 지표는 about 이 아니라 metric 에 쓴다.
- compared_with 의 outcome 은 about 쪽 기준이다 (about 이 이겼으면 win). 비교 기준선이 문서에 명시된 경우만 채운다.
- evidence 는 반드시 원문 복사. 요약·번역 금지.
- 사람 이름·계정·대화 내용·회사명 같은 개인 정보는 dataset·claim 에 쓰지 않는다. 데이터는 유형으로만 적는다.
- 해당 사항이 없으면 빈 배열."""


def batches(doc):
    cur, size = [], 0
    for c in doc["chunks"]:
        if cur and size + len(c["text"]) > BATCH_CHARS:
            yield cur
            cur, size = [], 0
        cur.append(c)
        size += len(c["text"])
    if cur:
        yield cur


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def call(doc, chunks, cache):
    user = f"문서: {doc['title']} ({doc['kind']}, 작성자 id 는 그래프가 따로 관리하므로 무시)\n\n" + "\n\n".join(
        f"<chunk id=\"{c['id']}\">\n{c['text']}\n</chunk>" for c in chunks
    )
    k = JsonCache.key(PROMPT_VERSION, CHAT_MODEL, SYSTEM, user)
    hit = cache.get(k)
    if hit is not None:
        return hit
    resp = llm().chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    try:
        out = json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        out = {"error": resp.choices[0].message.content[:500]}
    out["_usage"] = [resp.usage.prompt_tokens, resp.usage.completion_tokens]
    cache.put(k, out)
    return out


ALIAS = {a.lower(): name for d in ENTS.values() for name, v in d.items() for a in v["aliases"] + [name]}


def canon(e):
    """LLM 이 별칭으로 쓴 이름('Vector Search', 'Turtle')을 정규 이름으로 돌린다. 모르면 그대로."""
    if not isinstance(e, str):
        return e
    k = e.strip().lower()
    return ALIAS.get(k) or ALIAS.get(re.sub(r"[-_ ]?v?\d+(\.\d+)*$", "", k)) or e


def validate(raw, chunks):
    """엔티티 이름·evidence·chunk id 를 검사해 채택분과 탈락 사유를 나눈다."""
    text = {c["id"]: norm(c["text"]) for c in chunks}
    allowed = set(TECHNIQUES) | set(TOOLS)
    seen = set()
    for kind in ("findings", "pitfalls"):
        for item in raw.get(kind) or []:
            for f in ("about", "occurs_in", "mitigated_by"):
                if isinstance(item.get(f), list):
                    item[f] = list(dict.fromkeys(canon(e) for e in item[f]))
            for x in item.get("compared_with") or []:
                x["entity"] = canon(x.get("entity"))
    kept, dropped = {"findings": [], "pitfalls": [], "review_queue": []}, []
    for kind in ("findings", "pitfalls"):
        for item in raw.get(kind) or []:
            cid = item.get("chunk")
            if cid not in text:
                dropped.append((kind, "unknown chunk", item))
                continue
            if not item.get("evidence") or norm(item["evidence"]) not in text[cid]:
                dropped.append((kind, "evidence not in chunk", item))
                continue
            fields = ("about",) if kind == "findings" else ("occurs_in", "mitigated_by")
            for f in fields:
                bad = [e for e in item.get(f) or [] if e not in allowed]
                item[f] = [e for e in item.get(f) or [] if e in allowed]
                item.setdefault("unlisted", []).extend(bad)
            if kind == "findings":
                cw = [x for x in item.get("compared_with") or [] if x.get("entity") in allowed]
                item.setdefault("unlisted", []).extend(
                    x.get("entity") for x in item.get("compared_with") or [] if x.get("entity") not in allowed
                )
                # 자기 자신과의 비교(about 에도 있는 엔티티)는 승패 방향이 뒤집혀 들어오므로 버린다
                item["compared_with"] = [
                    x for x in cw if x.get("outcome") in ("win", "lose", "tie") and x["entity"] not in item["about"]
                ]
                if not item["about"]:
                    dropped.append((kind, "no listed entity", item))
                    continue
                if set(item["about"]) <= METRIC_LIKE and not item["compared_with"]:
                    dropped.append((kind, "only metric, no subject", item))
                    continue
                dup = (cid, norm(item.get("claim")))
                if dup in seen:
                    dropped.append((kind, "duplicate", item))
                    continue
                seen.add(dup)
            elif not item["occurs_in"]:
                dropped.append((kind, "no listed entity", item))
                continue
            kept[kind].append(item)
    kept["review_queue"] = [r for r in raw.get("review_queue") or [] if r.get("chunk") in text]
    return kept, dropped


def run(docs, workers=8):
    cache = JsonCache("extract")
    jobs = [(d, b) for d in docs for b in batches(d)]
    with ThreadPoolExecutor(workers) as pool:
        raws = list(pool.map(lambda j: call(j[0], j[1], cache), jobs))
    result = {"findings": [], "pitfalls": [], "review_queue": [], "dropped": [], "usage": [0, 0], "errors": 0}
    for (d, b), raw in zip(jobs, raws):
        if "error" in raw:
            result["errors"] += 1
            continue
        result["usage"][0] += raw["_usage"][0]
        result["usage"][1] += raw["_usage"][1]
        kept, dropped = validate(raw, b)
        for kind in ("findings", "pitfalls", "review_queue"):
            result[kind].extend(kept[kind])
        result["dropped"].extend({"kind": k, "reason": r, "item": i} for k, r, i in dropped)
    return result, len(jobs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="note·lab 문서 중 앞에서부터 멤버별로 고른 N편만")
    args = ap.parse_args()
    docs = [d for d in json.loads((OUT / "corpus.json").read_text()) if d["kind"] in ("note", "lab")]
    if args.sample:
        picks = ["members/kdyann/labs/06-graphrag/README.md", "members/heebindev/labs/03-triple-extraction-kg/README.md",
                 "members/e0ng/notes/03-rrf.md", "members/lys0611/labs/02-hybrid-rag-agent/README.md",
                 "members/dldusgh318/labs/01-three-generations/WEEK3_hybrid_search_rrf.md",
                 "members/sunghyun/labs/06-graphrag/README.md"]
        by_path = {d["path"]: d for d in docs}
        docs = [by_path[p] for p in picks if p in by_path][: args.sample]
        print("sample:", [d["path"] for d in docs])
    result, n_calls = run(docs)
    name = "extract_sample.json" if args.sample else "extract.json"
    (OUT / name).write_text(json.dumps(result, ensure_ascii=False, indent=1))
    from collections import Counter

    print(f"calls {n_calls}, errors {result['errors']}, tokens in/out {result['usage']}")
    print(f"findings {len(result['findings'])} (measured {sum(f.get('kind') == 'measured' for f in result['findings'])}), "
          f"pitfalls {len(result['pitfalls'])}, review_queue {len(result['review_queue'])}, dropped {len(result['dropped'])}")
    print("dropped reasons", Counter(d["reason"] for d in result["dropped"]))
    print("unlisted", Counter(u for k in ("findings", "pitfalls") for i in result[k] for u in i.get("unlisted") or []).most_common(15))
