"""Sell path: POST /api/items/{draft_id}/sell (docs/04), eBay and models faked."""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agents import pricing
from app.core import config, llm
from app.integrations import ebay, marketplace
from app.main import app

client = TestClient(app)
JACKET = {"zip": "54311", "text": "Black puffer jacket, hooded, water-resistant, size M, barely worn"}
COMPS = [
    {"title": "Columbia Men's Puffer Jacket M Black", "price": 50.0, "condition": "Pre-owned",
     "source": "ebay", "url": "https://www.ebay.com/itm/1"},
    {"title": "North Face Down Jacket Hooded", "price": 60.0, "condition": "Pre-owned",
     "source": "ebay", "url": "https://www.ebay.com/itm/2"},
    {"title": "iPhone 15 phone case", "price": 9.0, "condition": "New",
     "source": "ebay", "url": "https://www.ebay.com/itm/3"},
]


def _draft():
    return client.post("/api/items/parse", data=JACKET).json()


def _sell(draft_id):
    return client.post(f"/api/items/{draft_id}/sell")


@pytest.fixture
def ebay_up(monkeypatch):
    """eBay configured and returning COMPS."""
    monkeypatch.setattr(config, "EBAY_APP_ID", "app")
    monkeypatch.setattr(config, "EBAY_CERT_ID", "cert")
    queries = []

    async def fake_search(q, limit=10):
        queries.append(q)
        return COMPS
    monkeypatch.setattr(ebay, "search", fake_search)
    return queries


def test_no_ebay_keys_gives_estimate():
    draft = _draft()
    r = _sell(draft["draft_id"])
    assert r.status_code == 200
    body = r.json()
    mid = marketplace.suggest_price(draft["item"])
    assert body["basis"] == "estimate" and body["comps"] == []
    assert body["suggested_price"] == {"low": round(mid * 0.8), "high": round(mid * 1.2),
                                       "currency": "USD"}
    assert body["listing_draft"]["title"] == "Black Puffer Jacket, Size M, Like New"
    last = client.get("/api/events").json()["events"][-1]
    assert (last["agent"], last["event_type"], last["category"]) == \
        ("pricing", "price_quoted", "outerwear")
    assert last["message"] == f"Suggested ${round(mid * 0.8)}–{round(mid * 1.2)} (estimate)"


def test_ebay_comps_in_stub_mode(ebay_up):
    body = _sell(_draft()["draft_id"]).json()
    assert ebay_up == ["puffer jacket"]
    assert body["basis"] == "active listings"
    assert [c["url"] for c in body["comps"]] == [COMPS[0]["url"], COMPS[1]["url"]]   # case dropped
    assert body["suggested_price"] == {"low": 33, "high": 50, "currency": "USD"}   # median 55
    msgs = [e["message"] for e in client.get("/api/events").json()["events"]]
    assert "Found 3 active eBay listings" in msgs
    assert "Suggested $33–50 (currently listed for)" in msgs


def test_ebay_error_falls_back_to_estimate(monkeypatch):
    monkeypatch.setattr(config, "EBAY_APP_ID", "app")
    monkeypatch.setattr(config, "EBAY_CERT_ID", "cert")

    async def down(q, limit=10):
        raise ebay.EbayError("search failed (503)")
    monkeypatch.setattr(ebay, "search", down)
    assert _sell(_draft()["draft_id"]).json()["basis"] == "estimate"
    msgs = [e["message"] for e in client.get("/api/events").json()["events"]]
    assert "Couldn't reach eBay (search failed (503)); using an estimate" in msgs


def test_model_pricing_keeps_only_real_comps(monkeypatch, ebay_up, modal_mode):

    async def model(system, user):
        assert "Puffer Jacket M Black" in user
        return {"suggested_price": {"low": 35, "high": 55, "currency": "USD"},
                "comps": [COMPS[0], {**COMPS[1], "url": "https://made.up/x"}],
                "listing_draft": {"title": "x" * 100, "description": "Warm."}}
    monkeypatch.setattr(llm, "complete_json", model)
    body = _sell(_draft()["draft_id"]).json()
    assert body["basis"] == "active listings" and [c["url"] for c in body["comps"]] == [COMPS[0]["url"]]
    assert body["suggested_price"]["low"] == 35 and len(body["listing_draft"]["title"]) == 80


