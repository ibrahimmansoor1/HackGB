"""Runs in stub mode (no model needed): cd backend && pytest"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


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
