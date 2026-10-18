"""Requests suggest matches; POST /api/matches/accept reserves one (docs/04)."""
from fastapi.testclient import TestClient

from app.agents import orchestrator
from app.main import app

client = TestClient(app)
CHICAGO = {"text": "need a warm coat, moving to Chicago in December", "zip": "60601"}


def _request():
    client.post("/api/admin/seed")
    return client.post("/api/requests", json=CHICAGO).json()


def _accept(req_id, item_id):
    return client.post("/api/matches/accept", json={"request_id": req_id, "item_id": item_id})


def test_query_has_needs_list_and_matches_have_titles():
    body = _request()
    assert body["query"]["needs"] == ["winter coat"] and "need" not in body["query"]
    assert body["matches"][0]["title"]


def test_accept_reserves_closes_and_notifies():
    body = _request()
    top = body["matches"][0]
    r = _accept(body["request_id"], top["item_id"])
    assert r.status_code == 200
    out = r.json()
    zip_code = top["item"]["zip"]
    assert out["match_id"].startswith("mat_") and out["item_id"] == top["item_id"]
    assert out["status"] == "reserved" and out["donor_notified"] is True
    assert out["handoff"] == {"method": "pickup", "zip": zip_code, "message":
                              f"Reserved. The donor has been notified; pickup in {zip_code}."}
    reserved = client.get("/api/items?status=reserved").json()["items"]
    assert [i["id"] for i in reserved] == [top["item_id"]]

    events = client.get("/api/events").json()["events"]
    last = events[-1]
    assert last["event_type"] == "match_accepted" and last["category"] == top["item"]["category"]
    assert last["message"] == f"{top['item_id']} reserved; donor notified, pickup in {zip_code}"


def test_accept_errors():
    body = _request()
    req_id, [first, second, *_] = body["request_id"], body["matches"]
    assert _accept("req_9999", first["item_id"]).status_code == 404
    assert _accept(req_id, "itm_9999").status_code == 404
    assert _accept(req_id, first["item_id"]).status_code == 200
    assert _accept(req_id, second["item_id"]).status_code == 409      # request closed

    other = client.post("/api/requests", json=CHICAGO).json()
    assert first["item_id"] not in [m["item_id"] for m in other["matches"]]   # reserved now
    assert _accept(other["request_id"], other["matches"][0]["item_id"]).status_code == 200


def test_two_requests_racing_for_one_item():
    a, b = _request(), client.post("/api/requests", json=CHICAGO).json()
    item_id = a["matches"][0]["item_id"]
    assert item_id in [m["item_id"] for m in b["matches"]]
    assert _accept(a["request_id"], item_id).status_code == 200
    assert _accept(b["request_id"], item_id).status_code == 409


def test_item_being_listed_cannot_be_accepted():
    body = _request()
    item_id = body["matches"][0]["item_id"]
    orchestrator._listing_now.add(item_id)
    assert _accept(body["request_id"], item_id).status_code == 409
