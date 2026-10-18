"""The docs/07 demo, end to end, with no API keys (stub mode). cd backend && pytest"""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents import stub_rules
from app.core import config
from app.integrations import marketplace
from app.main import app
from app.schemas import Item

client = TestClient(app)
CHICAGO = {"text": "need a warm coat, moving to Chicago in December", "zip": "60601"}
ITEM_FIELDS = set(Item.model_fields)   # docs/03 items, minus embedding
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    assert config.USE_STUBS, "demo tests expect stub mode (no MODAL_ENDPOINT_URL)"
    monkeypatch.setattr(config, "MARKETPLACE_DRY_RUN", True)
    monkeypatch.setattr(config, "NOSTR_NSEC", "")

    def no_network():
        raise AssertionError("tests must never open a real relay connection")
    monkeypatch.setattr(marketplace, "_new_client", no_network)


def _messages(after=0):
    return [e["message"] for e in client.get(f"/api/events?after={after}").json()["events"]]


def _last_event_id():
    events = client.get("/api/events").json()["events"]
    return events[-1]["id"] if events else 0


# ---- seed ------------------------------------------------------------------
def test_seed_loads_18_varied_items_with_docs_fields():
    assert client.post("/api/admin/seed").json() == {"seeded": 18}
    items = client.get("/api/items?status=available").json()["items"]
    assert len(items) == 18
    for it in items:
        assert set(it) == ITEM_FIELDS and "embedding" not in it
        assert it["donor_id"] == "demo_donor" and it["note"] and re.fullmatch(r"\d{5}", it["zip"])
        assert it["status"] == "available" and 2 <= len(it["attributes"]) <= 6
        assert it["image_url"].startswith(config.PUBLIC_BASE_URL + "/static/seed/")
    assert len({it["category"] for it in items}) >= 7
    assert "Loaded 18 demo items into inventory" in _messages()


def test_seed_twice_does_not_duplicate():
    client.post("/api/admin/seed")
    assert client.post("/api/admin/seed").json() == {"seeded": 0}
    assert len(client.get("/api/items").json()["items"]) == 18


def test_seed_photos_are_served():
    client.post("/api/admin/seed")
    for it in client.get("/api/items").json()["items"]:
        path = it["image_url"].removeprefix(config.PUBLIC_BASE_URL)
        r = client.get(path)
        assert r.status_code == 200 and r.headers["content-type"] == "image/png", path


# ---- donor path ------------------------------------------------------------
def test_donate_note_is_parsed():
    r = client.post("/api/items", data={"zip": "54301",
                                        "note": "Black puffer jacket, size M, barely worn"})
    assert r.status_code == 201
    it = r.json()
    assert set(it) == ITEM_FIELDS
    assert (it["category"], it["item"], it["color"], it["size"], it["condition"]) == \
        ("outerwear", "puffer jacket", "black", "M", "like new")
    assert it["season"] == "winter" and "insulated" in it["attributes"]
    assert it["status"] == "available" and it["image_url"] is None


def test_donate_photo_only_gets_absolute_url_and_is_served():
    r = client.post("/api/items", data={"zip": "54301"},
                    files={"image": ("jacket.png", PNG, "image/png")})
    assert r.status_code == 201
    it = r.json()
    assert it["item"] == "puffer jacket"      # what the stub "sees" in a photo
    assert it["image_url"] == f"{config.PUBLIC_BASE_URL}/static/uploads/{it['id']}.png"
    served = client.get(it["image_url"].removeprefix(config.PUBLIC_BASE_URL))
    assert served.status_code == 200 and served.content == PNG
    (config.UPLOAD_DIR / f"{it['id']}.png").unlink()


