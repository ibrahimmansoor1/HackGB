"""Pricing from web search (Brave): going rates when there are no eBay comps."""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import config, llm
from app.integrations import websearch
from app.main import app

client = TestClient(app)
JACKET = {"zip": "54311", "text": "Black puffer jacket, hooded, water-resistant, size M"}
RESULTS = [
    {"title": "Used Puffer Jacket Men's M - eBay", "url": "https://www.ebay.com/itm/1",
     "snippet": "Black puffer jacket, pre-owned. $45.00 or Best Offer."},
    {"title": "Puffer jacket | Poshmark", "url": "https://poshmark.com/listing/2",
     "snippet": "Hooded puffer jacket size M, gently used — $55"},
    {"title": "iPhone case", "url": "https://example.com/3", "snippet": "$9.99"},
    {"title": "How to wash a puffer jacket", "url": "https://example.com/4", "snippet": "Tips."},
]


def _draft():
    return client.post("/api/items/parse", data=JACKET).json()["draft_id"]


@pytest.fixture
def brave(monkeypatch):
    monkeypatch.setattr(config, "BRAVE_API_KEY", "test")
    queries = []

    async def fake(q, count=10):
        queries.append(q)
        return RESULTS
    monkeypatch.setattr(websearch, "search", fake)
    return queries


def test_offline_reads_prices_from_snippets(brave):
    body = client.post(f"/api/items/{_draft()}/sell").json()
    assert brave == ["used puffer jacket price"]
    assert body["basis"] == "web search"
    assert [c["source"] for c in body["comps"]] == ["ebay.com", "poshmark.com"]   # case dropped
    assert body["suggested_price"] == {"low": 30, "high": 45, "currency": "USD"}   # median 50
    msgs = [e["message"] for e in client.get("/api/events").json()["events"]]
    assert "Read 2 going rates online (ebay.com, poshmark.com)" in msgs
    assert "Suggested $30–45 (listed online for)" in msgs


def test_model_reads_results_and_invented_urls_are_dropped(brave, modal_mode, monkeypatch):
    async def model(system, user, images=None):
        assert "Poshmark" in user
        return {"suggested_price": {"low": 35, "high": 50},
                "comps": [{"title": "Used Puffer", "price": 45, "source": "ebay.com",
                           "url": "https://www.ebay.com/itm/1"},
                          {"title": "Made up", "price": 99, "source": "x.com",
                           "url": "https://x.com/fake"}],
                "listing_draft": {"title": "Black Puffer Jacket, M", "description": "Warm."}}
    monkeypatch.setattr(llm, "complete_json", model)
    body = client.post(f"/api/items/{_draft()}/sell").json()
    assert body["basis"] == "web search" and [c["url"] for c in body["comps"]] == \
        ["https://www.ebay.com/itm/1"]


def test_search_failure_or_no_prices_falls_back_to_estimate(monkeypatch):
    monkeypatch.setattr(config, "BRAVE_API_KEY", "test")

    async def down(q, count=10):
        raise websearch.SearchError("search failed (429)")
    monkeypatch.setattr(websearch, "search", down)
    assert client.post(f"/api/items/{_draft()}/sell").json()["basis"] == "estimate"

    async def no_prices(q, count=10):
        return [RESULTS[3]]
    monkeypatch.setattr(websearch, "search", no_prices)
    assert client.post(f"/api/items/{_draft()}/sell").json()["basis"] == "estimate"


def test_no_key_skips_search(monkeypatch):
    async def boom(q, count=10):
        raise AssertionError("no key: must not search")
    monkeypatch.setattr(websearch, "search", boom)
    assert client.post(f"/api/items/{_draft()}/sell").json()["basis"] == "estimate"


def test_concierge_uses_web_prices(brave):
    out = client.post(f"/api/items/{_draft()}/handle", json={}).json()
    assert out["price_quote"] == {"low": 30, "high": 45, "currency": "USD"}
    assert "similar items go for online $30–45" in out["summary"]


def test_brave_client_parses_results(monkeypatch):
    monkeypatch.setattr(config, "BRAVE_API_KEY", "key123")

    def handler(req: httpx.Request):
        assert req.headers["x-subscription-token"] == "key123"
        assert req.url.params["q"] == "used puffer jacket price"
        return httpx.Response(200, json={"web": {"results": [
            {"title": "<strong>Puffer</strong> jacket", "url": "https://ebay.com/1",
             "description": "Only <strong>$40</strong> &amp; free shipping",
             "extra_snippets": ["Size M"]},
            {"title": "no url"}]}})
    monkeypatch.setattr(websearch, "_transport", httpx.MockTransport(handler))
    out = asyncio.run(websearch.search("used puffer jacket price"))
    assert out == [{"title": "Puffer jacket", "url": "https://ebay.com/1",
                    "snippet": "Only $40 & free shipping Size M"}]

    monkeypatch.setattr(websearch, "_transport", httpx.MockTransport(lambda r: httpx.Response(401)))
    with pytest.raises(websearch.SearchError):
        asyncio.run(websearch.search("x"))
