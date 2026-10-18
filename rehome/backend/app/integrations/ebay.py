"""eBay Browse API: active listings used as pricing comps (docs/02, "Known risk").

Called ONLY by the orchestrator; never touches the DB. Uses an app-only
OAuth token (client credentials from EBAY_APP_ID + EBAY_CERT_ID), cached
until shortly before it expires. Prices are asking prices, so the UI labels
them "currently listed for".
"""
import time
import httpx
from app.core import config

SCOPE = "https://api.ebay.com/oauth/api_scope"
TIMEOUT_S = 8
_token: tuple[str, float] | None = None    # (access token, expires at)
_transport: httpx.AsyncBaseTransport | None = None   # tests swap in a MockTransport


class EbayError(Exception):
    """eBay unreachable, misconfigured, or returned something unexpected."""


def configured() -> bool:
    return bool(config.EBAY_APP_ID and config.EBAY_CERT_ID)


def _base() -> str:
    return "https://api.sandbox.ebay.com" if config.EBAY_ENV == "sandbox" else "https://api.ebay.com"


async def _access_token(client: httpx.AsyncClient) -> str:
    global _token
    if _token and _token[1] > time.time():
        return _token[0]
    r = await client.post(f"{_base()}/identity/v1/oauth2/token",
                          data={"grant_type": "client_credentials", "scope": SCOPE},
                          auth=(config.EBAY_APP_ID, config.EBAY_CERT_ID))
    if r.status_code != 200:
        raise EbayError(f"token request failed ({r.status_code})")
    body = r.json()
    _token = (body["access_token"], time.time() + int(body.get("expires_in", 7200)) - 60)
    return _token[0]


async def search(query: str, limit: int = 10) -> list[dict]:
    """Active fixed-price listings for `query` -> [{title, price, condition, source, url}]."""
    if not configured():
        raise EbayError("EBAY_APP_ID / EBAY_CERT_ID not set")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S, transport=_transport) as client:
            token = await _access_token(client)
            r = await client.get(f"{_base()}/buy/browse/v1/item_summary/search",
                                 params={"q": query, "limit": limit,
                                         "filter": "buyingOptions:{FIXED_PRICE}"},
                                 headers={"Authorization": f"Bearer {token}",
                                          "X-EBAY-C-MARKETPLACE-ID": config.EBAY_MARKETPLACE})
        if r.status_code != 200:
            raise EbayError(f"search failed ({r.status_code})")
        summaries = r.json().get("itemSummaries", [])
    except (httpx.HTTPError, KeyError, ValueError) as e:   # network, or a malformed body
        raise EbayError(str(e) or type(e).__name__) from e
    comps = []
    for s in summaries:
        price = s.get("price") or {}
        if price.get("currency") != "USD" or not s.get("itemWebUrl"):
            continue
        try:
            value = float(price["value"])
        except (KeyError, TypeError, ValueError):
            continue
        comps.append({"title": s.get("title", ""), "price": value,
                      "condition": s.get("condition"), "source": "ebay",
                      "url": s["itemWebUrl"]})
    return comps