def test_donate_photo_and_note():
    r = client.post("/api/items", data={"zip": "54301", "note": "brown snow boots, size 9"},
                    files={"image": ("boots.jpg", b"\xff\xd8\xff" + b"\0" * 32, "image/jpeg")})
    it = r.json()
    assert r.status_code == 201 and it["item"] == "snow boots" and it["size"] == "9"
    assert it["image_url"].endswith(".jpg")
    (config.UPLOAD_DIR / f"{it['id']}.jpg").unlink()


def test_donate_rejects_bad_input():
    assert client.post("/api/items", data={"zip": "54301"}).status_code == 400
    assert client.post("/api/items", data={"zip": "54301", "note": "   "}).status_code == 400
    r = client.post("/api/items", data={"zip": "54301"},
                    files={"image": ("x.html", b"<script>alert(1)</script>", "text/html")})
    assert r.status_code == 415
    big = b"\0" * (10 * 1024 * 1024 + 1)
    r = client.post("/api/items", data={"zip": "54301"},
                    files={"image": ("big.png", big, "image/png")})
    assert r.status_code == 413
    assert not list(config.UPLOAD_DIR.glob("*.html"))


# ---- requester path --------------------------------------------------------
def test_chicago_request_matches_insulated_outerwear():
    client.post("/api/admin/seed")
    r = client.post("/api/requests", json=CHICAGO)
    assert r.status_code == 201
    body = r.json()
    q = body["query"]
    assert body["status"] == "matched"
    assert {"insulated", "water-resistant"} <= set(q["must_have"])
    assert "snow" in q["inferred_context"] and "chicago" not in q["search_text"].lower()
    matches = body["matches"]
    assert 1 <= len(matches) <= config.TOP_K
    assert [m["rank"] for m in matches] == list(range(1, len(matches) + 1))
    top = matches[0]["item"]
    assert top["category"] == "outerwear" and "insulated" in top["attributes"]
    assert all(m["item"]["category"] != "kids" for m in matches)
    for m in matches:
        assert 0 < m["score"] <= 1 and m["reason"] and len(m["reason"].split()) <= 12
    assert "built for sub-freezing winters" in matches[0]["reason"]
    reserved = client.get("/api/items?status=reserved").json()["items"]
    assert [i["id"] for i in reserved] == [matches[0]["item_id"]]


def test_donated_jacket_is_matched_in_the_demo():
    """docs/07: donate a jacket at the table, then the Chicago request finds it."""
    client.post("/api/admin/seed")
    mine = client.post("/api/items", data={"zip": "54301",
                                           "note": "Black puffer jacket, hooded, water-resistant, size M"}).json()
    ids = [m["item_id"] for m in client.post("/api/requests", json=CHICAGO).json()["matches"]]
    assert mine["id"] in ids


def test_request_for_a_child_only_gets_kids_items():
    client.post("/api/admin/seed")
    body = client.post("/api/requests", json={"text": "winter coat for my daughter",
                                              "zip": "54301"}).json()
    assert body["matches"] and all(m["item"]["category"] == "kids" for m in body["matches"])


@pytest.mark.parametrize("text,expected", [
    ("pots and pans for my first apartment", "cookware set"),
    ("a shirt for a job interview", "dress shirt"),
    ("running shoes", "running shoes"),
    ("rain jacket for Seattle", "rain shell"),
    ("boots for snow, size 9", "snow boots"),
])
def test_requests_find_the_obvious_item(text, expected):
    client.post("/api/admin/seed")
    body = client.post("/api/requests", json={"text": text, "zip": "54301"}).json()
    assert body["matches"][0]["item"]["item"] == expected


def test_no_match_leaves_request_open():
    client.post("/api/admin/seed")
    body = client.post("/api/requests", json={"text": "a unicorn costume", "zip": "54301"}).json()
    assert body["status"] == "open" and body["matches"] == []
    assert "No good match yet; request left open" in _messages()


