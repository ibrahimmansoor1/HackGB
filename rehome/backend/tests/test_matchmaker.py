"""Matchmaker agent (new donations -> waiting requests) and posting a draft for sale."""
import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.integrations import marketplace
from app.main import app

client = TestClient(app)
CHICAGO = {"text": "need a warm coat, moving to Chicago in December", "zip": "60601"}
JACKET = {"zip": "54311", "text": "Black puffer jacket, hooded, water-resistant, size M"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "MARKETPLACE_DRY_RUN", True)
    monkeypatch.setattr(config, "NOSTR_NSEC", "")

    def no_network():
        raise AssertionError("tests must never open a real relay connection")
    monkeypatch.setattr(marketplace, "_new_client", no_network)


def _draft(**data):
    return client.post("/api/items/parse", data={**JACKET, **data}).json()["draft_id"]


def _messages():
    return [(e["agent"], e["message"]) for e in client.get("/api/events").json()["events"]]


def test_donation_fills_a_request_that_was_waiting():
    req = client.post("/api/requests", json=CHICAGO).json()
    assert req["status"] == "open"                        # nothing in stock yet

    out = client.post(f"/api/items/{_draft()}/donate").json()
    assert out["waiting_requests"] == [req["request_id"]]
    assert "1 open request nearby could use it" in out["message"]
    assert ("matchmaker", f"{out['item_id']} may fit {req['request_id']} (winter coat, zip 60601)") \
        in _messages()

    r = client.post("/api/matches/accept", json={"request_id": req["request_id"],
                                                 "item_id": out["item_id"]})
    assert r.status_code == 200 and r.json()["status"] == "reserved"


def test_closed_and_unrelated_requests_are_skipped():
    client.post("/api/requests", json={"text": "winter coat for my daughter", "zip": "54301"})
    client.post("/api/requests", json={"text": "pots and pans", "zip": "54301"})
    out = client.post(f"/api/items/{_draft()}/donate").json()
    assert out["waiting_requests"] == []                  # kids coat / cookware don't fit
    assert any(a == "matchmaker" and m.startswith("No open requests fit") for a, m in _messages())

    req = client.post("/api/requests", json=CHICAGO).json()   # matches the jacket above
    client.post("/api/matches/accept", json={"request_id": req["request_id"],
                                             "item_id": out["item_id"]})
    assert client.post(f"/api/items/{_draft()}/donate").json()["waiting_requests"] == []


def test_post_draft_lists_it_at_the_quoted_price():
    draft_id = _draft()
    r = client.post(f"/api/items/{draft_id}/post", json={"price": 42.5})
    assert r.status_code == 201
    body = r.json()
    assert body["item"]["status"] == "listed" and body["listing"]["price"] == 42.5
    assert body["listing"]["dry_run"] is True
    assert client.post(f"/api/items/{draft_id}/donate").status_code == 404   # draft consumed
    events = client.get("/api/events").json()["events"]
    assert not any(e["event_type"] == "item_donated" for e in events)     # sold, not donated
    assert f"Priced {body['item']['id']} at $42.5 (from the price quote)" in \
        [e["message"] for e in events]


def test_post_draft_without_price_uses_the_heuristic_and_rejects_bad_prices():
    assert client.post(f"/api/items/{_draft()}/post", json={"price": 0}).status_code == 422
    body = client.post(f"/api/items/{_draft()}/post").json()
    assert body["listing"]["price"] == marketplace.suggest_price(body["item"])
    assert client.post("/api/items/drf_9999/post").status_code == 404
