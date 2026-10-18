"""Sell/donate split, donate side: POST /api/items/parse -> /{draft_id}/donate (docs/04)."""
from datetime import timedelta

from fastapi.testclient import TestClient

from app.core import config, db
from app.main import app
from app.schemas import ParsedItem

client = TestClient(app)
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
JACKET = {"zip": "54311", "text": "Black puffer jacket, hooded, water-resistant, size M"}


def _parse(**data):
    return client.post("/api/items/parse", data={**JACKET, **data})


def test_parse_returns_draft_and_stores_no_item():
    r = _parse()
    assert r.status_code == 201
    body = r.json()
    assert body["draft_id"].startswith("drf_") and body["options"] == ["sell", "donate"]
    assert set(body["item"]) == set(ParsedItem.model_fields)
    assert body["item"]["item"] == "puffer jacket" and body["item"]["brand"] is None
    assert body["image_url"] is None
    assert client.get("/api/items").json()["items"] == []


def test_parse_saves_first_photo_under_the_draft_id():
    r = client.post("/api/items/parse", data={"zip": "54311"},
                    files=[("images", ("a.png", PNG, "image/png")),
                           ("images", ("b.jpg", b"\xff\xd8\xff", "image/jpeg"))])
    body = r.json()
    assert r.status_code == 201 and body["item"]["item"] == "puffer jacket"
    assert body["image_url"] == f"{config.PUBLIC_BASE_URL}/static/uploads/{body['draft_id']}.png"
    assert client.get(body["image_url"].removeprefix(config.PUBLIC_BASE_URL)).content == PNG
    (config.UPLOAD_DIR / f"{body['draft_id']}.png").unlink()


def test_parse_rejects_bad_input():
    assert client.post("/api/items/parse", data={"zip": "54311"}).status_code == 400
    assert client.post("/api/items/parse", data={"zip": "54311", "text": "  "}).status_code == 400
    assert client.post("/api/items/parse", data={"text": "coat"}).status_code == 422
    r = client.post("/api/items/parse", data={"zip": "54311"},
                    files={"images": ("x.html", b"<b>", "text/html")})
    assert r.status_code == 415
    r = client.post("/api/items/parse", data={"zip": "54311"},
                    files={"images": ("big.png", b"\0" * (10 * 1024 * 1024 + 1), "image/png")})
    assert r.status_code == 413
    r = client.post("/api/items/parse", data={"zip": "54311"},
                    files={"images": ("empty.png", b"", "image/png")})
    assert r.status_code == 400


def test_donate_makes_it_searchable_and_consumes_the_draft():
    draft = _parse().json()
    r = client.post(f"/api/items/{draft['draft_id']}/donate")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "available" and body["item_id"].startswith("itm_")
    assert body["message"] == "Thanks! Your puffer jacket is now searchable."
    [item] = client.get("/api/items?status=available").json()["items"]
    assert item["id"] == body["item_id"] and item["zip"] == "54311"
    assert item["summary"] == draft["item"]["summary"] and item["note"] == JACKET["text"]
    assert client.post(f"/api/items/{draft['draft_id']}/donate").status_code == 404

    matches = client.post("/api/requests", json={"text": "need a warm coat, moving to Chicago "
                                                         "in December", "zip": "60601"}).json()
    assert body["item_id"] in [m["item_id"] for m in matches["matches"]]


def test_donate_pickup_zip_overrides_the_draft_zip():
    draft_id = _parse().json()["draft_id"]
    r = client.post(f"/api/items/{draft_id}/donate", json={"pickup_zip": "60601"})
    assert client.get("/api/items").json()["items"][0]["zip"] == "60601"
    assert r.status_code == 201


def test_unknown_or_expired_draft_is_404():
    assert client.post("/api/items/drf_9999/donate").status_code == 404
    draft_id = _parse().json()["draft_id"]
    db._drafts[draft_id]["created_at"] -= timedelta(hours=25)
    assert client.post(f"/api/items/{draft_id}/donate").status_code == 404


def test_parse_and_donate_events():
    draft_id = _parse().json()["draft_id"]
    item_id = client.post(f"/api/items/{draft_id}/donate").json()["item_id"]
    events = client.get("/api/events").json()["events"]
    steps = [(e["agent"], e["event_type"], e["message"]) for e in events]
    assert steps == [
        ("orchestrator", None, "New item received"),
        ("parser", "item_parsed", "Identified black puffer jacket, size M"),
        ("orchestrator", "item_donated", f"Saved {item_id} as available"),
    ]
    assert events[-1]["category"] == "outerwear" and events[-1]["item_id"] == item_id


def test_parser_failure_is_502(monkeypatch):
    from app.agents import parser

    async def broken(*a):
        raise ValueError("model down")
    monkeypatch.setattr(parser, "parse_item", broken)
    assert _parse().status_code == 502
    assert client.post("/api/items", data={"zip": "1", "note": "coat"}).status_code == 502