# ---- activity feed -----------------------------------------------------------
def test_feed_shows_every_docs05_step():
    client.post("/api/admin/seed")
    start = _last_event_id()
    item_id = client.post("/api/items", data={"zip": "54301", "note": "Black puffer jacket, size M"}
                          ).json()["id"]
    client.post("/api/requests", json=CHICAGO)
    spare = client.get("/api/items?status=available").json()["items"][0]["id"]
    client.post(f"/api/items/{spare}/list")
    client.post("/api/admin/simulate-expiry")

    events = client.get(f"/api/events?after={start}").json()["events"]
    assert [e["id"] for e in events] == sorted(e["id"] for e in events)
    assert all(e["id"] > start for e in events)
    by_agent = {(e["agent"], e["message"]) for e in events}
    msgs = [m for _, m in by_agent]
    steps = [("orchestrator", "New donation received"),
             ("parser", "Identified black puffer jacket, size M"),
             ("orchestrator", f"Saved {item_id} as available"),
             ("orchestrator", "New request from 60601")]
    for step in steps:
        assert step in by_agent, step
    assert any(a == "requester" and m.startswith("Inferred sub-freezing winters, snow; needs "
                                                 "insulated, water-resistant") for a, m in by_agent)
    assert any(re.fullmatch(r"Found \d+ candidates", m) for m in msgs)
    assert any(re.fullmatch(r"Matched itm_\d+ \(0\.\d+\) and reserved it", m) for m in msgs)
    assert any(m.startswith(f"Priced {spare} at $") for m in msgs)
    assert f"Listed {spare} on Shopstr (dry run)" in msgs
    assert f"30 days unsold — {spare} moved to donation pool" in msgs


def test_feed_pages_at_50():
    client.post("/api/admin/seed")
    for _ in range(20):
        client.post("/api/requests", json={"text": "a unicorn costume", "zip": "54301"})
    first = client.get("/api/events?after=0").json()["events"]
    assert len(first) == 50
    rest = client.get(f"/api/events?after={first[-1]['id']}").json()["events"]
    assert rest and rest[0]["id"] == first[-1]["id"] + 1


# ---- marketplace on demo items ---------------------------------------------
def test_list_a_seeded_item_dry_run():
    client.post("/api/admin/seed")
    item = client.get("/api/items").json()["items"][0]
    r = client.post(f"/api/items/{item['id']}/list")
    assert r.status_code == 200
    body = r.json()
    assert body["item"]["status"] == "listed" and body["listing"]["dry_run"] is True
    assert body["listing"]["url"].startswith("https://shopstr.store/listing/naddr1")
    assert [lst["item_id"] for lst in client.get("/api/listings?status=active").json()["listings"]] \
        == [item["id"]]


def test_matched_items_list_unless_reserved():
    """Rank 1 is reserved for the requester (409); the other matches stay listable."""
    client.post("/api/admin/seed")
    matches = client.post("/api/requests", json=CHICAGO).json()["matches"]
    assert len(matches) >= 2
    assert client.post(f"/api/items/{matches[0]['item_id']}/list").status_code == 409
    assert client.post(f"/api/items/{matches[1]['item_id']}/list").status_code == 200


def test_listings_status_filter_is_validated():
    assert client.get("/api/listings?status=bogus").status_code == 422
    assert client.get("/api/items?status=bogus").status_code == 422


