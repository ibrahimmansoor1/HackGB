"""Call every API endpoint on a running backend and print PASS/FAIL.

    # terminal 1: uvicorn app.main:app --port 8000
    # terminal 2 (from backend/, venv active):
    python scripts/smoke_test.py                 # or: python scripts/smoke_test.py http://host:8000

Uses the demo flow from docs/07. Marketplace calls stay in dry run unless you
configured live Nostr keys. Restart the backend first for a clean inventory.
"""
import sys

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
CHICAGO = {"text": "need a warm coat, moving to Chicago in December", "zip": "60601"}
results: list[bool] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ->  {detail}" if detail else ""))


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=30)
    try:
        r = c.get("/api/health")
    except httpx.ConnectError:
        print(f"Can't reach {BASE}. Start the backend first: uvicorn app.main:app --port 8000")
        return 1
    check("GET  /api/health", r.status_code == 200 and r.json()["status"] == "ok",
          f"stubs={r.json().get('stubs')}")
    start = c.get("/api/events").json()["events"]
    after = start[-1]["id"] if start else 0

    r = c.post("/api/admin/seed")
    check("POST /api/admin/seed", r.status_code == 200, str(r.json()))

    items = c.get("/api/items", params={"status": "available"}).json()["items"]
    check("GET  /api/items?status=available", len(items) >= 1, f"{len(items)} available")

    photo = items[0]["image_url"] if items else ""
    path = photo.split("/static/", 1)[-1] if "/static/" in photo else ""
    r = c.get(f"/static/{path}") if path else None
    check("GET  seed photo", r is not None and r.status_code == 200, photo)

    r = c.post("/api/items", data={"zip": "54301",
                                   "note": "Black puffer jacket, hooded, water-resistant, size M"})
    donated = r.json() if r.status_code == 201 else {}
    check("POST /api/items (donate)", r.status_code == 201,
          donated.get("summary", r.text[:120]))

    r = c.post("/api/requests", json=CHICAGO)
    body = r.json() if r.status_code == 201 else {}
    matches = body.get("matches", [])
    check("POST /api/requests (Chicago coat)",
          r.status_code == 201 and body.get("status") == "matched"
          and "insulated" in body["query"]["must_have"],
          f"must_have={body.get('query', {}).get('must_have')}")
    for m in matches:
        print(f"        #{m['rank']} {m['item']['item']} ({m['score']}) - {m['reason']}")
    if donated:
        check("  donated jacket is among the matches",
              donated["id"] in [m["item_id"] for m in matches])

    available = c.get("/api/items", params={"status": "available"}).json()["items"]
    target = available[0]["id"] if available else "itm_none"
    r = c.post(f"/api/items/{target}/list")
    listing = r.json().get("listing", {}) if r.status_code == 200 else {}
    check(f"POST /api/items/{target}/list", r.status_code == 200,
          f"${listing.get('price')} dry_run={listing.get('dry_run')} {listing.get('url', r.text)[:70]}")

    r = c.get("/api/listings", params={"status": "active"})
    check("GET  /api/listings?status=active", r.status_code == 200 and
          target in [x["item_id"] for x in r.json()["listings"]])

    r = c.post("/api/admin/simulate-expiry")
    check("POST /api/admin/simulate-expiry", r.status_code == 200 and target in r.json()["expired"],
          str(r.json()))

    r = c.get("/api/events", params={"after": after})
    events = r.json()["events"]
    agents = {e["agent"] for e in events}
    check("GET  /api/events?after=", {"orchestrator", "parser", "requester"} <= agents,
          f"{len(events)} new events")
    for e in events:
        print(f"        {e['id']:>3} {e['agent']:<12} {e['message']}")

    check("error 404 unknown item", c.post("/api/items/itm_nope/list").status_code == 404)
    check("error 400 empty donation", c.post("/api/items", data={"zip": "54301"}).status_code == 400)
    check("error 415 wrong file type", c.post(
        "/api/items", data={"zip": "54301"},
        files={"image": ("x.html", b"<b>hi</b>", "text/html")}).status_code == 415)
    check("error 422 bad status filter",
          c.get("/api/items", params={"status": "bogus"}).status_code == 422)

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
