"""Sell side, draft -> Nostr listing (POST /api/items/{draft_id}/post). Dry run only.
cd backend && pytest"""
import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.integrations import marketplace
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "MARKETPLACE_DRY_RUN", True)
    monkeypatch.setattr(config, "NOSTR_NSEC", "")

    def no_network():
        raise AssertionError("tests must never open a real relay connection")
    monkeypatch.setattr(marketplace, "_new_client", no_network)


def _draft(text="Black puffer jacket, size M, barely worn"):
    r = client.post("/api/items/parse", data={"zip": "54301", "text": text})
    assert r.status_code == 201, r.text
    return r.json()["draft_id"]


def _donated_total():
    return client.get("/api/impact").json()["totals"]["items_donated"]


def test_sell_draft_then_list_at_the_sellers_price():
    draft_id = _draft()
    quote = client.post(f"/api/items/{draft_id}/sell").json()["suggested_price"]
    price = (quote["low"] + quote["high"]) / 2
    donated_before = _donated_total()

    r = client.post(f"/api/items/{draft_id}/post", json={"price": price})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["item"]["status"] == "listed" and body["item"]["id"].startswith("itm_")
    assert body["listing"]["price"] == price and body["listing"]["dry_run"] is True
    assert body["listing"]["nostr_url"].startswith("https://njump.me/naddr1")

    # a sale is not a donation, and the draft is used up
    assert _donated_total() == donated_before
    assert client.post(f"/api/items/{draft_id}/donate").status_code == 404
    assert client.post(f"/api/items/{draft_id}/post").status_code == 404
    msgs = [e["message"] for e in client.get("/api/events").json()["events"]]
    item_id = body["item"]["id"]
    assert f"Saved {item_id} to list for sale" in msgs
    assert f"Priced {item_id} at ${price:g} (from the price quote)" in msgs


def test_post_draft_without_a_price_uses_the_default():
    r = client.post(f"/api/items/{_draft()}/post")
    assert r.status_code == 201
    assert r.json()["listing"]["price"] == 25          # outerwear, like new


def test_post_rejects_bad_prices_and_unknown_drafts():
    draft_id = _draft()
    assert client.post(f"/api/items/{draft_id}/post", json={"price": 0}).status_code == 422
    assert client.post(f"/api/items/{draft_id}/post", json={"price": -5}).status_code == 422
    assert client.post("/api/items/drf_9999/post").status_code == 404
    assert client.post(f"/api/items/{draft_id}/post").status_code == 201   # still usable


def test_listed_draft_is_never_suggested_to_requesters():
    client.post(f"/api/items/{_draft()}/post")
    body = client.post("/api/requests", json={
        "text": "need a warm coat, moving to Chicago in December", "zip": "60601"}).json()
    assert all(m["item"]["status"] == "available" for m in body["matches"])


def test_item_list_accepts_a_price_too():
    client.post("/api/admin/seed")
    item_id = client.get("/api/items?status=available").json()["items"][0]["id"]
    r = client.post(f"/api/items/{item_id}/list", json={"price": 12.5})
    assert r.status_code == 200 and r.json()["listing"]["price"] == 12.5


def test_post_uses_the_pricing_agents_title_and_description():
    draft_id = _draft()
    sell = client.post(f"/api/items/{draft_id}/sell").json()
    draft = sell["listing_draft"]
    r = client.post(f"/api/items/{draft_id}/post", json={
        "price": sell["suggested_price"]["low"],
        "title": draft["title"], "description": draft["description"]})
    assert r.status_code == 201, r.text
    listing = r.json()["listing"]
    assert listing["title"] == draft["title"]
    assert listing["description"] == draft["description"]
    shown = client.get("/api/listings").json()["listings"]
    assert any(x["title"] == draft["title"] for x in shown)


def test_listing_event_carries_the_agents_text():
    item = {"id": "itm_t1", "item": "jacket", "color": "black", "summary": "A jacket.",
            "category": "outerwear", "condition": "good", "attributes": []}
    ev = marketplace.build_listing_event(item, 20, title="North Face Puffer, Size M",
                                         description="Warm, barely worn puffer.")
    tags = {t[0]: t[1] for t in marketplace._tags(ev)}
    assert tags["title"] == "North Face Puffer, Size M"
    assert ev.content().startswith("Warm, barely worn puffer.")
    plain = marketplace.build_listing_event(item, 20)
    assert {t[0]: t[1] for t in marketplace._tags(plain)}["title"] == "Black jacket"
