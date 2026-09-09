#!/usr/bin/env python3
"""이름 가명화 + 개인정보 마스킹.

- 발신자 이름을 가명으로 바꾸고, 본문에 등장하는 그 이름(성 포함 / 이름만)도 같은 가명으로 치환한다.
  같은 사람은 항상 같은 가명 → 뒤에서 그래프를 만들 때 사람 노드가 깨지지 않는다.
- 전화번호·주민등록번호·카드번호·계좌번호(추정)·이메일·긴 숫자열을 [전화번호] 같은 토큰으로 바꾼다.
- 매핑표(name_map.json)는 data/private/ 에만 저장하고 절대 커밋하지 않는다. (.gitignore 에 포함)

사용법
  python src/pseudonymize.py data/interim/여행모임.jsonl \
      --out data/interim/여행모임.masked.jsonl --map data/private/name_map.json

매핑표는 {"실명": "가명"} JSON. 처음 실행하면 자동으로 채워지며, 이후 파일을 열어
자연스러운 가명으로 바꾸고 다시 실행하면 그대로 반영된다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# 기본 가명 풀. 다 쓰면 가명NN 으로 이어진다. (실제 지인 이름과 겹치면 매핑표에서 바꿔 쓰면 된다)
DEFAULT_POOL = [
    "김하람", "이도윤", "박서아", "최준우", "정하윤", "강지호", "조은우", "윤서윤", "장시우", "임유나",
    "한지안", "오수아", "서예준", "신다은", "권하준", "황지우", "안서준", "송아린", "류건우", "홍하은",
]

# 이름 뒤에 붙어도 이름으로 인정할 조사/호칭 (이 뒤에 한글이 더 오면 다른 단어로 본다)
_SUFFIX = r"(?=$|[^가-힣]|(?:야|아|님|형|누나|오빠|언니|씬|씨|이|가|은|는|도|한테|랑|이랑|이가|을|를|의|만|께|한테서)(?![가-힣]))"


def _digits(s: str) -> int:
    return sum(ch.isdigit() for ch in s)


PII_PATTERNS: list[tuple[str, re.Pattern, "callable | None"]] = [
    ("이메일", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), None),
    ("주민번호", re.compile(r"(?<!\d)\d{6}\s?-\s?[1-4]\d{6}(?!\d)"), None),
    ("카드번호", re.compile(r"(?<!\d)\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}(?!\d)"), None),
    ("전화번호", re.compile(r"(?<!\d)01[016789][- .]?\d{3,4}[- .]?\d{4}(?!\d)"), None),
    ("전화번호", re.compile(r"(?<!\d)0(?:2|3[1-3]|4[1-4]|5[1-5]|6[1-4]|70|80)[- .]?\d{3,4}[- .]?\d{4}(?!\d)"), None),
    # 하이픈 포함 숫자 묶음 중 총 자릿수 10~16 → 계좌번호로 추정 (날짜 2024-01-01 은 8자리라 제외됨)
    ("계좌번호", re.compile(r"(?<!\d)\d{2,6}(?:-\d{2,7}){1,3}(?!\d)"), lambda s: 10 <= _digits(s) <= 16),
    # 하이픈 없는 10~14자리 숫자열 (계좌·운송장·주문번호 등, 보수적으로 가림)
    ("숫자열", re.compile(r"(?<!\d)\d{10,14}(?!\d)"), None),
]


def mask_pii(text: str, stats: Counter) -> str:
    for label, pat, cond in PII_PATTERNS:
        def _rep(m, label=label, cond=cond):
            if cond and not cond(m.group(0)):
                return m.group(0)
            stats[label] += 1
            return f"[{label}]"
        text = pat.sub(_rep, text)
    return text


def build_name_patterns(name_map: dict[str, str]) -> list[tuple[re.Pattern, str]]:
    """긴 이름부터 치환하도록 정렬. (성+이름) 전체와, 3글자 한글 이름의 (이름) 부분을 각각 패턴화."""
    pats: list[tuple[re.Pattern, str]] = []
    for real, fake in sorted(name_map.items(), key=lambda kv: -len(kv[0])):
        if not real.strip():
            continue
        pats.append((re.compile(re.escape(real)), fake))
        if re.fullmatch(r"[가-힣]{3,4}", real):
            given = real[1:]
            fake_given = fake[1:] if re.fullmatch(r"[가-힣]{3}", fake) else fake
            pats.append((re.compile(rf"(?<![가-힣]){re.escape(given)}{_SUFFIX}"), fake_given))
    return pats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inp", help="parse_kakao.py 가 만든 JSONL")
    ap.add_argument("--out", required=True)
    ap.add_argument("--map", default="data/private/name_map.json", help="실명→가명 매핑 JSON (비공개)")
    ap.add_argument("--extra-names", nargs="*", default=[],
                    help="발신자는 아니지만 본문에 자주 나오는 실명(제3자)도 가명화하려면 여기에 추가")
    ap.add_argument("--no-pii", action="store_true", help="숫자/이메일 마스킹 생략 (이름만 가명화)")
    args = ap.parse_args()

    msgs = [json.loads(l) for l in open(args.inp, encoding="utf-8") if l.strip()]
    senders = {m["sender"] for m in msgs if m.get("sender")}
    names = sorted(senders | set(args.extra_names), key=len, reverse=True)

    map_path = Path(args.map)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    name_map: dict[str, str] = json.loads(map_path.read_text(encoding="utf-8")) if map_path.exists() else {}
    used = set(name_map.values())
    pool = [p for p in DEFAULT_POOL if p not in used]
    for n in names:
        if n in name_map:
            continue
        fake = pool.pop(0) if pool else f"가명{len(name_map) + 1:02d}"
        while fake in used:
            fake = f"가명{len(name_map) + 1:02d}"
        name_map[n] = fake
        used.add(fake)
    map_path.write_text(json.dumps(name_map, ensure_ascii=False, indent=2), encoding="utf-8")

    pats = build_name_patterns(name_map)
    stats: Counter = Counter()
    name_hits = 0
    out_msgs = []
    for m in msgs:
        m = dict(m)
        if m.get("sender"):
            m["sender"] = name_map.get(m["sender"], m["sender"])
        text = m.get("text", "")
        for pat, fake in pats:
            text, n = pat.subn(fake, text)
            name_hits += n
        if not args.no_pii:
            text = mask_pii(text, stats)
        m["text"] = text
        out_msgs.append(m)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for m in out_msgs:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    # meta 파일이 있으면 발신자 통계도 가명으로 바꿔 복사
    meta_in = Path(args.inp + ".meta.json")
    if meta_in.exists():
        meta = json.loads(meta_in.read_text(encoding="utf-8"))
        meta["senders"] = {name_map.get(k, k): v for k, v in meta.get("senders", {}).items()}
        meta["pseudonymized"] = True
        Path(str(out) + ".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[mask] {len(out_msgs):,}건 → {out}", file=sys.stderr)
    print(f"  가명화 대상 {len(name_map)}명 (매핑표: {map_path}) / 본문 내 이름 치환 {name_hits}회", file=sys.stderr)
    print(f"  PII 마스킹: {dict(stats) or '없음'}", file=sys.stderr)
    print("  ⚠ 별명/초성(예: 철수형→'철수'는 잡히지만 'ㅊㅅ'는 안 잡힘)과 주소는 자동으로 못 잡는다. "
          "grep 으로 한 번 훑어보고 --extra-names 로 보강할 것.", file=sys.stderr)


if __name__ == "__main__":
    main()
