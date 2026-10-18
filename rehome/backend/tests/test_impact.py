"""GET /api/impact (docs/04), on the in-memory version of impact_hourly."""
from datetime import timedelta

from fastapi.testclient import TestClient

from app.core import db
from app.main import app

client = TestClient(app)
CHICAGO = {"text": "need a warm coat, moving to Chicago in December", "zip": "60601"}
KEYS = {"items_parsed", "items_donated", "prices_quoted", "requests_made", "matches_made",
        "matches_accepted"}


def _demo_activity():
    client.post("/api/admin/seed")            # seed emits no counted events
    for text in ("Black puffer jacket, size M", "wool blanket"):
        draft_id = client.post("/api/items/parse", data={"zip": "54311", "text": text}
                               ).json()["draft_id"]
        client.post(f"/api/items/{draft_id}/sell")
        client.post(f"/api/items/{draft_id}/donate")
    req = client.post("/api/requests", json=CHICAGO).json()
    client.post("/api/requests", json={"text": "a unicorn costume", "zip": "54311"})
    client.post("/api/matches/accept",
                json={"request_id": req["request_id"], "item_id": req["matches"][0]["item_id"]})


def test_empty_dashboard_has_every_total():
    body = client.get("/api/impact").json()
    assert body == {"totals": dict.fromkeys(KEYS, 0), "by_category": [], "hourly": []}


def test_totals_categories_and_hourly():
    _demo_activity()
    body = client.get("/api/impact").json()
    assert body["totals"] == {"items_parsed": 2, "items_donated": 2, "prices_quoted": 2,
                              "requests_made": 2, "matches_made": 1, "matches_accepted": 1}
    cats = {c["category"]: c for c in body["by_category"]}
    assert cats["outerwear"] == {"category": "outerwear", "items_donated": 1, "matches_accepted": 1}
    assert cats["home"]["items_donated"] == 1 and cats["home"]["matches_accepted"] == 0
    assert {h["event_type"] for h in body["hourly"]} == {
        "item_parsed", "item_donated", "price_quoted", "request_made", "match_made",
        "match_accepted"}
    assert sum(h["n"] for h in body["hourly"]) == sum(body["totals"].values())


def test_hourly_covers_only_the_last_24h():
    _demo_activity()
    for e in db._events:
        if e.get("event_type") == "request_made":
            e["created_at"] -= timedelta(hours=30)
    body = client.get("/api/impact").json()
    assert body["totals"]["requests_made"] == 2                       # all time
    assert "request_made" not in {h["event_type"] for h in body["hourly"]}
