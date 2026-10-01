#!/usr/bin/env python3
"""OpenDART 원문에서 검색 주제와 가까운 구간을 추출한다."""

import html
import io
import json
import os
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
CONFIG = Path(__file__).resolve().parents[1] / "config" / "dart_filings.json"
OUTPUT = ROOT / "data" / "do-dop" / "company-analysis-kg" / "raw" / "dart" / "documents.jsonl"
KEYWORDS = ("HBM", "고대역폭", "AI", "인공지능", "반도체", "투자", "시설투자", "매출", "영업이익", "메모리")


def load_env() -> None:
    """루트 .env의 단순 KEY=VALUE 항목을 환경변수로 읽는다."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def download_xml(api_key: str, receipt_no: str) -> str:
    """공시 원문 ZIP을 내려받아 안쪽 XML을 문자열로 반환한다."""
    query = urllib.parse.urlencode({"crtfc_key": api_key, "rcept_no": receipt_no})
    request = urllib.request.Request(
        "https://opendart.fss.or.kr/api/document.xml?" + query,
        headers={"User-Agent": "KG-study educational collector"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    xml_name = max(archive.namelist(), key=lambda name: archive.getinfo(name).file_size)
    return archive.read(xml_name).decode("utf-8", errors="replace")


def text_blocks(xml: str) -> list[str]:
    """표 셀과 문단 경계를 유지하면서 XML 태그를 제거한다."""
    xml = re.sub(r"</(?:P|TD|TH|TR|TITLE|SECTION|TABLE)>", "\n", xml, flags=re.I)
    xml = re.sub(r"<[^>]+>", " ", xml)
    plain = html.unescape(xml).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in plain.splitlines()]
    return [line for line in lines if len(line) >= 12]


def extract_relevant_section(xml: str, window: int = 6) -> str:
    """키워드 점수가 가장 높은 연속 문단을 하나의 관련 섹션으로 고른다."""
    blocks = text_blocks(xml)
    if not blocks:
        raise ValueError("공시 원문에서 텍스트를 찾지 못했습니다.")

    best_start = 0
    best_score = -1
    for start in range(len(blocks)):
        candidate = " ".join(blocks[start : start + window])
        score = sum(candidate.lower().count(keyword.lower()) for keyword in KEYWORDS)
        if score > best_score:
            best_start, best_score = start, score

    section = "\n".join(blocks[best_start : best_start + window])
    return section[:4000]


def main() -> None:
    load_env()
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        raise SystemExit("루트 .env에 DART_API_KEY를 입력해 주세요.")

    filings = json.loads(CONFIG.read_text(encoding="utf-8"))
    documents = []
    for filing in filings:
        receipt_no = filing["receipt_no"]
        print(f"수집 중: {filing['company']} {filing['title']} ({receipt_no})")
        xml = download_xml(api_key, receipt_no)
        documents.append(
            {
                "id": filing["id"],
                "title": filing["title"],
                "date": f"{receipt_no[:4]}-{receipt_no[4:6]}-{receipt_no[6:8]}",
                "source": "dart",
                "company": [filing["company"]],
                "text": extract_relevant_section(xml),
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}",
                "receipt_no": receipt_no,
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as file:
        for document in documents:
            file.write(json.dumps(document, ensure_ascii=False) + "\n")
    print(f"DART 관련 섹션 {len(documents)}건 저장: {OUTPUT}")


if __name__ == "__main__":
    main()
