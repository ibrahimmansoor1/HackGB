"""Runs in stub mode (no model needed): cd backend && pytest"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["db"] == "memory"


def test_donor_and_requester_flow():
    client.post("/api/admin/seed")
    r = client.post("/api/items", data={"zip": "02115", "note": "barely worn"})
    assert r.status_code == 201 and r.json()["status"] == "available"

    r = client.post("/api/requests",
                    json={"text": "need a warm coat, moving to Chicago in December", "zip": "60601"})
    body = r.json()
    assert r.status_code == 201
    assert body["status"] == "matched" and body["matches"]

    events = client.get("/api/events").json()["events"]
    assert any(e["agent"] == "requester" for e in events)


def test_impact_events_carry_type_and_category():
    client.post("/api/items", data={"zip": "02115", "note": "black winter coat"})
    client.post("/api/admin/seed")
    client.post("/api/requests", json={"text": "need a warm coat", "zip": "60601"})
    events = client.get("/api/events").json()["events"]
    typed = {e["event_type"]: e for e in events if e["event_type"]}
    assert set(typed) == {"item_parsed", "item_donated", "request_made", "match_made"}
    assert typed["item_donated"]["category"] and typed["match_made"]["category"]
    assert typed["request_made"]["category"] is None


def test_stub_embeddings_keep_their_threshold_with_a_real_text_model(monkeypatch):
    """Modal text model set, no embed model: matching must still use the stub cutoff."""
    from app.agents import orchestrator
    from app.core import config
    monkeypatch.setattr(config, "USE_STUBS", False)
    monkeypatch.setattr(config, "MODAL_EMBED_MODEL", "")
    assert orchestrator._threshold() == 0.2
    monkeypatch.setattr(config, "MODAL_EMBED_MODEL", "bge")
    assert orchestrator._threshold() == config.MATCH_THRESHOLD


def test_seed_skips_items_already_in_db():
    """After a restart _seeded is empty but Tiger still holds the seed items."""
    from app.agents import orchestrator
    assert client.post("/api/admin/seed").json()["seeded"] == 18
    orchestrator._seeded.clear()
    assert client.post("/api/admin/seed").json()["seeded"] == 0
    assert len(client.get("/api/items").json()["items"]) == 18