def test_model_failure_is_502(monkeypatch, ebay_up, modal_mode):

    async def model(system, user):
        return {"suggested_price": {"low": 90, "high": 10}}
    monkeypatch.setattr(llm, "complete_json", model)
    assert _sell(_draft()["draft_id"]).status_code == 502


def test_sell_keeps_the_draft_and_unknown_is_404():
    draft_id = _draft()["draft_id"]
    assert _sell(draft_id).status_code == 200
    assert client.post(f"/api/items/{draft_id}/donate").status_code == 201
    assert _sell(draft_id).status_code == 404
    assert _sell("drf_9999").status_code == 404


def test_stub_pricing_without_comparable_comps_gives_estimate(monkeypatch, ebay_up):
    monkeypatch.setattr(ebay, "search", lambda q, limit=10: _async([COMPS[2]]))
    assert _sell(_draft()["draft_id"]).json()["basis"] == "estimate"


async def _async(value):
    return value


# ---- eBay client against a fake HTTP server ----------------------------------
def test_ebay_client_parses_and_caches_token(monkeypatch):
    monkeypatch.setattr(config, "EBAY_APP_ID", "app")
    monkeypatch.setattr(config, "EBAY_CERT_ID", "cert")
    monkeypatch.setattr(ebay, "_token", None)
    seen = []

    def handler(req: httpx.Request):
        seen.append(req.url.path)
        if req.url.path.endswith("/oauth2/token"):
            assert req.headers["authorization"].startswith("Basic ")
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
        assert req.headers["authorization"] == "Bearer tok"
        assert req.headers["x-ebay-c-marketplace-id"] == "EBAY_US"
        assert req.url.params["q"] == "Columbia puffer jacket"
        return httpx.Response(200, json={"itemSummaries": [
            {"title": "Columbia Puffer", "price": {"value": "49.99", "currency": "USD"},
             "condition": "Pre-owned", "itemWebUrl": "https://www.ebay.com/itm/1"},
            {"title": "Euro listing", "price": {"value": "40", "currency": "EUR"},
             "itemWebUrl": "https://www.ebay.com/itm/2"},
            {"title": "No price", "itemWebUrl": "https://www.ebay.com/itm/3"},
        ]})
    monkeypatch.setattr(ebay, "_transport", httpx.MockTransport(handler))

    out = asyncio.run(ebay.search("Columbia puffer jacket"))
    assert out == [{"title": "Columbia Puffer", "price": 49.99, "condition": "Pre-owned",
                    "source": "ebay", "url": "https://www.ebay.com/itm/1"}]
    asyncio.run(ebay.search("Columbia puffer jacket"))
    assert [p.rsplit("/", 1)[-1] for p in seen] == ["token", "search", "search"]


def test_ebay_client_errors_are_ebay_errors(monkeypatch):
    monkeypatch.setattr(config, "EBAY_APP_ID", "app")
    monkeypatch.setattr(config, "EBAY_CERT_ID", "cert")
    monkeypatch.setattr(ebay, "_token", None)
    monkeypatch.setattr(ebay, "_transport", httpx.MockTransport(lambda r: httpx.Response(401)))
    with pytest.raises(ebay.EbayError):
        asyncio.run(ebay.search("coat"))
    monkeypatch.setattr(config, "EBAY_APP_ID", "")
    with pytest.raises(ebay.EbayError):
        asyncio.run(ebay.search("coat"))


def test_listing_draft_template_with_brand():
    item = {"brand": "Columbia", "color": "black", "item": "puffer jacket", "size": "M",
            "condition": "like new", "summary": "A coat.", "attributes": ["insulated"]}
    d = pricing.listing_draft(item)
    assert d["title"] == "Columbia Black Puffer Jacket, Size M, Like New"
    assert "Features: insulated." in d["description"]
