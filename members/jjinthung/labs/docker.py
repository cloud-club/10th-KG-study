#!/usr/bin/env python3
"""Docker Compose로 Nori Elasticsearch를 시작하고 준비 상태를 확인합니다."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def wait_for_elasticsearch(url: str, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    health_url = f"{url.rstrip('/')}/_cluster/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=5) as response:
                health = json.load(response)
            if health.get("status") in {"green", "yellow"}:
                print(f"Elasticsearch 준비 완료: {url}")
                return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(2)
    raise RuntimeError(
        f"Elasticsearch가 {timeout}초 안에 준비되지 않았습니다: {health_url}"
    )


def is_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(
            f"{url.rstrip('/')}/_cluster/health", timeout=3
        ) as response:
            return json.load(response).get("status") in {"green", "yellow"}
    except (urllib.error.URLError, TimeoutError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Docker Compose로 Elasticsearch(Nori)를 시작합니다."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Elasticsearch 준비 대기 시간(초)",
    )
    parser.add_argument("--url", default="http://localhost:9200")
    args = parser.parse_args()

    if shutil.which("docker") is None:
        raise RuntimeError(
            "docker 명령을 찾을 수 없습니다. Docker Desktop을 설치하고 실행한 뒤 "
            "새 VS Code 터미널을 열어 다시 실행하세요."
        )

    labs_dir = Path(__file__).resolve().parent
    compose_file = labs_dir / "docker-compose.yml"
    if not compose_file.exists():
        raise FileNotFoundError(f"docker-compose.yml을 찾을 수 없습니다: {compose_file}")

    if is_ready(args.url):
        print(f"이미 실행 중인 Elasticsearch를 재사용합니다: {args.url}")
    else:
        try:
            subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(compose_file),
                    "up",
                    "-d",
                    "elasticsearch",
                ],
                cwd=labs_dir,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            if not is_ready(args.url):
                raise error
            print(f"기존 Elasticsearch를 재사용합니다: {args.url}")
    wait_for_elasticsearch(args.url, args.timeout)
    print("다음 명령으로 Nori BM25 인덱스를 생성하세요:")
    print(f"{sys.executable} labs\\01-bm25\\index.py")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"실행 실패: {error}", file=sys.stderr)
        raise SystemExit(1) from error
