"""노션 Export(zip) -> data/raw/*.md

노션이 뱉는 파일명에는 32자리 hex ID가 붙어 있고 폴더 구조도 그대로 따라온다.
    "온톨로지 스터디 3d32fc180e8980ba8d58c5f43510219a/스터디 2주차 3d32....md"
검색 실습에서 이 ID는 노이즈일 뿐이라 벗겨내고, 대신 원래 경로를 문서 맨 위
프론트매터에 남긴다. (1·2세대에서 메타데이터 필터를 붙일 때 쓸 재료)

사용:
    python src/collect_notion.py ~/Downloads/Export-xxxx.zip
"""
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

from common import RAW

NOTION_ID = re.compile(r"\s+[0-9a-f]{32}(?=\.|/|$)")


def clean(path: str) -> str:
    """경로에서 노션 ID를 제거한다."""
    return NOTION_ID.sub("", path)


def slug(path: str) -> str:
    """중첩 경로를 파일명 하나로 눕힌다. 계층은 '__'로 보존."""
    p = Path(path)
    parts = list(p.parent.parts) + [p.stem]
    joined = "__".join(parts)
    return re.sub(r"[^\w가-힣.\-]+", "_", joined)[:180] + ".md"


def main(zip_path: Path) -> None:
    written = skipped = 0
    seen: dict[str, int] = {}   # 서로 다른 경로가 같은 슬러그로 눕는 걸 막는다
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir() or not info.filename.endswith(".md"):
                skipped += 1
                continue
            # 파일명 인코딩: zip이 UTF-8 플래그를 안 세우면 zipfile이 cp437로
            # 잘못 디코드해 둔다. 그때만 되돌린다.
            name = info.filename
            if not info.flag_bits & 0x800:
                name = name.encode("cp437", "replace").decode("utf-8", "replace")
            # 맥에서 만든 export는 한글이 NFD(자소 분리)로 들어온다. 그대로 두면
            # "학교"가 "ㅎㅏㄱㄱㅛ"로 쪼개져 grep부터 전부 어긋난다.
            name = unicodedata.normalize("NFC", name)

            body = unicodedata.normalize("NFC", z.read(info).decode("utf-8", "replace"))
            if not body.strip():
                skipped += 1
                continue

            rel = clean(name)
            # "캐시.md"처럼 다른 폴더에 같은 제목이 있으면 슬러그가 충돌한다.
            # 그냥 두면 뒤 문서가 앞 문서를 덮어써서 조용히 사라진다.
            base = slug(rel)
            seen[base] = seen.get(base, 0) + 1
            if seen[base] > 1:
                base = f"{base[:-3]}~{seen[base]}.md"
            out = RAW / base
            header = json.dumps({"source": rel}, ensure_ascii=False)
            out.write_text(f"<!--meta {header} -->\n{body}", encoding="utf-8")
            written += 1

    print(f"수집 완료: {written}개 문서 -> {RAW}  (건너뜀 {skipped})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("사용법: python src/collect_notion.py <노션 Export zip 경로>")
    main(Path(sys.argv[1]).expanduser())
