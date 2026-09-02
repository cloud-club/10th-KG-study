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
FALLBACK_MODELS = ["gpt-5-mini", "gpt-4.1-mini", "gpt-4o-mini"]  # 앞 모델이 계정에서 안 되면 차례로 시도
MODEL_ERROR_RE = re.compile(r"model|unsupported|not supported|does not exist", re.I)
MAX_ITEM_CHARS = 2500
MAX_TAGS = 5
TIMEOUT_SECONDS = 120
RETRY_DELAY_SECONDS = 4

KIND_LABEL = {"note": "노트", "lab": "실습", "shared": "공유 프로젝트", "commit": "커밋",
              "streak": "연속 활동", "level": "레벨 업"}
FEED_TEMPLATES = {
    "note": "🎙️ {member} 선수, 노트 커밋 '{title}'! 지식그래프에 새 내용이 얹힙니다.",
    "lab": "{member} 선수, 실습 커밋 '{title}'! 코드가 굴러갑니다.",
    "shared": "{member} 선수, 공유 프로젝트에 '{title}' 커밋! 팀 플레이 가동.",
    "commit": "{member} 선수, '{title}' 커밋으로 한 걸음 전진.",
    "streak": "🔥 {member} 선수 {title}! 히트맵이 물들고 있습니다.",
    "level": "⬆️ {member} 선수 {title}! 꾸준함의 승리입니다.",
}
MAX_DIFF_CHARS = 2500
FEED_FIELDS = ("id", "date", "member", "kind", "title", "url", "summary", "tags", "items", "stats", "files")

SYSTEM_PROMPT = (
    "너는 Knowledge Graph(KG) 스터디 현황판의 해설자다. "
    "밝고 재치 있지만 과장하지 않는 한국어로 쓴다. 이모지는 문장당 최대 1개. "
    "반드시 요청된 키만 가진 JSON 객체 하나로만 답한다."
)


# ------------------------------------------------------------------- helpers

class ModelUnavailable(Exception):
    """모델 이름이 틀렸거나 계정에서 쓸 수 없을 때. 다음 후보 모델로 넘어간다."""


_state = {"model": None}  # 이번 빌드에서 실제로 성공한 모델 (이후 호출은 이걸로 고정)


def log(message: str) -> None:
    print(f"[dashboard-llm] {message}", file=sys.stderr)


def candidate_models() -> list[str]:
    configured = os.environ.get("OPENAI_MODEL", "").strip()
    models = [configured] if configured else []
    return models + [m for m in FALLBACK_MODELS if m not in models]


def resolved_model() -> str:
    return _state["model"] or candidate_models()[0]


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
            if exc.code == 404 or (exc.code == 400 and MODEL_ERROR_RE.search(detail)):
                raise ModelUnavailable(detail) from exc
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                return None
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
            log(f"요청 실패 (시도 {attempt}): {exc}")
            if attempt == 2:
                return None
        time.sleep(RETRY_DELAY_SECONDS)
    return None


def cached_call(prompt: str, api_key: str, cache: dict) -> dict | None:
    """캐시 → 확정된 모델 → 후보 모델 순으로 시도. 모델이 안 되면 다음 후보로 넘어간다."""
    models = [_state["model"]] if _state["model"] else candidate_models()
    for model in models:
        key = cache_key(model, prompt)
        if key in cache:
            _state["model"] = model
            return cache[key]
        try:
            result = call_openai(prompt, api_key, model)
        except ModelUnavailable as exc:
            log(f"모델 '{model}' 사용 불가 → 다음 후보 시도 ({str(exc)[:100]})")
            continue
        _state["model"] = model
        if result is not None:
            cache[key] = result
        return result
    log("사용 가능한 모델이 없음 → 폴백")
    return None


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


def event_block(e: dict) -> str:
    stats = e.get("stats") or {}
    stat_line = (f"파일 {stats.get('files', 0)}개, +{stats.get('additions', 0)} -{stats.get('deletions', 0)}"
                 if stats else "-")
    items = "; ".join(f"{i['kind']}:{i['title']}" for i in e.get("items") or []) or "-"
    files = ", ".join(e.get("files") or []) or "-"
    diff = (e.get("_diff") or "")[:MAX_DIFF_CHARS]
    return (
        f"### id={e['id']}\n날짜: {e['date']} | 멤버: {e['member']} | 종류: {KIND_LABEL.get(e['kind'], e['kind'])}\n"
        f"커밋 메시지/제목: {e['title']}\n변경: {stat_line}\n파일: {files}\n연결된 노트/실습: {items}\n"
        + (f"diff 발췌:\n```\n{diff}\n```\n" if diff else "")
    )


