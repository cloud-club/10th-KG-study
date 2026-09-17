"""공식 해시태그 후보 중 24시간 이상·좋아요 1,000개 이상인 게시물을 추천한다."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from instagram_common import HASHTAG_PATTERN, REPO_ROOT, required_env, write_jsonl
from fetch_reference_instagram import GRAPH_HOST, ReferenceAPIError, _request_json, check_access

DEFAULT_HASHTAGS = ["reels", "fyp", "coding", "AI", "개발"]
MAX_SELECTION_COUNT = 10
RRF_K = 60
MIN_AGE_HOURS = 24
MIN_LIKES = 1000
MEDIA_FIELDS = "id,caption,media_type,permalink,timestamp,like_count,comments_count"
RAW_PATH = REPO_ROOT / "data/kdyann/raw/instagram_topic_media.jsonl"
DOCUMENTS_PATH = REPO_ROOT / "data/kdyann/processed/instagram_topic_documents.jsonl"
SELECTED_PATH = REPO_ROOT / "data/kdyann/processed/instagram_topic_selected.jsonl"


def valid_permalink(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return (parsed.scheme == "https" and parsed.netloc in {"instagram.com", "www.instagram.com"}
            and not parsed.username and not parsed.password and not parsed.fragment
            and bool(re.fullmatch(r"/(?:p|reel|tv)/[A-Za-z0-9_-]+/?", parsed.path)))


def fetch_topics(base_url: str, user_id: str, token: str, hashtags: list[str],
                 max_candidates: int) -> list[dict[str, Any]]:
    """최대 1페이지/edge/tag만 요청하여 탐색 요청량을 제한한다."""
    if not 1 <= max_candidates <= 50:
        raise ValueError("--max-candidates는 1~50 사이여야 합니다.")
    rows: dict[str, dict[str, Any]] = {}
    for hashtag in hashtags:
        payload = _request_json(f"{base_url}/ig_hashtag_search", token,
                                {"user_id": user_id, "q": hashtag})
        data = payload.get("data")
        if not isinstance(data, list):
            raise ReferenceAPIError("해시태그 검색 응답 형식이 올바르지 않습니다.")
        if not data:
            continue
        hashtag_id = str(data[0].get("id", "")) if isinstance(data[0], dict) else ""
        if not hashtag_id.isdigit():
            raise ReferenceAPIError("해시태그 ID를 확인하지 못했습니다.")
        for edge in ("top_media", "recent_media"):
            page = _request_json(f"{base_url}/{hashtag_id}/{edge}", token,
                                 {"user_id": user_id, "fields": MEDIA_FIELDS,
                                  "limit": max_candidates})
            if not isinstance(page.get("data"), list):
                raise ReferenceAPIError("해시태그 게시물 응답 형식이 올바르지 않습니다.")
            for media in page["data"][:max_candidates]:
                if not isinstance(media, dict) or not media.get("id"):
                    raise ReferenceAPIError("게시물 ID를 확인하지 못했습니다.")
                identifier = str(media["id"])
                source = {"hashtag": hashtag, "hashtag_id": hashtag_id, "edge": edge}
                row = rows.setdefault(identifier, {"media": {}, "discovery": []})
                row["media"].update({key: media[key] for key in MEDIA_FIELDS.split(",") if key in media})
                if source not in row["discovery"]:
                    row["discovery"].append(source)
    return list(rows.values())


def normalize_topic(row: dict[str, Any], collected_at: str) -> dict[str, Any] | None:
    media = row["media"]
    caption = media.get("caption")
    if not isinstance(caption, str) or not caption.strip():
        return None
    metrics = {}
    for field, label in (("like_count", "likes"), ("comments_count", "comments")):
        value = media.get(field)
        if valid_count(value):
            metrics[label] = value
    return {"id": str(media["id"]), "source": "instagram", "source_type": "topic",
            "text": caption.strip(), "hashtags": HASHTAG_PATTERN.findall(caption),
            "media_type": media.get("media_type"), "permalink": media.get("permalink"),
            "published_at": media.get("timestamp"), "collected_at": collected_at,
            "metrics": metrics, "discovery": row["discovery"]}


def valid_count(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and value >= 0 and (not isinstance(value, float) or math.isfinite(value)))


def observed_count(document: dict[str, Any], name: str) -> int | float | None:
    metrics = document.get("metrics")
    value = metrics.get(name) if isinstance(metrics, dict) else None
    return value if valid_count(value) else None


def publication_time(document: dict[str, Any]) -> datetime | None:
    value = document.get("published_at")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except ValueError:
        return None


def select_documents(documents: list[dict[str, Any]], now: datetime, count: int,
                     max_age_days: int) -> list[dict[str, Any]]:
    """기간·좋아요 조건을 만족한 후보의 좋아요와 관측 댓글 순위를 RRF로 합친다."""
    if not 1 <= count <= MAX_SELECTION_COUNT:
        raise ValueError(f"추천 상한은 1~{MAX_SELECTION_COUNT} 사이여야 합니다.")
    eligible = []
    for document in documents:
        if not valid_permalink(document.get("permalink")):
            continue
        stamp = publication_time(document)
        if (stamp is None or stamp > now - timedelta(hours=MIN_AGE_HOURS)
                or stamp < now - timedelta(days=max_age_days)):
            continue
        likes = observed_count(document, "likes")
        if likes is None or likes < MIN_LIKES:
            continue
        eligible.append(document)
    likes_order = sorted(eligible, key=lambda row: (-observed_count(row, "likes"), row["id"]))
    comments_order = sorted((row for row in eligible if observed_count(row, "comments") is not None),
                            key=lambda row: (-observed_count(row, "comments"), row["id"]))
    likes_ranks = {row["id"]: rank for rank, row in enumerate(likes_order, 1)}
    comments_ranks = {row["id"]: rank for rank, row in enumerate(comments_order, 1)}
    scores = {row["id"]: 1 / (RRF_K + likes_ranks[row["id"]])
              + (1 / (RRF_K + comments_ranks[row["id"]]) if row["id"] in comments_ranks else 0)
              for row in eligible}
    result = sorted(eligible, key=lambda row: (-scores[row["id"]], row["id"]))[:count]
    return [{**row, "selection": {"method": "likes_comments_rrf", "score": scores[row["id"]],
                                  "k": RRF_K, "likes_rank": likes_ranks[row["id"]],
                                  "comments_rank": comments_ranks.get(row["id"]),
                                  "min_age_hours": MIN_AGE_HOURS, "min_likes": MIN_LIKES,
                                  "max_age_days": max_age_days,
                                  "observed_likes": observed_count(row, "likes"),
                                  "observed_comments": observed_count(row, "comments")}}
            for row in result]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] for row in rows):
        raise ValueError("기존 후보 코퍼스 형식이 올바르지 않습니다. 저장하지 않았습니다.")
    return rows


def merge_documents(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {row["id"]: row for row in previous}
    for row in current:
        old = merged.get(row["id"], {})
        discovery = list(old.get("discovery", []))
        discovery.extend(source for source in row["discovery"] if source not in discovery)
        merged[row["id"]] = {**row, "discovery": discovery}
    return sorted(merged.values(), key=lambda row: row["id"])


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="해시태그 후보 수집; 24시간 이상·좋아요 1,000개 이상을 좋아요/댓글 순위 RRF로 최대 10개 추천")
    parser.add_argument("--hashtag", action="append", help="탐색 해시태그; 여러 번 지정 가능")
    parser.add_argument("--max-candidates", type=int, default=25, help="해시태그/edge당 1페이지 상한 (1~50)")
    parser.add_argument("--count", type=int, default=MAX_SELECTION_COUNT, help="추천 상한 (1~10, 기본 10)")
    parser.add_argument("--max-age-days", type=int, default=7, help="추천 대상 작성 시각의 최대 나이")
    parser.add_argument("--check-access", action="store_true", help="권한·계정만 점검; 수집 접근은 별도 검증")
    parser.add_argument("--list-linked-accounts", action="store_true", help="Facebook 페이지명·연결된 Instagram ID만 확인")
    args = parser.parse_args(argv)
    args.hashtag = list(dict.fromkeys(tag.strip().removeprefix("#") for tag in (args.hashtag or DEFAULT_HASHTAGS)))
    if not 1 <= args.max_candidates <= 50 or not 1 <= args.count <= MAX_SELECTION_COUNT or args.max_age_days < 1:
        parser.error("후보 상한 1~50, 추천 상한 1~10, 최대 나이 1일 이상이어야 합니다.")
    if len(args.hashtag) > 10 or any(not re.fullmatch(r"[\w가-힣]{1,100}", tag) for tag in args.hashtag):
        parser.error("해시태그는 # 없이 단어로, 최대 10개 지정하세요.")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        version, token = (required_env(name) for name in ("INSTAGRAM_API_VERSION", "FACEBOOK_ACCESS_TOKEN"))
        if not re.fullmatch(r"v\d+\.\d+", version):
            raise ValueError("API 버전 형식을 확인하세요.")
        base = f"https://{GRAPH_HOST}/{version}"
        if args.list_linked_accounts:
            payload = _request_json(f"{base}/me/accounts", token,
                                    {"fields": "id,name,instagram_business_account", "limit": 100})
            if not isinstance(payload.get("data"), list):
                raise ReferenceAPIError("페이지 목록 응답 형식이 올바르지 않습니다.")
            for page in payload["data"]:
                if isinstance(page, dict) and isinstance(page.get("instagram_business_account"), dict):
                    print("페이지:", page.get("name", ""), "Instagram ID:", page["instagram_business_account"].get("id", ""))
            print("첫 페이지 결과입니다. 연결이 없거나 목록에 없으면 페이지 선택·권한을 확인하세요.")
            return 0
        user_id = required_env("FACEBOOK_INSTAGRAM_USER_ID")
        if not user_id.isdigit():
            raise ValueError("Facebook Login Instagram 계정 ID 형식을 확인하세요.")
        if args.check_access:
            summary = check_access(base, user_id, token)
            print("요청 계정:", summary["requesting_account"])
            print("승인 권한:", ", ".join(summary["granted_permissions"]))
            print("해시태그 접근 검증은 실제 수집 요청으로 별도 확인해야 합니다.")
            return 0
        now = datetime.now(timezone.utc)
        rows = fetch_topics(base, user_id, token, args.hashtag, args.max_candidates)
        for row in rows:
            row["collected_at"] = now.isoformat()
        documents = [doc for row in rows if (doc := normalize_topic(row, now.isoformat()))]
        accumulated = merge_documents(read_jsonl(DOCUMENTS_PATH), documents)
        selected = select_documents(documents, now, args.count, args.max_age_days)
        # 조회·정규화·기존 데이터 읽기가 모두 성공한 뒤 별도 결과를 저장한다.
        write_jsonl(RAW_PATH, rows)
        write_jsonl(DOCUMENTS_PATH, accumulated)
        write_jsonl(SELECTED_PATH, selected)
    except (ReferenceAPIError, ValueError, OSError) as error:
        message = str(error) if isinstance(error, ReferenceAPIError) else "설정 또는 데이터 형식을 확인하세요. 수집 결과를 생성하지 못했습니다."
        print("오류:", message, file=sys.stderr)
        return 1
    print(f"이번 후보 {len(documents)}건, 누적 {len(accumulated)}건, 추천 {len(selected)}건")
    print(f"추천 파일: {SELECTED_PATH}")
    print("추천은 24시간 이상·좋아요 1,000개 이상인 후보의 좋아요/댓글 순위 RRF입니다. 전체 Instagram 인기 순위가 아닙니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
