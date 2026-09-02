"""OpenAI API 로 멤버 칭호/요약/태그와 스터디 소식을 만든다. 키가 없으면 규칙 기반 폴백.

환경변수:
    OPENAI_API_KEY   없으면 LLM 호출을 건너뛴다 (빌드는 계속됨)
    OPENAI_MODEL     기본 gpt-5-mini
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-5-mini"
MAX_ITEM_CHARS = 2500
MAX_TAGS = 5
TIMEOUT_SECONDS = 120
RETRY_DELAY_SECONDS = 4

KIND_LABEL = {"note": "노트", "lab": "실습", "streak": "연속 활동", "level": "레벨 업", "join": "합류"}
FEED_TEMPLATES = {
    "note": "🎙️ {member} 선수, '{title}' 노트 제출! 지식그래프에 새 노드가 추가됩니다.",
    "lab": "{member} 선수, '{title}' 실습으로 득점! 손으로 직접 굴려 봤습니다.",
    "streak": "🔥 {member} 선수 {title}! 히트맵이 물들고 있습니다.",
    "level": "⬆️ {member} 선수 {title}! 꾸준함의 승리입니다.",
    "join": "새 선수 입장! {member} 선수가 워밍업에 들어갑니다.",
}

SYSTEM_PROMPT = (
    "너는 Knowledge Graph(KG) 스터디 현황판의 해설자다. "
    "밝고 재치 있지만 과장하지 않는 한국어로 쓴다. 이모지는 문장당 최대 1개. "
    "반드시 요청된 키만 가진 JSON 객체 하나로만 답한다."
)


# ------------------------------------------------------------------- helpers

def log(message: str) -> None:
    print(f"[dashboard-llm] {message}", file=sys.stderr)


def load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache(path: Path, cache: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as exc:
        log(f"캐시 저장 실패: {exc}")


def cache_key(model: str, prompt: str) -> str:
    return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()


def extract_json(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def request_body(model: str, prompt: str) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": 4000,
    }
    if model.startswith("gpt-5"):
        body["reasoning_effort"] = "low"
    return body


def call_openai(prompt: str, api_key: str, model: str) -> dict | None:
    payload = json.dumps(request_body(model, prompt)).encode("utf-8")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    for attempt in (1, 2):
        req = urllib.request.Request(API_URL, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            parsed = extract_json(content)
            if parsed is None:
                log(f"JSON 파싱 실패 (모델 응답 앞부분): {content[:120]!r}")
            return parsed
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            log(f"HTTP {exc.code} (시도 {attempt}): {detail}")
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                return None
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
            log(f"요청 실패 (시도 {attempt}): {exc}")
            if attempt == 2:
                return None
        time.sleep(RETRY_DELAY_SECONDS)
    return None


def cached_call(prompt: str, api_key: str, model: str, cache: dict) -> dict | None:
    key = cache_key(model, prompt)
    if key in cache:
        return cache[key]
    result = call_openai(prompt, api_key, model)
    if result is not None:
        cache[key] = result
    return result


# ------------------------------------------------------------------ prompts

def item_block(item: dict) -> str:
    kind = "노트" if item["kind"] == "note" else "실습"
    tags = ", ".join(item["tags"]) or "(없음)"
    excerpt = item.get("_excerpt", "")[:MAX_ITEM_CHARS]
    return (
        f"### [{kind}] id={item['id']}\n"
        f"제목: {item['title']}\n날짜: {item['date'] or '?'}\n기존 태그: {tags}\n"
        f"본문:\n{excerpt}\n"
    )


def member_prompt(member: dict) -> str:
    items = member["notes"] + member["labs"]
    counts = member["counts"]
    return (
        f"멤버 GitHub ID: {member['id']}\n"
        f"자기소개: {member['intro'] or '(없음)'}\n"
        f"통계: 노트 {counts['notes']}개, 실습 {counts['labs']}개, 커밋 {counts['commits']}회, "
        f"연속 활동 {member['streak']}일\n\n"
        "아래 자료를 읽고 JSON 으로 답해라.\n"
        "{\n"
        '  "title": "이 멤버에게 어울리는 RPG 스타일 칭호 (12자 이내, 예: 트리플 추출 견습생)",\n'
        '  "summary": "지금까지 무엇을 공부했고 어디까지 왔는지 2문장 (친근한 말투)",\n'
        '  "highlights": ["눈에 띄는 포인트 1", "포인트 2"],\n'
        '  "items": {\n'
        '    "<id>": {"tags": ["소문자 영어 키워드 3~5개, 기존 태그가 있으면 그대로 두고 부족한 것만 보충"],\n'
        '             "one_liner": "이 자료를 한 문장으로"}\n'
        "  }\n"
        "}\n"
        "items 의 키는 아래 id 를 그대로 쓴다. 태그는 KG 스터디 그래프에서 노드로 쓰이니 "
        "'rdf', 'sparql', 'neo4j', 'triple-extraction', 'embedding' 처럼 일반적인 용어를 골라라.\n\n"
        + "\n".join(item_block(i) for i in items)
    )


def digest_prompt(members: list[dict], totals: dict) -> str:
    lines = []
    for m in members:
        c = m["counts"]
        lines.append(
            f"- {m['id']}: 노트 {c['notes']}, 실습 {c['labs']}, 커밋 {c['commits']}, "
            f"연속 {m['streak']}일, 최근 활동 {m['last_active'] or '없음'}, "
            f"칭호 '{m['title']}', 요약: {m['summary']}"
        )
    return (
        f"스터디 전체 통계: 멤버 {totals['members']}명, 노트 {totals['notes']}개, "
        f"실습 {totals['labs']}개, 커밋 {totals['commits']}회\n\n"
        "멤버별 현황:\n" + "\n".join(lines) + "\n\n"
        "JSON 으로 답해라.\n"
        "{\n"
        '  "digest": "스터디 전체 분위기를 전하는 2~3문장. 잘하고 있는 점을 짚고 가볍게 응원",\n'
        '  "shoutouts": ["멤버 id 를 언급하며 칭찬 한 줄 (최대 3개)"]\n'
        "}\n"
    )


def feed_prompt(events: list[dict]) -> str:
    lines = [
        f"- id={e['id']} | {e['date']} | {e['member']} | {KIND_LABEL.get(e['kind'], e['kind'])} | "
        f"{e['title']} | 요약: {e['summary'] or '-'} | 태그: {', '.join(e['tags']) or '-'}"
        for e in events
    ]
    return (
        "아래는 KG 스터디에서 최근 일어난 일들이다. 스포츠 중계 캐스터처럼 각 사건을 한 줄로 중계해라.\n"
        "규칙: 한국어, 50~70자, 멤버 id 를 '○○ 선수'라고 부르고, 무엇을 공부했는지가 드러나야 한다. "
        "이모지는 줄당 최대 1개, 전체의 절반 이상은 이모지 없이. 과장은 살짝, 거짓 정보는 금지.\n"
        'JSON 으로 답해라: {"lines": [{"id": "<id 그대로>", "text": "중계 문장"}]}\n\n'
        + "\n".join(lines)
    )


# ---------------------------------------------------------------- fallbacks

def fallback_commentary(event: dict) -> str:
    template = FEED_TEMPLATES.get(event["kind"], "{member} 선수, {title}.")
    return template.format(member=event["member"], title=event["title"])


def fallback_title(member: dict) -> str:
    c = member["counts"]
    if c["notes"] == 0 and c["labs"] == 0:
        return "이제 막 입장한 탐험가"
    if c["labs"] > c["notes"]:
        return "손으로 배우는 실습파"
    if c["notes"] >= 3:
        return "노트 쌓는 기록가"
    return "그래프 초보 모험가"


def fallback_summary(member: dict) -> str:
    c = member["counts"]
    if c["notes"] == 0 and c["labs"] == 0:
        return "아직 첫 노트를 기다리는 중이에요. 시작이 반!"
    latest = (member["notes"] + member["labs"])[-1]["title"]
    return f"노트 {c['notes']}개, 실습 {c['labs']}개를 쌓았어요. 최근 주제는 '{latest}'."


def fallback_digest(members: list[dict], totals: dict) -> str:
    if not members:
        return "아직 멤버가 없어요. members/ 아래에 폴더를 만들어 시작해 보세요."
    active = [m["id"] for m in members if m["counts"]["notes"] + m["counts"]["labs"] > 0]
    who = ", ".join(active) if active else "모두"
    return (
        f"{totals['members']}명이 노트 {totals['notes']}개, 실습 {totals['labs']}개, "
        f"커밋 {totals['commits']}회를 쌓았어요. {who} 화이팅!"
    )


def apply_fallbacks(members: list[dict]) -> None:
    for m in members:
        m["title"] = m["title"] or fallback_title(m)
        m["summary"] = m["summary"] or fallback_summary(m)


# ---------------------------------------------------------------- applying

def build_feed(events: list[dict], api_key: str, model: str, cache: dict) -> tuple[list[dict], str]:
    """사건 목록에 중계 문장을 붙인다. LLM 이 없거나 실패하면 템플릿 문장."""
    if not events:
        return [], "empty"
    texts: dict[str, str] = {}
    if api_key:
        result = cached_call(feed_prompt(events), api_key, model, cache)
        for line in (result or {}).get("lines") or []:
            if isinstance(line, dict) and line.get("id") and str(line.get("text") or "").strip():
                texts[str(line["id"])] = str(line["text"]).strip()
        if not texts:
            log("중계 문장 생성 실패 → 템플릿 사용")
    feed = []
    for e in events:
        feed.append({
            "id": e["id"], "date": e["date"], "member": e["member"], "kind": e["kind"],
            "title": e["title"], "url": e["url"],
            "text": texts.get(e["id"]) or fallback_commentary(e),
            "summary": e.get("summary", ""), "tags": list(e.get("tags", [])),
            "mock": False,
        })
    return feed, ("llm" if texts else "fallback")


def apply_member_result(member: dict, result: dict) -> None:
    member["title"] = str(result.get("title") or "").strip()[:20]
    member["summary"] = str(result.get("summary") or "").strip()
    member["highlights"] = [str(h).strip() for h in result.get("highlights") or [] if str(h).strip()][:3]
    member["llm"] = True
    items = result.get("items") or {}
    for item in member["notes"] + member["labs"]:
        info = items.get(item["id"]) or {}
        llm_tags = [str(t).strip().lower() for t in info.get("tags") or [] if str(t).strip()]
        merged = list(item["tags"])
        for tag in llm_tags:
            if tag not in merged and len(merged) < MAX_TAGS:
                merged.append(tag)
        item["tags"] = merged
        if not item["summary"] and info.get("one_liner"):
            item["summary"] = str(info["one_liner"]).strip()
    member["tags"] = []
    for item in member["notes"] + member["labs"]:
        for tag in item["tags"]:
            if tag not in member["tags"]:
                member["tags"].append(tag)


def enrich_with_llm(members: list[dict], totals: dict, cache_path: Path, events: list[dict] | None = None) -> dict:
    """members 를 제자리에서 보강하고, study 에 합칠 값과 feed/feed_source 를 돌려준다."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "").strip() or DEFAULT_MODEL
    events = events or []
    if not api_key:
        log("OPENAI_API_KEY 없음 → 규칙 기반 폴백 사용")
        apply_fallbacks(members)
        feed, feed_source = build_feed(events, "", model, {})
        return {
            "digest": fallback_digest(members, totals), "shoutouts": [], "digest_source": "fallback", "model": "",
            "feed": feed, "feed_source": feed_source,
        }

    cache = load_cache(cache_path)
    for m in members:
        if not m["notes"] and not m["labs"]:
            continue
        result = cached_call(member_prompt(m), api_key, model, cache)
        if result:
            apply_member_result(m, result)
        else:
            log(f"{m['id']} 요약 실패 → 폴백")
    apply_fallbacks(members)

    digest_result = cached_call(digest_prompt(members, totals), api_key, model, cache)
    feed, feed_source = build_feed(events, api_key, model, cache)
    save_cache(cache_path, cache)
    if not digest_result:
        return {
            "digest": fallback_digest(members, totals), "shoutouts": [], "digest_source": "fallback", "model": model,
            "feed": feed, "feed_source": feed_source,
        }
    shoutouts = [str(s).strip() for s in digest_result.get("shoutouts") or [] if str(s).strip()][:3]
    return {
        "digest": str(digest_result.get("digest") or fallback_digest(members, totals)).strip(),
        "shoutouts": shoutouts,
        "digest_source": "llm",
        "model": model,
        "feed": feed,
        "feed_source": feed_source,
    }
