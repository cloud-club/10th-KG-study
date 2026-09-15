"""Instagram 프로페셔널 계정의 게시물과 인사이트를 JSONL로 수집한다.

필수 환경 변수:
    INSTAGRAM_API_VERSION
    INSTAGRAM_USER_ID
    INSTAGRAM_ACCESS_TOKEN
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_RAW = REPO_ROOT / "data/kdyann/raw/instagram_media.jsonl"
DEFAULT_PROCESSED = REPO_ROOT / "data/kdyann/processed/instagram_documents.jsonl"
GRAPH_HOST = "graph.instagram.com"
MEDIA_FIELDS = (
    "id,caption,media_type,media_product_type,permalink,timestamp,"
    "username,like_count,comments_count"
)
CORE_METRICS = (
    "reach",
    "views",
    "likes",
    "comments",
    "shares",
    "saved",
    "total_interactions",
)
REELS_METRICS = (
    "ig_reels_avg_watch_time",
    "ig_reels_video_view_total_time",
)
HASHTAG_PATTERN = re.compile(r"(?<!\w)#([0-9A-Za-z_가-힣]+)")


class InstagramAPIError(RuntimeError):
    """Instagram API 요청이 실패했을 때 발생한다."""


def _safe_url(url: str) -> str:
    """페이지네이션 URL에서 토큰을 제거하고 허용된 호스트인지 확인한다."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != GRAPH_HOST:
        raise InstagramAPIError(f"허용되지 않은 API 주소입니다: {parsed.hostname}")

    query = [(key, value) for key, value in parse_qsl(parsed.query) if key != "access_token"]
    return urlunparse(parsed._replace(query=urlencode(query)))