def feed_prompt(events: list[dict]) -> str:
    return (
        "아래는 KG 스터디 레포에서 최근 일어난 일들이다. 커밋은 diff 발췌를 실제로 읽고 무엇을 했는지 파악한 뒤, "
        "스포츠 중계 캐스터처럼 한 줄로 중계해라.\n"
        "규칙: 한국어. text 는 50~80자, 멤버 id 를 '○○ 선수'라고 부르고 어떤 작업(무슨 코드/노트를 어떻게)인지 드러나야 한다. "
        "summary 는 캐스터 톤 없이 실제 변경 내용을 사실대로 1문장 (diff 에 없는 내용은 지어내지 말 것). "
        "tags 는 그 작업의 주제 키워드 2~4개, 소문자 영어. 이모지는 text 에만 최대 1개, 전체의 절반 이상은 이모지 없이.\n"
        'JSON 으로 답해라: {"lines": [{"id": "<id 그대로>", "text": "...", "summary": "...", "tags": ["..."]}]}\n\n'
        + "\n".join(event_block(e) for e in events)
    )


# ---------------------------------------------------------------- fallbacks

def fallback_commentary(event: dict) -> str:
    template = FEED_TEMPLATES.get(event["kind"], "{member} 선수, {title}.")
    return template.format(member=event["member"], title=event["title"][:60])


def fallback_summary_line(event: dict) -> str:
    stats = event.get("stats") or {}
    if not stats:
        return ""
    files = ", ".join(Path(f).name for f in (event.get("files") or [])[:4])
    more = len(event.get("files") or []) - 4
    return (f"파일 {stats.get('files', 0)}개 변경 (+{stats.get('additions', 0)} / -{stats.get('deletions', 0)})"
            + (f": {files}" if files else "") + (f" 외 {more}개" if more > 0 else ""))


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

def feed_texts(events: list[dict], api_key: str, cache: dict) -> dict[str, dict]:
    """사건별 중계 결과. 이미 캐시된 사건은 건너뛰고, 새 사건만 한 번에 묶어 호출한다."""
    results: dict[str, dict] = {}
    pending = []
    for e in events:
        key = f"feed:{resolved_model()}:{e['id']}"
        if key in cache:
            results[e["id"]] = cache[key]
        else:
            pending.append(e)
    if not pending:
        return results
    result = cached_call(feed_prompt(pending), api_key, cache)
    for line in (result or {}).get("lines") or []:
        if not (isinstance(line, dict) and line.get("id") and str(line.get("text") or "").strip()):
            continue
        entry = {
            "text": str(line["text"]).strip(),
            "summary": str(line.get("summary") or "").strip(),
            "tags": [str(t).strip().lower() for t in line.get("tags") or [] if str(t).strip()][:MAX_TAGS],
        }
        results[str(line["id"])] = entry
        cache[f"feed:{resolved_model()}:{line['id']}"] = entry
    if not result:
        log("중계 문장 생성 실패 → 템플릿 사용")
    return results


def build_feed(events: list[dict], api_key: str, cache: dict) -> tuple[list[dict], str]:
    """사건 목록에 중계 문장을 붙인다. LLM 이 없거나 실패하면 템플릿 문장."""
    if not events:
        return [], "empty"
    texts = feed_texts(events, api_key, cache) if api_key else {}
    feed = []
    for e in events:
        info = texts.get(e["id"]) or {}
        tags = list(e.get("tags") or [])
        for tag in info.get("tags") or []:
            if tag not in tags and len(tags) < MAX_TAGS:
                tags.append(tag)
        entry = {k: e.get(k) for k in FEED_FIELDS}
        entry["text"] = info.get("text") or fallback_commentary(e)
        entry["summary"] = info.get("summary") or e.get("summary") or fallback_summary_line(e)
        entry["tags"] = tags
        feed.append(entry)
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


def enrich_with_llm(members: list[dict], totals: dict, cache: dict, events: list[dict] | None = None) -> dict:
    """members 를 제자리에서 보강하고, study 에 합칠 값과 feed/feed_source 를 돌려준다. cache 는 호출자가 저장."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    events = events or []
    if not api_key:
        log("OPENAI_API_KEY 없음 → 규칙 기반 폴백 사용")
        apply_fallbacks(members)
        feed, feed_source = build_feed(events, "", cache)
        return {
            "digest": fallback_digest(members, totals), "shoutouts": [], "digest_source": "fallback", "model": "",
            "feed": feed, "feed_source": feed_source,
        }

    for m in members:
        if not m["notes"] and not m["labs"]:
            continue
        result = cached_call(member_prompt(m), api_key, cache)
        if result:
            apply_member_result(m, result)
        else:
            log(f"{m['id']} 요약 실패 → 폴백")
    apply_fallbacks(members)

    digest_result = cached_call(digest_prompt(members, totals), api_key, cache)
    feed, feed_source = build_feed(events, api_key, cache)
    model = resolved_model()
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
