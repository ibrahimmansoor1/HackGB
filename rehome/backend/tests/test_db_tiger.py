"""Tiger Data backend tests. Skipped unless TEST_DATABASE_URL is set.

    TEST_DATABASE_URL="postgres://..." pytest tests/test_db_tiger.py

WARNING: deletes every row in the database it points at. Use a separate
Tiger Cloud service (or a fork) for tests, not the demo database.
"""
import os
from datetime import timedelta

import numpy as np
import pytest

from app.core import config, llm

URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture()
def tdb(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", URL)
    from app.core import db_tiger
    db_tiger.close()
    db_tiger.init_schema()
    db_tiger.reset()
    yield db_tiger
    db_tiger.close()


def _item(db, item, attrs, status="available"):
    text = f"{item} {' '.join(attrs)}"
    row = {"id": db.new_item_id(), "donor_id": "demo_donor", "image_url": None, "note": None,
           "zip": "02115", "category": "outerwear", "item": item, "color": "black",
           "size": "M", "condition": "good", "season": "winter", "attributes": attrs,
           "summary": text, "embedding": llm._stub_embed(text), "status": status,
           "created_at": db.now()}
    return db.insert_item(row)


def test_ids_count_up(tdb):
    assert tdb.new_item_id() == "itm_0001"
    assert tdb.new_item_id() == "itm_0002"
    assert tdb.new_request_id() == "req_0001"
    assert tdb.new_listing_id() == "lst_0001"


def test_item_roundtrip(tdb):
    row = _item(tdb, "puffer jacket", ["insulated", "hooded"])
    got = tdb.get_item(row["id"])
    assert got["item"] == "puffer jacket" and got["attributes"] == ["insulated", "hooded"]
    assert len(got["embedding"]) == config.EMBED_DIM
    assert np.allclose(got["embedding"], row["embedding"], atol=1e-6)
    assert tdb.get_item("itm_9999") is None
    tdb.update_item_status(row["id"], "reserved")
    assert [r["id"] for r in tdb.list_items("reserved")] == [row["id"]]
    assert tdb.list_items("available") == []


def test_vector_search_matches_stub_cosine(tdb):
    a = _item(tdb, "puffer jacket", ["insulated", "hooded", "winter"])
    b = _item(tdb, "linen shirt", ["lightweight", "breathable", "summer"])
    c = _item(tdb, "wool coat", ["insulated", "warm", "winter"], status="reserved")
    q = llm._stub_embed("insulated winter jacket")
    res = tdb.vector_search(q, top_k=5)
    ids = [r["id"] for r, _ in res]
    assert ids[0] == a["id"] and c["id"] not in ids and b["id"] in ids
    for row, score in res:  # same number the in-memory stub computes
        v = np.asarray(row["embedding"])
        expect = float(np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v)))
        assert score == pytest.approx(expect, abs=1e-5)
    assert len(tdb.vector_search(q, top_k=1)) == 1
    assert [r["id"] for r, _ in tdb.vector_search(q, 5, status="reserved")] == [c["id"]]


def test_requests_matches_events(tdb):
    item = _item(tdb, "puffer jacket", ["insulated"])
    rid = tdb.new_request_id()
    tdb.insert_request({"id": rid, "requester_id": "demo_requester", "raw_text": "warm coat",
                        "zip": "60601", "need": "coat", "inferred_context": ["snow"],
                        "must_have": ["insulated"], "nice_to_have": [], "size": None,
                        "search_text": "insulated coat",
                        "embedding": llm._stub_embed("insulated coat"),
                        "status": "matched", "created_at": tdb.now()})
    tdb.insert_matches([{"request_id": rid, "item_id": item["id"], "score": 0.9, "rank": 1,
                         "reason": "warm", "status": "suggested"}])
    tdb.insert_matches([])
    e1 = tdb.insert_event({"agent": "orchestrator", "message": "a", "item_id": None,
                           "request_id": rid, "created_at": tdb.now()})
    e2 = tdb.insert_event({"agent": "parser", "message": "b", "item_id": item["id"],
                           "request_id": None, "created_at": tdb.now()})
    assert e2["id"] > e1["id"]
    assert [e["message"] for e in tdb.list_events()] == ["a", "b"]
    assert [e["message"] for e in tdb.list_events(after=e1["id"])] == ["b"]
    assert len(tdb.list_events(limit=1)) == 1


def test_listings(tdb):
    item = _item(tdb, "snow boots", ["waterproof"])
    now = tdb.now()
    lst = {"id": tdb.new_listing_id(), "item_id": item["id"], "platform": "nostr",
           "external_id": "abc", "price": 12.0, "listed_at": now,
           "expires_at": now + timedelta(days=30), "url": "https://shopstr.store/listing/x",
           "status": "active", "dry_run": True, "relays_accepted": []}
    tdb.insert_listing(lst)
    assert tdb.list_listings("active")[0]["relays_accepted"] == []
    tdb.update_listing(lst["id"], status="expired")
    assert tdb.list_listings("active") == [] and len(tdb.list_listings("expired")) == 1
    with pytest.raises(ValueError):
        tdb.update_listing(lst["id"], bogus=1)


def test_info(tdb):
    info = tdb.info()
    assert info["backend"] == "tiger" and "vector" in info["extensions"]
    assert info["vector_index"] in ("diskann", "hnsw")
