"""getxapi.com client — the cheapest X data source we've found.

$0.05 per 1,000 tweets. 3× cheaper than twitterapi.io. $0.10 free
credit at signup, no credit card. Same pay-as-you-go model.

API reference: https://www.getxapi.com  (docs link varies)
Base URL:       https://api.getxapi.com   (update if docs differ)
Auth:           X-API-Key header
Key env var:    MEMEGINE_GETXAPI_KEY

Same shape as twitterapi_client — returns TweetData so the watcher
doesn't care which provider is active.

If GetXAPI's endpoint paths differ from what's hardcoded here, override
via env MEMEGINE_GETXAPI_BASE_URL.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from . import x_fetch


_DEFAULT_BASE_URL = "https://api.getxapi.com"
KEY_ENV_VAR = "MEMEGINE_GETXAPI_KEY"
BASE_URL_ENV_VAR = "MEMEGINE_GETXAPI_BASE_URL"


class GetxapiError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get(KEY_ENV_VAR, "").strip()
    if not key:
        raise GetxapiError(
            f"{KEY_ENV_VAR} is not set — sign up at https://www.getxapi.com "
            "and paste your key into .env"
        )
    return key


def _base_url() -> str:
    return os.environ.get(BASE_URL_ENV_VAR, _DEFAULT_BASE_URL).rstrip("/")


def _http_get(path: str, params: dict) -> dict:
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{_base_url()}{path}"
    if qs:
        url = f"{url}?{qs}"
    req = urllib.request.Request(
        url,
        headers={
            "X-API-Key": _api_key(),
            "Accept": "application/json",
            "User-Agent": "memegine/0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except OSError:
            err_body = ""
        raise GetxapiError(f"HTTP {exc.code}: {err_body[:300]}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GetxapiError(f"network: {exc}")
    except json.JSONDecodeError as exc:
        raise GetxapiError(f"JSON parse: {exc}")


def user_last_tweets(handle: str, *, limit: int = 20) -> list[x_fetch.TweetData]:
    """Newest N tweets for @handle. Normalized to TweetData."""
    handle = handle.lstrip("@").strip().lower()
    if not handle:
        return []
    raw = _http_get(
        "/twitter/user/last_tweets",
        {"userName": handle, "count": limit},
    )
    tweets = raw.get("tweets") or raw.get("data") or []
    out: list[x_fetch.TweetData] = []
    for r in tweets[:limit]:
        td = _normalize(r)
        if td is not None:
            out.append(td)
    return out


def tweet_by_id(tweet_id: str) -> Optional[x_fetch.TweetData]:
    raw = _http_get("/twitter/tweet/by_id", {"tweetId": tweet_id})
    data = raw.get("tweet") or raw.get("data")
    return _normalize(data) if data else None


def _normalize(raw: dict) -> Optional[x_fetch.TweetData]:
    """Mirror of twitterapi_client._normalize. Both providers converge
    on roughly the same shape, with a couple of field aliases."""
    if not isinstance(raw, dict):
        return None
    tid = str(raw.get("id") or raw.get("id_str") or raw.get("tweetId") or "")
    if not tid:
        return None
    text = str(raw.get("text") or raw.get("full_text") or "").strip()
    user = raw.get("user") or raw.get("author") or {}
    handle = str(
        user.get("userName") or user.get("screen_name") or user.get("handle") or ""
    ).strip().lstrip("@").lower()
    name = str(user.get("name") or "").strip()
    created = str(raw.get("createdAt") or raw.get("created_at") or "").strip()
    from ._time import now_iso as _now_iso
    entities = raw.get("entities") or {}
    hashtags = [h.get("text", "") for h in (entities.get("hashtags") or []) if isinstance(h, dict)]
    mentions = [
        (m.get("screen_name") or m.get("username") or "")
        for m in (entities.get("user_mentions") or entities.get("mentions") or [])
        if isinstance(m, dict)
    ]
    symbols = [s.get("text", "") for s in (entities.get("symbols") or []) if isinstance(s, dict)]
    urls = [
        (u.get("expanded_url") or u.get("url") or "")
        for u in (entities.get("urls") or [])
        if isinstance(u, dict)
    ]
    media_urls: list[str] = []
    for m in (entities.get("media") or raw.get("media") or []):
        if isinstance(m, dict):
            mu = m.get("media_url_https") or m.get("url")
            if mu:
                media_urls.append(mu)

    return x_fetch.TweetData(
        id=tid,
        text=text,
        author_handle=handle,
        author_name=name,
        created_at=created,
        url=f"https://x.com/{handle}/status/{tid}" if handle else f"https://x.com/i/status/{tid}",
        favorite_count=int(raw.get("likeCount") or raw.get("favorite_count") or 0),
        reply_count=int(raw.get("replyCount") or raw.get("reply_count") or 0),
        hashtags=[h for h in hashtags if h],
        mentions=[m for m in mentions if m],
        symbols=[s for s in symbols if s],
        urls=[u for u in urls if u],
        media_urls=media_urls,
        lang=str(raw.get("lang") or "en"),
        fetched_at=_now_iso(),
    )


def probe() -> dict:
    try:
        tweets = user_last_tweets("jack", limit=1)
        if tweets:
            return {"ok": True, "msg": f"OK — @jack id={tweets[0].id}"}
        return {"ok": False, "msg": "empty response"}
    except GetxapiError as exc:
        return {"ok": False, "msg": str(exc)}
