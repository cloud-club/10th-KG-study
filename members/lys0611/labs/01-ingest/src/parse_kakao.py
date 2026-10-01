#!/usr/bin/env python3
"""카카오톡 '대화 내보내기' 파일을 메시지 JSONL로 변환한다.

지원 형식 (자동 감지)
  windows : [이름] [오후 3:15] 메시지
            날짜 구분선  --------------- 2024년 1월 1일 월요일 ---------------
  android : 2024년 1월 1일 오후 3:15, 이름 : 메시지
            (이름 없이 날짜/시간만 있는 줄은 날짜 구분선, 이름 없이 문장만 있으면 시스템 메시지)
  ios/mac : 2024. 1. 1. 오후 3:15, 이름 : 메시지   (24시간제 "15:15" 도 허용)
            날짜 구분선  2024년 1월 1일 월요일
  csv     : Date,User,Message 헤더의 CSV (안드로이드 '모든 메시지 내부저장소에 저장')

사용법
  python src/parse_kakao.py "data/raw/여행모임*.txt" --room 여행모임 --out data/interim/여행모임.jsonl

출력
  <out>            메시지 1건 = JSON 1줄 (seq, sent_at, sender, msg_type, text, line_no, source_file)
  <out>.meta.json  방 이름, 감지된 형식, 파일 목록, 통계
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------- 줄 패턴
RE_WIN_DATE = re.compile(r"^-{5,}\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*\S요일\s*-{5,}\s*$")
RE_WIN_MSG = re.compile(
    r"^\[(?P<name>[^\]]+)\]\s*\[(?P<ampm>오전|오후)\s*(?P<h>\d{1,2}):(?P<m>\d{2})\]\s?(?P<text>.*)$"
)
RE_AND_PREF = re.compile(
    r"^(?P<y>\d{4})년\s*(?P<mo>\d{1,2})월\s*(?P<d>\d{1,2})일\s*(?P<ampm>오전|오후)\s*"
    r"(?P<h>\d{1,2}):(?P<m>\d{2})(?P<rest>.*)$"
)
RE_IOS_PREF = re.compile(
    r"^(?P<y>\d{4})\.\s*(?P<mo>\d{1,2})\.\s*(?P<d>\d{1,2})\.\s*(?:(?P<ampm>오전|오후)\s*)?"
    r"(?P<h>\d{1,2}):(?P<m>\d{2})(?P<rest>.*)$"
)
RE_DATE_ONLY = re.compile(r"^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*\S요일\s*$")
RE_REST_MSG = re.compile(r"^,\s*(?P<name>.+?)\s:\s?(?P<text>.*)$")
RE_SAVED = re.compile(r"^저장한 날짜\s*:\s*(.+)$")
RE_SYSTEM_LINE = re.compile(
    r"^\S.*(님이 들어왔습니다|님이 나갔습니다|님을 초대했습니다|님을 내보냈습니다|님이 .+님을 초대했습니다)\.?$"
)

MEDIA_EXACT = {"사진", "동영상", "이모티콘", "음성메시지", "보이스톡 해요", "페이스톡 해요",
               "라이브톡", "연락처", "지도", "선물", "음성 메시지"}
RE_MEDIA = re.compile(
    r"^(사진 \d+장|동영상 \d+개|파일: .+|\S+\.(jpe?g|png|gif|mp4|mov|pdf|docx?|xlsx?|pptx?|zip|hwpx?|txt))$",
    re.I,
)
RE_URL_ONLY = re.compile(r"^https?://\S+$")
DELETED = {"삭제된 메시지입니다.", "삭제된 메시지입니다", "이 메시지는 삭제되었습니다."}

DT_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M",
              "%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]


def to_24h(ampm: str | None, h) -> int:
    h = int(h)
    if ampm == "오전":
        return 0 if h == 12 else h
    if ampm == "오후":
        return 12 if h == 12 else h + 12
    return h  # 24시간제


def classify(text: str) -> str:
    t = text.strip()
    if not t:
        return "empty"
    if t in DELETED:
        return "deleted"
    if t in MEDIA_EXACT or RE_MEDIA.match(t):
        return "media"
    if RE_URL_ONLY.match(t):
        return "link"
    return "text"


def read_lines(path: Path) -> list[str]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return raw.decode(enc).splitlines()
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 알 수 없습니다: {path}")


def detect_format(lines: list[str]) -> str:
    scores = {"windows": 0, "android": 0, "ios": 0}
    for line in lines[:500]:
        if RE_WIN_MSG.match(line):
            scores["windows"] += 1
        elif RE_AND_PREF.match(line):
            scores["android"] += 1
        elif RE_IOS_PREF.match(line):
            scores["ios"] += 1
    fmt = max(scores, key=scores.get)
    if scores[fmt] == 0:
        head = "\n".join(lines[:15])
        raise SystemExit("형식을 인식하지 못했습니다. 파일 앞부분을 확인해 주세요:\n" + head)
    return fmt


class TxtParser:
    def __init__(self, fmt: str, source: str):
        self.fmt = fmt
        self.source = source
        self.msgs: list[dict] = []
        self.cur: dict | None = None
        self.cur_date: tuple[int, int, int] | None = None
        self.saved_at: str | None = None
        self.room_title: str | None = None

    # -- 버퍼 관리
    def flush(self):
        if self.cur is None:
            return
        self.cur["text"] = self.cur["text"].rstrip()
        if self.cur["msg_type"] == "text":
            self.cur["msg_type"] = classify(self.cur["text"])
        self.msgs.append(self.cur)
        self.cur = None

    def start(self, dt: datetime, sender: str | None, text: str, msg_type: str, line_no: int):
        self.flush()
        self.cur = {"sent_at": dt, "sender": sender, "text": text, "msg_type": msg_type,
                    "line_no": line_no, "source_file": self.source}

    def cont(self, line: str):
        if self.cur is not None:
            self.cur["text"] += "\n" + line

    # -- 줄 처리
    def feed(self, line: str, line_no: int):
        if line_no <= 3:  # 파일 머리: "OOO 님과 카카오톡 대화" / "저장한 날짜 : ..."
            if line.endswith("카카오톡 대화") and self.room_title is None:
                self.room_title = line.strip()
                return
            m = RE_SAVED.match(line)
            if m:
                self.saved_at = m.group(1).strip()
                return
        if self.fmt == "windows":
            return self._feed_windows(line, line_no)
        return self._feed_mobile(line, line_no)

    def _feed_windows(self, line: str, line_no: int):
        m = RE_WIN_DATE.match(line)
        if m:
            self.flush()
            self.cur_date = (int(m[1]), int(m[2]), int(m[3]))
            return
        m = RE_WIN_MSG.match(line)
        if m and self.cur_date:
            dt = datetime(*self.cur_date, to_24h(m["ampm"], m["h"]), int(m["m"]))
            self.start(dt, m["name"].strip(), m["text"], "text", line_no)
            return
        if self.cur_date and RE_SYSTEM_LINE.match(line):
            # 윈도우 시스템 줄에는 시각이 없다 → 직전 메시지 시각(같은 날이면)을 빌려 쓴다
            prev = self.cur["sent_at"] if self.cur else None
            dt = prev if prev and prev.date() == datetime(*self.cur_date).date() else datetime(*self.cur_date)
            self.start(dt, None, line.strip(), "system", line_no)
            self.flush()
            return
        self.cont(line)

    def _feed_mobile(self, line: str, line_no: int):
        pref = RE_AND_PREF if self.fmt == "android" else RE_IOS_PREF
        m = pref.match(line)
        if m:
            dt = datetime(int(m["y"]), int(m["mo"]), int(m["d"]), to_24h(m["ampm"], m["h"]), int(m["m"]))
            rest = m["rest"]
            mm = RE_REST_MSG.match(rest)
            if mm:
                self.start(dt, mm["name"].strip(), mm["text"], "text", line_no)
                return
            body = rest.strip(" ,")
            if body:  # "2024년 1월 1일 오후 3:15, 홍길동님이 들어왔습니다." 같은 시스템 메시지
                self.start(dt, None, body, "system", line_no)
                self.flush()
                return
            self.flush()  # 날짜/시간만 있는 구분선
            return
        if RE_DATE_ONLY.match(line):
            self.flush()
            return
        if RE_SYSTEM_LINE.match(line) and self.cur is not None:
            self.start(self.cur["sent_at"], None, line.strip(), "system", line_no)
            self.flush()
            return
        self.cont(line)


def parse_txt(path: Path) -> tuple[list[dict], dict]:
    lines = read_lines(path)
    fmt = detect_format(lines)
    p = TxtParser(fmt, path.name)
    for i, line in enumerate(lines, start=1):
        p.feed(line, i)
    p.flush()
    return p.msgs, {"format": fmt, "room_title": p.room_title, "saved_at": p.saved_at}


def parse_dt_flex(s: str) -> datetime:
    s = s.strip()
    for f in DT_FORMATS:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    m = RE_AND_PREF.match(s) or RE_IOS_PREF.match(s)
    if m:
        return datetime(int(m["y"]), int(m["mo"]), int(m["d"]), to_24h(m["ampm"], m["h"]), int(m["m"]))
    raise SystemExit(f"날짜 형식을 해석할 수 없습니다: {s!r}")


def parse_csv(path: Path) -> tuple[list[dict], dict]:
    msgs = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = {c.strip().lower(): c for c in (reader.fieldnames or [])}
        dcol, ucol, mcol = cols.get("date"), cols.get("user"), cols.get("message")
        if not (dcol and ucol and mcol):
            raise SystemExit(f"CSV 헤더가 Date,User,Message 형태가 아닙니다: {reader.fieldnames}")
        for i, row in enumerate(reader, start=2):
            text = (row[mcol] or "").strip()
            sender = (row[ucol] or "").strip() or None
            msgs.append({"sent_at": parse_dt_flex(row[dcol]), "sender": sender, "text": text,
                         "msg_type": classify(text) if sender else "system",
                         "line_no": i, "source_file": path.name})
    return msgs, {"format": "csv", "room_title": None, "saved_at": None}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="txt/csv 경로 또는 glob 패턴 (여러 개 가능, 분할 파일 지원)")
    ap.add_argument("--room", required=True, help="방 이름 (DB의 rooms.name 이 된다)")
    ap.add_argument("--out", required=True, help="출력 JSONL 경로")
    args = ap.parse_args()

    files: list[Path] = []
    for pat in args.inputs:
        hits = sorted(glob.glob(pat))
        if not hits and Path(pat).exists():
            hits = [pat]
        files.extend(Path(h) for h in hits)
    if not files:
        raise SystemExit(f"입력 파일이 없습니다: {args.inputs}")

    all_msgs: list[dict] = []
    formats, saved = set(), None
    for fp in files:
        msgs, info = parse_csv(fp) if fp.suffix.lower() == ".csv" else parse_txt(fp)
        formats.add(info["format"])
        saved = saved or info["saved_at"]
        print(f"[parse] {fp.name}: {len(msgs):,}건 ({info['format']})", file=sys.stderr)
        all_msgs.extend(msgs)

    all_msgs.sort(key=lambda m: m["sent_at"])  # 안정 정렬: 같은 분 안에서는 원래 순서 유지
    for seq, m in enumerate(all_msgs, start=1):
        m["seq"] = seq
        m["sent_at"] = m["sent_at"].isoformat()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for m in all_msgs:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    types = Counter(m["msg_type"] for m in all_msgs)
    senders = Counter(m["sender"] for m in all_msgs if m["sender"])
    meta = {
        "room": args.room,
        "formats": sorted(formats),
        "files": [fp.name for fp in files],
        "saved_at": saved,
        "n_messages": len(all_msgs),
        "first_at": all_msgs[0]["sent_at"] if all_msgs else None,
        "last_at": all_msgs[-1]["sent_at"] if all_msgs else None,
        "msg_types": dict(types),
        "senders": dict(senders.most_common()),
    }
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[done] {len(all_msgs):,}건 → {out}", file=sys.stderr)
    print(f"  기간: {meta['first_at']} ~ {meta['last_at']}", file=sys.stderr)
    print(f"  유형: {dict(types)}", file=sys.stderr)
    print(f"  발신자 상위: {senders.most_common(8)}", file=sys.stderr)
    print("  샘플:", file=sys.stderr)
    for m in [x for x in all_msgs if x["msg_type"] == "text"][:3]:
        print(f"    {m['sent_at']} | {m['sender']} | {m['text'][:60]!r}", file=sys.stderr)


if __name__ == "__main__":
    main()