def _request_json(url: str, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    safe_url = _safe_url(url)
    if params:
        parsed = urlparse(safe_url)
        query = dict(parse_qsl(parsed.query))
        query.update({key: str(value) for key, value in params.items()})
        safe_url = urlunparse(parsed._replace(query=urlencode(query)))

    request = Request(
        safe_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "kg-study-instagram-collector/1.0",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        try:
            payload = json.loads(error.read().decode("utf-8"))
            message = payload.get("error", {}).get("message", "알 수 없는 API 오류")
        except (UnicodeDecodeError, json.JSONDecodeError):
            message = f"HTTP {error.code}"
        raise InstagramAPIError(f"Instagram API 요청 실패: {message}") from error
    except URLError as error:
        raise InstagramAPIError(f"Instagram API에 연결할 수 없습니다: {error.reason}") from error


def fetch_media(base_url: str, user_id: str, token: str, max_posts: int) -> list[dict[str, Any]]:
    url = f"{base_url}/{user_id}/media"
    params: dict[str, Any] | None = {"fields": MEDIA_FIELDS, "limit": min(max_posts, 100)}
    media: list[dict[str, Any]] = []

    while url and len(media) < max_posts:
        payload = _request_json(url, token, params)
        media.extend(payload.get("data", []))
        next_url = payload.get("paging", {}).get("next")
        url = _safe_url(next_url) if next_url else ""
        params = None

    return media[:max_posts]


def _metric_value(metric: dict[str, Any]) -> int | float | None:
    total_value = metric.get("total_value", {}).get("value")
    if isinstance(total_value, (int, float)):
        return total_value

    values = metric.get("values", [])
    if values and isinstance(values[0].get("value"), (int, float)):
        return values[0]["value"]
    return None


def _parse_metrics(payload: dict[str, Any]) -> dict[str, int | float]:
    result: dict[str, int | float] = {}
    for metric in payload.get("data", []):
        value = _metric_value(metric)
        if value is not None and metric.get("name"):
            result[metric["name"]] = value
    return result


def fetch_insights(base_url: str, media: dict[str, Any], token: str) -> dict[str, int | float]:
    metrics = list(CORE_METRICS)
    if media.get("media_product_type") == "REELS":
        metrics.extend(REELS_METRICS)

    url = f"{base_url}/{media['id']}/insights"
    try:
        return _parse_metrics(_request_json(url, token, {"metric": ",".join(metrics)}))
    except InstagramAPIError:
        # 미디어 유형에 지원되지 않는 지표 하나가 섞이면 묶음 요청 전체가 실패할
        # 수 있으므로, 개별 요청으로 다시 시도해 지원되는 값만 남긴다.
        result: dict[str, int | float] = {}
        for metric in metrics:
            try:
                payload = _request_json(url, token, {"metric": metric})
                result.update(_parse_metrics(payload))
            except InstagramAPIError:
                continue
        return result


def _number(metrics: dict[str, Any], key: str) -> float:
    value = metrics.get(key, 0)
    return float(value) if isinstance(value, (int, float)) else 0.0


def normalize(record: dict[str, Any], collected_at: str) -> dict[str, Any] | None:
    media = record["media"]
    caption = (media.get("caption") or "").strip()
    if not caption:
        return None

    metrics = dict(record.get("insights", {}))
    metrics.setdefault("likes", media.get("like_count", 0))
    metrics.setdefault("comments", media.get("comments_count", 0))

    reach = _number(metrics, "reach")
    engagement = sum(_number(metrics, key) for key in ("likes", "comments", "saved", "shares"))
    rates = {
        "engagement_rate": engagement / reach if reach else None,
        "save_rate": _number(metrics, "saved") / reach if reach else None,
        "share_rate": _number(metrics, "shares") / reach if reach else None,
    }

    return {
        "id": media["id"],
        "source": "instagram",
        "text": caption,
        "hashtags": HASHTAG_PATTERN.findall(caption),
        "media_type": media.get("media_type"),
        "media_product_type": media.get("media_product_type"),
        "permalink": media.get("permalink"),
        "published_at": media.get("timestamp"),
        "collected_at": collected_at,
        "metrics": metrics,
        "rates": rates,
    }


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            for row in rows:
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    temporary.replace(path)
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Instagram 게시물과 인사이트를 JSONL로 수집")
    parser.add_argument("--max-posts", type=int, default=100)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--processed-output", type=Path, default=DEFAULT_PROCESSED)
    return parser.parse_args()


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"환경 변수 {name} 값이 필요합니다.")
    return value


def main() -> int:
    args = parse_args()
    if args.max_posts < 1:
        print("--max-posts는 1 이상이어야 합니다.", file=sys.stderr)
        return 2

    try:
        api_version = required_env("INSTAGRAM_API_VERSION")
        user_id = required_env("INSTAGRAM_USER_ID")
        token = required_env("INSTAGRAM_ACCESS_TOKEN")
        if not re.fullmatch(r"v\d+\.\d+", api_version):
            raise ValueError("INSTAGRAM_API_VERSION은 v24.0 같은 형식이어야 합니다.")
        if not user_id.isdigit():
            raise ValueError("INSTAGRAM_USER_ID는 숫자 형식이어야 합니다.")

        base_url = f"https://{GRAPH_HOST}/{api_version}"
        media_items = fetch_media(base_url, user_id, token, args.max_posts)
        collected_at = datetime.now(timezone.utc).isoformat()

        raw_rows = []
        for index, media in enumerate(media_items, start=1):
            print(f"[{index}/{len(media_items)}] {media['id']} 인사이트 수집")
            raw_rows.append({"media": media, "insights": fetch_insights(base_url, media, token)})

        raw_count = write_jsonl(args.raw_output, raw_rows)
        documents = [document for row in raw_rows if (document := normalize(row, collected_at))]
        processed_count = write_jsonl(args.processed_output, documents)
    except (InstagramAPIError, ValueError, OSError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1

    print(f"원본 {raw_count}건 저장: {args.raw_output}")
    print(f"검색 문서 {processed_count}건 저장: {args.processed_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