# ---- PUBLIC_BASE_URL -> Nostr image tag --------------------------------------
def test_public_base_url_puts_image_on_nostr_listing(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://rehome-demo.example.org")
    client.post("/api/admin/seed")
    item = client.get("/api/items").json()["items"][0]
    assert item["image_url"].startswith("https://rehome-demo.example.org/static/seed/")
    ev = marketplace.build_listing_event({**item, "id": item["id"]}, 10)
    tags = json.loads(ev.as_json())["tags"]
    assert ["image", item["image_url"]] in tags


@pytest.mark.parametrize("url,public", [
    ("https://rehome-demo.example.org/static/seed/a.png", True),
    ("http://203.0.113.7/static/a.png", False),      # documentation range, not global
    ("http://8.8.8.8/a.png", True),
    ("http://localhost:8000/static/a.png", False),
    ("http://127.0.0.1:8000/static/a.png", False),
    ("http://192.168.1.20:8000/static/a.png", False),
    ("http://10.0.0.5/a.png", False),
    ("http://rehome.local/a.png", False),
    ("/static/uploads/a.png", False),
    ("ftp://example.org/a.png", False),
    (None, False),
])
def test_only_public_images_are_tagged(url, public):
    assert marketplace._is_public_image(url) is public


# ---- stub rules (pure) ---------------------------------------------------------
@pytest.mark.parametrize("note,expected", [
    ("Black puffer jacket, size M, barely worn",
     {"category": "outerwear", "item": "puffer jacket", "size": "M", "condition": "like new"}),
    ("warm wool blanket, some pilling",
     {"category": "home", "item": "wool blanket", "size": None, "condition": "fair"}),
    ("kids snow boots size 11, waterproof",
     {"category": "kids", "item": "kids snow boots", "size": "11"}),
    ("Gray running shoes, brand new", {"category": "footwear", "color": "gray", "condition": "new"}),
    ("a box of random stuff", {"category": "other", "item": "donated item"}),
])
def test_parse_note(note, expected):
    parsed = stub_rules.parse_note(note, has_image=False)
    for key, value in expected.items():
        assert parsed[key] == value, (key, parsed)
    assert parsed["summary"].endswith(".")


def test_sizes_are_never_guessed():
    assert stub_rules.find_size("navy wool peacoat") is None
    assert stub_rules.find_size("medium-ish jacket") is None
    assert stub_rules.find_size("pink coat 6T") == "6T"


@pytest.mark.parametrize("text,zip_code,must,ctx", [
    ("need a warm coat, moving to Chicago in December", "60601",
     ["insulated", "water-resistant"], "snow"),
    ("coat for Chicago in July", "60601", ["breathable"], "hot weather"),
    ("rain jacket for Seattle", "98101", ["waterproof"], "frequent rain"),
    ("a winter jacket", "", ["insulated", "water-resistant"], "snow"),
    ("a jacket", "54301", ["insulated", "water-resistant"], "snow"),   # Green Bay zip
    ("running shoes", "54301", [], None),                              # zip alone ≠ snow gear
])
def test_parse_need(text, zip_code, must, ctx):
    q = stub_rules.parse_need(text, zip_code)
    assert q["must_have"] == must
    assert (ctx in q["inferred_context"]) if ctx else q["inferred_context"] == []
    assert not re.search(r"chicago|seattle", q["search_text"], re.I)


def test_routers_never_import_the_db():
    """SOURCE_OF_TRUTH rule 1: only the orchestrator touches the database."""
    routers = Path(__file__).resolve().parents[1] / "app" / "routers"
    for f in routers.glob("*.py"):
        src = f.read_text()
        assert not re.search(r"from app\.core import[^\n]*\bdb\b|import app\.core\.db", src), f.name


def test_empty_photo_without_note_is_rejected():
    r = client.post("/api/items", data={"zip": "54301"},
                    files={"image": ("empty.jpg", b"", "image/jpeg")})
    assert r.status_code == 400
    assert client.get("/api/items").json()["items"] == []


def test_word_sizes_are_normalized():
    assert stub_rules.find_size("fleece, size medium") == "M"
    assert stub_rules.find_size("size L") == "L"


def test_item_reserved_during_reason_call_is_not_matched(monkeypatch):
    """With a real model the reasons call is slow; an item listed meanwhile must
    not be reserved too."""
    from app.agents import orchestrator
    client.post("/api/admin/seed")
    real = orchestrator._reasons

    async def slow_reasons(query, rows):
        out = await real(query, rows)
        rows[0]["status"] = "listed"        # someone listed rank 1 meanwhile
        return out
    monkeypatch.setattr(orchestrator, "_reasons", slow_reasons)

    body = client.post("/api/requests", json=CHICAGO).json()
    listed = {i["id"] for i in client.get("/api/items?status=listed").json()["items"]}
    matched = {m["item_id"] for m in body["matches"]}
    reserved = {i["id"] for i in client.get("/api/items?status=reserved").json()["items"]}
    assert listed and not listed & matched and not listed & reserved
    assert reserved <= matched


def test_seed_image_base_url_overrides_seed_photos(monkeypatch):
    base = "https://raw.githubusercontent.com/shuja-waraich-03/HackGB/main/rehome/backend/static/seed"
    monkeypatch.setattr(config, "SEED_IMAGE_BASE_URL", base)
    client.post("/api/admin/seed")
    item = client.get("/api/items").json()["items"][0]
    assert item["image_url"] == f"{base}/puffer-jacket.png"
    assert marketplace.has_public_image(item)


# ---- listing cards + preview pages -------------------------------------------
def test_listings_carry_item_and_nostr_link():
    client.post("/api/admin/seed")
    item_id = client.get("/api/items").json()["items"][0]["id"]
    listing = client.post(f"/api/items/{item_id}/list").json()["listing"]
    naddr = listing["url"].rsplit("/", 1)[1]
    assert listing["nostr_url"] == f"https://njump.me/{naddr}"
    rows = client.get("/api/listings").json()["listings"]
    assert rows[0]["item_id"] == item_id
    assert rows[0]["item"]["id"] == item_id and rows[0]["item"]["image_url"]
    assert "embedding" not in rows[0]["item"]


def test_preview_pages():
    assert "Nothing listed yet" in client.get("/listings").text
    client.post("/api/admin/seed")
    item = client.get("/api/items").json()["items"][0]
    client.post(f"/api/items/{item['id']}/list")
    shop = client.get("/listings")
    assert shop.status_code == 200 and "text/html" in shop.headers["content-type"]
    assert "Black puffer jacket, size M" in shop.text and "$25" in shop.text
    assert "Dry run" in shop.text and item["image_url"] in shop.text
    page = client.get(f"/listings/{item['id']}")
    assert page.status_code == 200 and "insulated" in page.text
    client.post("/api/admin/simulate-expiry")
    assert "Expired" in client.get(f"/listings/{item['id']}").text
    assert client.get("/listings/itm_nope").status_code == 404


def test_preview_page_escapes_html():
    r = client.post("/api/items", data={"zip": "54301",
                                        "note": "<script>alert(1)</script> black jacket"})
    item_id = r.json()["id"]
    client.post(f"/api/items/{item_id}/list")
    page = client.get(f"/listings/{item_id}").text
    assert "<script>alert(1)</script>" not in page


# ---- demo reset --------------------------------------------------------------
def test_reset_clears_inventory_and_reseeds_from_0001():
    client.post("/api/admin/seed")
    client.post("/api/requests", json=CHICAGO)
    listed = client.get("/api/items?status=available").json()["items"][0]["id"]
    client.post(f"/api/items/{listed}/list")
    last = _last_event_id()

    r = client.post("/api/admin/reset")
    assert r.status_code == 200 and r.json() == {"reset": True, "closed_listings": [listed]}
    assert client.get("/api/items").json()["items"] == []
    assert client.get("/api/listings").json()["listings"] == []
    msgs = _messages(after=last)
    assert f"30 days unsold — {listed} moved to donation pool" in msgs   # closed first
    assert "Demo reset: inventory, requests, and listings cleared" in msgs
    assert all(e["id"] > last for e in client.get(f"/api/events?after={last}").json()["events"])

    assert client.post("/api/admin/seed").json() == {"seeded": 18}
    ids = [i["id"] for i in client.get("/api/items").json()["items"]]
    assert ids[0] == "itm_0001" and len(ids) == 18


def test_reset_with_nothing_listed():
    assert client.post("/api/admin/reset").json() == {"reset": True, "closed_listings": []}
