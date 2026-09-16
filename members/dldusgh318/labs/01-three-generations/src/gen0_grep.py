"""0세대: grep

저장 구조랄 게 없다. 그게 요점이다.
- 저장 단위: 파일 안의 한 줄
- 스키마: 없음
- 인덱스: 없음 -> 매 쿼리마다 전체 스캔 O(n)
- 랭킹: 없음(이진). 매칭되거나 아니거나

`python src/gen0_grep.py --stats` 로 "적재된 것"의 실체를 확인하고,
`python src/gen0_grep.py 학교` 로 검색한다.
"""
import shutil
import subprocess
import sys
import time

from common import RAW

# ripgrep이 있으면 쓴다. 더 빠를 뿐 하는 일은 같다(여전히 인덱스 없는 스캔).
GREP = "rg" if shutil.which("rg") else "grep"


def stats() -> None:
    files = sorted(RAW.glob("*.md"))
    total = sum(f.stat().st_size for f in files)
    lines = sum(f.read_text(encoding="utf-8", errors="replace").count("\n") for f in files)
    print("[0세대 grep] 저장 구조")
    print(f"  위치      : {RAW}")
    print(f"  문서      : {len(files)}개")
    print(f"  총 크기   : {total/1024/1024:.2f} MB")
    print(f"  라인      : {lines:,}줄  <- 사실상의 '레코드' 단위")
    print("  스키마    : 없음")
    print("  인덱스    : 없음 (쿼리마다 위 전체를 다시 읽는다)")
    print(f"  검색 도구 : {GREP}")


def search(query: str, limit: int = 5):
    """매칭된 라인을 반환한다. 순서는 파일명 순 — 관련도 순이 아니다."""
    cmd = ([GREP, "-n", "--no-heading", "--color=never", query, str(RAW)]
           if GREP == "rg" else
           [GREP, "-rn", query, str(RAW)])
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.perf_counter() - t0

    # collect_notion.py가 각 파일 맨 위에 심어 둔 <!--meta ...--> 줄은
    # 코퍼스 내용이 아니라 파이프라인이 만든 부산물이다. 검색 결과에서 뺀다.
    hits = [l for l in proc.stdout.splitlines()
            if l.strip() and "<!--meta " not in l]
    return hits[:limit], len(hits), elapsed


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] == "--stats":
        stats()
        return
    query = sys.argv[1]
    hits, total, elapsed = search(query)
    print(f'[0세대] "{query}" — {total}건 / {elapsed*1000:.0f}ms (전체 스캔, 순위 없음)')
    if not hits:
        print("  (없음) 표현이 한 글자만 달라도 못 찾는다.")
    for h in hits:
        # 긴 절대경로가 정작 중요한 본문을 밀어내지 않게 파일명만 남긴다.
        path, _, rest = h.partition(":")
        lineno, _, body = rest.partition(":")
        name = path.rsplit("/", 1)[-1]
        # 매칭된 부분이 줄 뒤쪽에 있으면 그 앞을 잘라내 보이게 한다.
        idx = body.find(query)
        if idx > 50:
            body = "…" + body[idx - 20:]
        print(f"  {name}:{lineno}")
        print(f"      {body.strip()[:100]}")


if __name__ == "__main__":
    main()
