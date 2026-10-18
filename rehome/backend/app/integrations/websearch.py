"""Brave Search API: web results the pricing agent reads for going rates.

Called ONLY by the orchestrator; never touches the DB. Needs BRAVE_API_KEY
(https://brave.com/search/api/). Returns titles, URLs and snippets; the
pricing agent pulls prices out of them and keeps only results it was given.
"""
import html
import re

import httpx
from app.core import config

URL = "https://api.search.brave.com/res/v1/web/search"
TIMEOUT_S = 8
_transport: httpx.AsyncBaseTransport | None = None   # tests swap in a MockTransport


class SearchError(Exception):
    """Brave unreachable, misconfigured, or returned something unexpected."""


def configured() -> bool:
    return bool(config.BRAVE_API_KEY)


async def search(query: str, count: int = 10) -> list[dict]:
    """Web results for `query` -> [{title, url, snippet}]."""
    if not configured():
        raise SearchError("BRAVE_API_KEY not set")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S, transport=_transport) as client:
            r = await client.get(URL, params={"q": query, "count": count, "country": "us"},
                                 headers={"X-Subscription-Token": config.BRAVE_API_KEY,
                                          "Accept": "application/json"})
        if r.status_code != 200:
            raise SearchError(f"search failed ({r.status_code})")
        results = (r.json().get("web") or {}).get("results") or []
    except (httpx.HTTPError, ValueError) as e:
        raise SearchError(str(e) or type(e).__name__) from e
    out = []
    for res in results:
        if not res.get("url"):
            continue
        snippet = " ".join([res.get("description") or "", *(res.get("extra_snippets") or [])])
        out.append({"title": _plain(res.get("title")), "url": res["url"],
                    "snippet": _plain(snippet)})
    return out


def _plain(text: str | None) -> str:
    """Brave highlights matches with <strong>; drop tags and HTML entities' markup."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text or ""))).strip()
