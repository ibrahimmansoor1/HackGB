"""Marketplace (Nostr / Shopstr). No network: dry run or a fake relay client.
cd backend && pytest"""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from nostr_sdk import Keys

from app.core import config
from app.integrations import marketplace
from app.main import app

client = TestClient(app)
RELAYS = ["wss://relay.one", "wss://relay.two", "wss://relay.three"]

ITEM = {"id": "itm_9001", "donor_id": "donor_secret_42", "note": "call me at 555-0100",
        "zip": "02115", "category": "outerwear", "item": "puffer jacket", "color": "black",
        "size": "M", "condition": "like new", "season": "winter",
        "attributes": ["insulated", "hooded"], "summary": "Black hooded puffer jacket, size M.",
        "image_url": "/static/uploads/itm_9001.jpg", "status": "available",
        "embedding": [0.1, 0.2]}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Default every test to dry run; a live test must opt in AND fake the client."""
    monkeypatch.setattr(config, "MARKETPLACE_DRY_RUN", True)
    monkeypatch.setattr(config, "NOSTR_NSEC", "")
    monkeypatch.setattr(config, "NOSTR_RELAYS", RELAYS)
    monkeypatch.setattr(config, "LISTING_LOCATION", "")

    def no_network():
        raise AssertionError("tests must never open a real relay connection")
    monkeypatch.setattr(marketplace, "_new_client", no_network)


def _tags(ev) -> list[list[str]]:
    return json.loads(ev.as_json())["tags"]


def _tag(ev, name):
    return next((t for t in _tags(ev) if t[0] == name), None)


def _new_item() -> str:
    r = client.post("/api/items", data={"zip": "02115", "note": "barely worn",
                                        "donor_id": "donor_secret_42"})
    assert r.status_code == 201
    return r.json()["id"]


class FakeOutput:
    def __init__(self, success, failed):
        self.success, self.failed = success, failed


class FakeClient:
    """Stands in for nostr_sdk.Client; accepts some relays, rejects the rest."""
    def __init__(self, accept=(), hang=False):
        self.accept, self.hang, self.relays, self.sent = set(accept), hang, [], []

    async def add_relay(self, url):
        self.relays.append(str(url))

    async def connect(self, wait=None):
        pass

    async def send_event(self, ev, ok_timeout=None):
        if self.hang:
            await asyncio.sleep(60)
        self.sent.append(ev)
        return FakeOutput([u for u in self.relays if u in self.accept],
                          {u: "blocked" for u in self.relays if u not in self.accept})

    async def disconnect(self):
        pass


def _go_live(monkeypatch, fake):
    monkeypatch.setattr(config, "NOSTR_NSEC", Keys.generate().secret_key().to_bech32())
    monkeypatch.setattr(config, "MARKETPLACE_DRY_RUN", False)
    monkeypatch.setattr(marketplace, "_new_client", lambda: fake)


# ---- event building --------------------------------------------------------
def test_listing_event_shape():
    ev = marketplace.build_listing_event(ITEM, 25)
    assert ev.kind().as_u16() == 30402
    assert ev.verify()
    for name in ("d", "title", "summary", "price", "location", "status", "published_at", "t"):
        assert _tag(ev, name), f"missing {name} tag"
    assert _tag(ev, "d")[1] == "itm_9001"
    assert _tag(ev, "price")[1:] == ["25", "USD"]
    assert _tag(ev, "status")[1] == "active"
    assert _tag(ev, "location")[1] == "02115"
    assert {t[1] for t in _tags(ev) if t[0] == "t"} == {"outerwear", "insulated", "hooded"}
    assert "**Condition:** like new" in ev.content()


def test_listing_event_never_leaks_donor_data():
    raw = marketplace.build_listing_event(ITEM, 25).as_json()
    assert "donor_secret_42" not in raw and "555-0100" not in raw


def test_image_tag_only_for_public_urls(monkeypatch):
    assert _tag(marketplace.build_listing_event(ITEM, 25), "image") is None
    public = {**ITEM, "image_url": "https://cdn.example.com/itm_9001.jpg"}
    assert _tag(marketplace.build_listing_event(public, 25), "image")[1] == public["image_url"]


def test_listing_location_setting_wins(monkeypatch):
    monkeypatch.setattr(config, "LISTING_LOCATION", "Boston, MA")
    assert _tag(marketplace.build_listing_event(ITEM, 25), "location")[1] == "Boston, MA"


def test_sold_event_replaces_listing():
    ev = marketplace.build_listing_event(ITEM, 25, status="sold", published_at=1700000000)
    assert _tag(ev, "status")[1] == "sold" and _tag(ev, "published_at")[1] == "1700000000"
    with pytest.raises(ValueError):
        marketplace.build_listing_event(ITEM, 25, status="expired")


# ---- pricing ---------------------------------------------------------------
def test_suggest_price():
    assert marketplace.suggest_price({"category": "outerwear", "condition": "new"}) == 30
    assert marketplace.suggest_price({"category": "outerwear", "condition": "like new"}) == 25
    assert marketplace.suggest_price({"category": "tops", "condition": "fair"}) == 5
    assert marketplace.suggest_price({"category": "mystery", "condition": "good"}) == 6
    for cat in marketplace.BASE_PRICE:
        for cond in marketplace.CONDITION_MULTIPLIER:
            price = marketplace.suggest_price({"category": cat, "condition": cond})
            assert isinstance(price, int) and price >= 1


# ---- API: dry run ----------------------------------------------------------
def test_list_endpoint_dry_run():
    item_id = _new_item()
    after = client.get("/api/events").json()["events"][-1]["id"]

    r = client.post(f"/api/items/{item_id}/list")
    assert r.status_code == 200
    body = r.json()
    assert body["item"]["status"] == "listed"
    listing = body["listing"]
    assert listing["platform"] == "nostr" and listing["dry_run"] is True
    assert listing["relays_accepted"] == [] and listing["price"] == 25
    assert listing["url"].startswith("https://shopstr.store/listing/naddr1")
    assert len(listing["external_id"]) == 64

    msgs = [e["message"] for e in client.get(f"/api/events?after={after}").json()["events"]]
    assert f"Priced {item_id} at $25 (outerwear, like new)" in msgs
    assert f"Listed {item_id} on Shopstr (dry run)" in msgs

    assert client.post(f"/api/items/{item_id}/list").status_code == 409   # already listed
    listed = client.get("/api/items?status=listed").json()["items"]
    assert item_id in [i["id"] for i in listed]
    assert any(lst["item_id"] == item_id for lst in client.get("/api/listings").json()["listings"])


def test_list_endpoint_missing_item():
    assert client.post("/api/items/itm_nope/list").status_code == 404


def test_simulate_expiry_returns_item_to_pool():
    item_id = _new_item()
    assert client.post(f"/api/items/{item_id}/list").status_code == 200

    r = client.post("/api/admin/simulate-expiry")
    assert r.status_code == 200 and item_id in r.json()["expired"]
    available = client.get("/api/items?status=available").json()["items"]
    assert item_id in [i["id"] for i in available]
    msgs = [e["message"] for e in client.get("/api/events").json()["events"]]
    assert f"30 days unsold — {item_id} moved to donation pool" in msgs

    assert client.post("/api/admin/simulate-expiry").json() == {"expired": []}
    assert client.post(f"/api/items/{item_id}/list").status_code == 200   # can relist


# ---- API: live mode with a fake relay client -------------------------------
def test_live_all_relays_fail_returns_502(monkeypatch):
    fake = FakeClient(accept=())
    _go_live(monkeypatch, fake)
    item_id = _new_item()

    r = client.post(f"/api/items/{item_id}/list")
    assert r.status_code == 502
    assert len(fake.sent) == 1 and fake.relays == RELAYS
    assert client.get("/api/items?status=available").json()["items"][-1]["id"] == item_id
    msgs = [e["message"] for e in client.get("/api/events").json()["events"]]
    assert any(m.startswith(f"Couldn't list {item_id} on Shopstr — 0/3") for m in msgs)


def test_live_publish_reports_relays(monkeypatch):
    fake = FakeClient(accept=RELAYS[:2])
    _go_live(monkeypatch, fake)
    item_id = _new_item()

    r = client.post(f"/api/items/{item_id}/list")
    assert r.status_code == 200
    listing = r.json()["listing"]
    assert listing["dry_run"] is False and listing["relays_accepted"] == RELAYS[:2]
    assert fake.sent[0].verify()
    msgs = [e["message"] for e in client.get("/api/events").json()["events"]]
    assert f"Listed {item_id} on Shopstr — 2/3 relays" in msgs

    assert item_id in client.post("/api/admin/simulate-expiry").json()["expired"]
    sold = [ev for ev in fake.sent[1:] if _tag(ev, "d")[1] == item_id]
    assert len(sold) == 1 and _tag(sold[0], "status")[1] == "sold"
    assert sold[0].created_at().as_secs() > fake.sent[0].created_at().as_secs()


def test_live_hanging_relays_time_out(monkeypatch):
    monkeypatch.setattr(marketplace, "TIMEOUT_S", 0.2)
    _go_live(monkeypatch, FakeClient(accept=RELAYS, hang=True))
    out = asyncio.run(marketplace.publish_listing(ITEM, 25))
    assert out["relays_accepted"] == [] and out["relays_failed"] == RELAYS
    assert out["dry_run"] is False


def test_invalid_nsec_is_a_502(monkeypatch):
    _go_live(monkeypatch, FakeClient(accept=RELAYS))
    monkeypatch.setattr(config, "NOSTR_NSEC", "not-a-key")
    item_id = _new_item()
    assert client.post(f"/api/items/{item_id}/list").status_code == 502
    assert client.get("/api/items?status=available").json()["items"][-1]["id"] == item_id


def test_request_never_reserves_an_item_mid_listing(monkeypatch):
    """Slow relays: a request arriving while the item is being listed must not
    reserve it (otherwise it ends up both reserved and for sale)."""
    from app.agents import orchestrator

    class SlowClient(FakeClient):
        async def send_event(self, ev, ok_timeout=None):
            await asyncio.sleep(0.2)
            return await super().send_event(ev, ok_timeout)

    _go_live(monkeypatch, SlowClient(accept=RELAYS))
    item_id = _new_item()

    async def race():
        listing = asyncio.create_task(orchestrator.list_item(item_id))
        await asyncio.sleep(0.05)
        req = await orchestrator.handle_request("black puffer jacket insulated hooded",
                                                "02115", "demo_requester")
        return await listing, req

    out, req = asyncio.run(race())
    assert out.item.status == "listed"
    assert item_id not in [m.item_id for m in req.matches]
