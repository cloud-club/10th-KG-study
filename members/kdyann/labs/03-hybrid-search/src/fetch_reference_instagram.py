"""Facebook Login Business Discovery로 참고 계정의 캡션을 별도 수집한다."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from instagram_common import HASHTAG_PATTERN, REPO_ROOT, required_env, write_jsonl


GRAPH_HOST = "graph.facebook.com"
DEFAULT_RAW = REPO_ROOT / "data/kdyann/raw/instagram_reference_media.jsonl"
DEFAULT_PROCESSED = REPO_ROOT / "data/kdyann/processed/instagram_reference_documents.jsonl"
MEDIA_FIELDS = "id,caption,permalink,timestamp,media_type,like_count,comments_count"
MAX_POSTS = 1000


class ReferenceAPIError(RuntimeError):
    """토큰이나 API 응답 원문을 노출하지 않는 수집 오류."""


def _safe_url(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.netloc != GRAPH_HOST
            or parsed.username or parsed.password or parsed.fragment):
        raise ReferenceAPIError("허용되지 않은 API 주소입니다.")
    query = [(key, value) for key, value in parse_qsl(parsed.query)
             if key.lower() != "access_token"]
    return urlunparse(parsed._replace(query=urlencode(query)))


class _GraphRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, _safe_url(newurl))


urlopen = build_opener(_GraphRedirectHandler()).open


def _request_json(url: str, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if not token or any(character.isspace() for character in token):
        raise ReferenceAPIError("Facebook 토큰 형식이 올바르지 않습니다.")
    safe_url = _safe_url(url)
    if params:
        parsed = urlparse(safe_url)
        query = dict(parse_qsl(parsed.query))
        query.update({key: str(value) for key, value in params.items()})
        safe_url = _safe_url(urlunparse(parsed._replace(query=urlencode(query))))
    request = Request(safe_url, headers={"Authorization": f"Bearer {token}",
                                       "Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as error:
        # Meta의 오류 메시지 및 URL에는 인증 정보가 포함될 수 있으므로 출력하지 않는다.
        raise ReferenceAPIError(f"Facebook Graph API HTTP {error.code}: 토큰·권한·계정 연결을 확인하세요.") from None
    except (URLError, OSError):
        raise ReferenceAPIError("Facebook Graph API에 연결할 수 없습니다.") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ReferenceAPIError("Facebook Graph API 응답이 올바른 JSON이 아닙니다.") from None
    except ValueError:
        raise ReferenceAPIError("Facebook Graph API 요청 형식이 올바르지 않습니다.") from None
    if not isinstance(payload, dict) or "error" in payload:
        raise ReferenceAPIError("Facebook Graph API 응답을 처리할 수 없습니다.")
    return payload


def check_access(base_url: str, user_id: str, token: str) -> dict[str, Any]:
    permissions = _request_json(f"{base_url}/me/permissions", token)
    account = _request_json(f"{base_url}/{user_id}", token, {"fields": "id,username"})
    if str(account.get("id")) != user_id or not account.get("username"):
        raise ReferenceAPIError("요청 Instagram 계정의 id·username을 확인하지 못했습니다.")
    granted = sorted({row["permission"] for row in permissions.get("data", [])
                      if isinstance(row, dict) and row.get("status") == "granted"
                      and isinstance(row.get("permission"), str)})
    return {"granted_permissions": granted, "requesting_account": account["username"]}


def fetch_reference(base_url: str, user_id: str, token: str,
                    username: str, max_posts: int) -> list[dict[str, Any]]:
    if not 1 <= max_posts <= MAX_POSTS:
        raise ValueError(f"--max-posts는 1~{MAX_POSTS} 사이여야 합니다.")
    if not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", username):
        raise ValueError("참고 계정 username 형식이 잘못되었습니다.")
    fields = (f"business_discovery.username({username})"
              f"{{id,username,media.limit({min(max_posts, 100)}){{{MEDIA_FIELDS}}}}}")
    payload = _request_json(f"{base_url}/{user_id}", token, {"fields": fields})
    discovery = payload.get("business_discovery")
    if not isinstance(discovery, dict) or not discovery.get("id") or not discovery.get("username"):
        raise ReferenceAPIError("Business Discovery 계정을 확인하지 못했습니다. 대상 계정 유형·권한을 확인하세요.")
    page = discovery.get("media")
    rows: dict[str, dict[str, Any]] = {}
    visited: set[str] = set()
    # 중복 게시물만 반환되거나 커서가 계속 바뀌는 경우에도 요청 수를 제한한다.
    for _ in range(min(max_posts, 100)):
        if not isinstance(page, dict) or not isinstance(page.get("data"), list):
            raise ReferenceAPIError("게시물 페이지 형식이 올바르지 않습니다.")
        for media in page["data"]:
            if not isinstance(media, dict) or not media.get("id"):
                raise ReferenceAPIError("게시물 ID를 확인하지 못했습니다.")
            rows.setdefault(str(media["id"]), {
                "media": {key: media[key] for key in MEDIA_FIELDS.split(",") if key in media},
                "source_type": "reference", "username": discovery["username"],
                "discovery": {"method": "business_discovery", "account_id": discovery["id"],
                              "requested_username": username, "requesting_account_id": user_id},
            })
            if len(rows) >= max_posts:
                return list(rows.values())
        next_url = page.get("paging", {}).get("next")
        if not next_url:
            return list(rows.values())
        if not isinstance(next_url, str):
            raise ReferenceAPIError("페이지네이션 주소 형식이 올바르지 않습니다.")
        safe_next = _safe_url(next_url)
        if safe_next in visited:
            raise ReferenceAPIError("페이지네이션 주소가 반복되었습니다. 저장하지 않았습니다.")
        visited.add(safe_next)
        page = _request_json(safe_next, token)
        if "business_discovery" in page:
            nested = page["business_discovery"]
            page = nested.get("media") if isinstance(nested, dict) else None
    raise ReferenceAPIError("페이지 요청 한도를 초과했습니다. 저장하지 않았습니다.")


def normalize_reference(row: dict[str, Any], collected_at: str) -> dict[str, Any] | None:
    media = row["media"]
    caption = (media.get("caption") or "").strip()
    if not caption:
        return None
    metrics = {}
    for field, name in (("like_count", "likes"), ("comments_count", "comments")):
        value = media.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[name] = value
    return {
        "id": media["id"], "source": "instagram", "source_type": "reference",
        "username": row["username"], "text": caption,
        "hashtags": HASHTAG_PATTERN.findall(caption), "media_type": media.get("media_type"),
        "permalink": media.get("permalink"), "published_at": media.get("timestamp"),
        "collected_at": collected_at, "metrics": metrics,
        "rates": {"engagement_rate": None, "save_rate": None, "share_rate": None},
        "discovery": row["discovery"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="참고 Instagram 프로페셔널 계정의 캡션을 별도 수집")
    parser.add_argument("--username", action="append", default=[], help="참고 계정 핸들 (여러 번 지정 가능)")
    parser.add_argument("--max-posts", type=int, default=30, help="계정당 수집 상한 (1~1000)")
    parser.add_argument("--check-access", action="store_true", help="Facebook 사용자 토큰 권한·요청 계정만 확인")
    args = parser.parse_args(argv)
    if not args.check_access and not args.username:
        parser.error("수집할 --username을 지정하세요.")
    if not 1 <= args.max_posts <= MAX_POSTS:
        parser.error("--max-posts는 1~1000 사이여야 합니다.")
    args.username = list(dict.fromkeys(name.strip().removeprefix("@").lower() for name in args.username))
    if any(not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", name) for name in args.username):
        parser.error("--username에 계정 핸들만 입력하세요.")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        version = required_env("INSTAGRAM_API_VERSION")
        user_id = required_env("FACEBOOK_INSTAGRAM_USER_ID")
        token = required_env("FACEBOOK_ACCESS_TOKEN")
        if not re.fullmatch(r"v\d+\.\d+", version) or not user_id.isdigit():
            raise ValueError("API 버전은 v24.0 형식, FACEBOOK_INSTAGRAM_USER_ID는 숫자여야 합니다.")
        base_url = f"https://{GRAPH_HOST}/{version}"
        if args.check_access:
            summary = check_access(base_url, user_id, token)
            print("요청 계정:", summary["requesting_account"])
            print("승인된 권한:", ", ".join(summary["granted_permissions"]) or "없음")
            print("사전 점검 완료. 외부 계정 조회 가능 여부는 --username 수집 요청으로 확인하세요.")
            return 0
        rows: dict[str, dict[str, Any]] = {}
        collected_at = datetime.now(timezone.utc).isoformat()
        for username in args.username:
            for row in fetch_reference(base_url, user_id, token, username, args.max_posts):
                row["collected_at"] = collected_at
                rows.setdefault(str(row["media"]["id"]), row)
        documents = [document for row in rows.values()
                     if (document := normalize_reference(row, collected_at))]
        # 모든 계정 수집·정규화가 성공한 후에만 별도 파일을 갱신한다.
        raw_count = write_jsonl(DEFAULT_RAW, rows.values())
        processed_count = write_jsonl(DEFAULT_PROCESSED, documents)
    except (ReferenceAPIError, ValueError, OSError) as error:
        # OS 예외에도 경로나 인증 정보가 포함될 수 있으므로 원문을 출력하지 않는다.
        message = str(error) if isinstance(error, (ReferenceAPIError, ValueError)) else "파일 저장에 실패했습니다."
        print(f"오류: {message}", file=sys.stderr)
        return 1
    print(f"참고 게시물 원본 {raw_count}건: {DEFAULT_RAW}")
    print(f"캡션 검색 문서 {processed_count}건: {DEFAULT_PROCESSED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
