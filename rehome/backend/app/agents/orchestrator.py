"""Orchestrator: the ONLY module that reads/writes the database.
Flows and ranking rules are specified in docs/02 and docs/05."""
import asyncio
from datetime import datetime, timedelta, timezone
from app.agents import parser, requester, stub_rules
from app.agents.events import emit
from app.core import config, db, llm
from app.integrations import marketplace
from app.seed_data import SEED_ITEMS, summary as seed_summary
from app.schemas import (AgentEvent, ExpiryOut, Item, Listing, ListItemOut, Match,
                         ParsedItem, RequestOut)

REASON_PROMPT = """For each candidate item, write one reason (max 12 words) explaining why it
fits this request, or what it lacks. Return ONLY a JSON array of
{"item_id": "...", "reason": "..."}."""

# Stub embeddings score much lower than real ones.
THRESHOLD = 0.2 if config.USE_STUBS else config.MATCH_THRESHOLD
LISTING_DAYS = 30
_listing_now: set[str] = set()   # items being published; guards double-clicks and matching


class FlowError(Exception):
    """A flow can't proceed; routers turn this into an HTTP error."""
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _public(row: dict) -> Item:
    return Item.model_validate({k: v for k, v in row.items() if k != "embedding"})


def _label(p: ParsedItem) -> str:
    """'black Columbia puffer jacket, size M' for feed messages."""
    name = " ".join(w for w in (p.color, p.brand, p.item) if w)
    return name + (f", size {p.size}" if p.size else "")


def _embed_text(p: dict) -> str:
    return " ".join([p["summary"], *p["attributes"], p["item"], p["category"],
                     p.get("season") or ""]).strip()


# ---- reads for routers (routers never import db) ---------------------------
def new_item_id() -> str:
    return db.new_item_id()


def items(status: str | None = None) -> list[Item]:
    return [_public(r) for r in db.list_items(status)]


def events(after: int = 0) -> list[AgentEvent]:
    return [AgentEvent.model_validate(e) for e in db.list_events(after)]


def db_backend() -> str:
    """`tiger` or `memory`, for /api/health."""
    return db.BACKEND


# ---- donor path: D1 -> D4 --------------------------------------------------
async def donate(note: str | None, zip_code: str, donor_id: str,
                 image_bytes: bytes | None, image_mime: str,
                 image_url: str | None, item_id: str) -> Item:
    emit("orchestrator", "New donation received", item_id=item_id)
    parsed = await parser.parse_item(note, [(image_bytes, image_mime)] if image_bytes else [])
    emit("parser", f"Identified {_label(parsed)}", item_id=item_id,
         event_type="item_parsed", category=parsed.category)
    return await store(parsed, note, zip_code, donor_id, image_url, item_id)


async def store(parsed: ParsedItem, note: str | None, zip_code: str,
                donor_id: str, image_url: str | None, item_id: str) -> Item:
    vec = await llm.embed(_embed_text(parsed.model_dump()))
    row = {**parsed.model_dump(), "id": item_id, "donor_id": donor_id, "note": note,
           "zip": zip_code, "image_url": image_url, "status": "available",
           "embedding": vec, "created_at": db.now()}
    db.insert_item(row)
    emit("orchestrator", f"Saved {item_id} as available", item_id=item_id,
         event_type="item_donated", category=parsed.category)
    return _public(row)


# ---- requester path: R1 -> R6 ----------------------------------------------
async def handle_request(text: str, zip_code: str, requester_id: str) -> RequestOut:
    req_id = db.new_request_id()
    emit("orchestrator", f"New request from {zip_code}", request_id=req_id,
         event_type="request_made")

    query = await requester.parse_request(text, zip_code)
    ctx = ", ".join(query.inferred_context) or "no extra context"
    need = ", ".join(query.must_have) or "nothing specific"
    emit("requester", f"Inferred {ctx}; needs {need}", request_id=req_id)

    qvec = await llm.embed(query.search_text)
    # Items mid-listing are still `available` in the DB; never reserve one.
    # Stub mode re-ranks harder (stub_fit), so it searches a wider pool first.
    pool = config.TOP_K * (3 if config.USE_STUBS else 1)
    candidates = [(r, s) for r, s in db.vector_search(qvec, top_k=pool + len(_listing_now))
                  if r["id"] not in _listing_now][:pool]
    emit("orchestrator", f"Found {len(candidates)} candidates", request_id=req_id)

    # threshold + must_have boost
    ranked = []
    for row, score in candidates:
        if score < THRESHOLD:
            continue
        hits = sum(stub_rules.satisfies(row["attributes"], a) for a in query.must_have)
        final = score + 0.05 * hits
        if config.USE_STUBS:
            final += stub_rules.stub_fit(query.model_dump(), row)
            if final < THRESHOLD:
                continue
        ranked.append((row, score, final))
    ranked.sort(key=lambda x: x[2], reverse=True)
    ranked = ranked[:config.TOP_K]

    reasons = await _reasons(query, [r for r, _, _ in ranked])
    # The reasons call can take seconds with a real model; drop anything that
    # got listed or reserved meanwhile so we never reserve an unavailable item.
    ranked = [(row, score, final) for row, score, final in ranked
              if _still_available(row["id"])]
    matches = [Match(item_id=row["id"], rank=i + 1, score=round(score, 3),
                     reason=reasons.get(row["id"], "Similar to what you asked for"),
                     item=_public(row))
               for i, (row, score, _) in enumerate(ranked)]

    status = "matched" if matches else "open"
    db.insert_request({**query.model_dump(), "id": req_id, "requester_id": requester_id,
                       "raw_text": text, "zip": zip_code, "embedding": qvec,
                       "status": status, "created_at": db.now()})
    db.insert_matches([{"request_id": req_id, "item_id": m.item_id, "score": m.score,
                        "rank": m.rank, "reason": m.reason, "status": "suggested"}
                       for m in matches])
    if matches:
        db.update_item_status(matches[0].item_id, "reserved")
        emit("orchestrator", f"Matched {matches[0].item_id} ({matches[0].score}) and reserved it",
             request_id=req_id, item_id=matches[0].item_id,
             event_type="match_made", category=matches[0].item.category)
    else:
        emit("orchestrator", "No good match yet; request left open", request_id=req_id)

    return RequestOut(request_id=req_id, status=status, query=query, matches=matches)


def _still_available(item_id: str) -> bool:
    """Fresh read: search rows are snapshots once the DB is Postgres."""
    row = db.get_item(item_id)
    return row is not None and row["status"] == "available" and item_id not in _listing_now


async def _reasons(query, rows: list[dict]) -> dict[str, str]:
    if not rows:
        return {}
    if config.USE_STUBS:
        q = query.model_dump()
        return {r["id"]: stub_rules.reason(q, r) for r in rows}
    cands = [{"item_id": r["id"], "summary": r["summary"], "attributes": r["attributes"]}
             for r in rows]
    try:
        out = await llm.complete_json(REASON_PROMPT,
                                      f"Request: {query.model_dump_json()}\nCandidates: {cands}")
        return {o["item_id"]: o["reason"] for o in out}
    except Exception:
        q = query.model_dump()
        return {r["id"]: stub_rules.reason(q, r) for r in rows}


# ---- demo seed ---------------------------------------------------------------
_seeded: list[str] = []


async def seed_demo() -> int:
    """Load SEED_ITEMS once (pre-parsed, no model call). Calling it again is a
    no-op so a double-click doesn't duplicate the inventory."""
    if not _seeded:
        # Tiger keeps data across restarts; don't seed twice.
        _seeded.extend(r["id"] for r in db.list_items()
                       if "/static/seed/" in (r.get("image_url") or ""))
    if _seeded:
        emit("orchestrator", f"Demo inventory already loaded ({len(_seeded)} items)")
        return 0
    for cat, item, color, size, cond, season, attrs, note, zip_code, photo in SEED_ITEMS:
        parsed = {"category": cat, "item": item, "color": color, "size": size,
                  "condition": cond, "season": season, "attributes": attrs,
                  "summary": seed_summary(color, item, size, cond, attrs)}
        ParsedItem.model_validate(parsed)
        item_id = db.new_item_id()
        db.insert_item({**parsed, "id": item_id, "donor_id": "demo_donor", "note": note,
                        "zip": zip_code,
                        "image_url": config.public_url(f"/static/seed/{photo}.png"),
                        "status": "available", "embedding": await llm.embed(_embed_text(parsed)),
                        "created_at": db.now()})
        _seeded.append(item_id)
    emit("orchestrator", f"Loaded {len(_seeded)} demo items into inventory")
    return len(_seeded)


# ---- marketplace (stretch): list -> 30 days unsold -> donation pool --------
async def list_item(item_id: str, platform: str = "nostr") -> ListItemOut:
    row = db.get_item(item_id)
    if row is None:
        raise FlowError(404, f"Item {item_id} not found.")
    if row["status"] != "available" or item_id in _listing_now:
        status = "being listed" if item_id in _listing_now else row["status"]
        raise FlowError(409, f"Item {item_id} is {status}; only available items can be listed.")
    channel = marketplace.get_channel(platform)
    _listing_now.add(item_id)
    try:
        price = marketplace.suggest_price(row)
        emit("orchestrator", f"Priced {item_id} at ${price} ({row['category']}, {row['condition']})",
             item_id=item_id)
        try:
            result = await channel.publish(row, price)
        except Exception as e:
            emit("orchestrator", f"Couldn't list {item_id} on {channel.label}: {e}", item_id=item_id)
            raise FlowError(502, f"Couldn't list on {channel.label}: {e}") from e

        ok = len(result["relays_accepted"])
        total = ok + len(result["relays_failed"])
        if not result["dry_run"] and ok == 0:
            emit("orchestrator", f"Couldn't list {item_id} on {channel.label} — 0/{total} relays "
                 "accepted; item stays available", item_id=item_id)
            raise FlowError(502, f"No {channel.label} relay accepted the listing (0/{total}).")

        listed_at = datetime.fromtimestamp(result["published_at"], timezone.utc)
        listing = {"id": db.new_listing_id(), "item_id": item_id, "platform": channel.platform,
                   "external_id": result["event_id"], "price": float(price),
                   "listed_at": listed_at, "expires_at": listed_at + timedelta(days=LISTING_DAYS),
                   "url": result["url"], "status": "active", "dry_run": result["dry_run"],
                   "relays_accepted": result["relays_accepted"]}
        db.insert_listing(listing)
        db.update_item_status(item_id, "listed")
        how = "(dry run)" if result["dry_run"] else f"— {ok}/{total} relays"
        emit("orchestrator", f"Listed {item_id} on {channel.label} {how}", item_id=item_id)
        return ListItemOut(item=_public(db.get_item(item_id)),
                           listing=Listing.model_validate(listing))
    finally:
        _listing_now.discard(item_id)


async def expire_listings() -> ExpiryOut:
    """Demo fast-forward: treat every active listing as 30 days old. Close it on
    the marketplace and return the item to the donation pool (available)."""
    due = []
    for lst in db.list_listings("active"):
        db.update_listing(lst["id"], status="expired")
        row = db.get_item(lst["item_id"])
        if row is not None and row["status"] == "listed":
            due.append((lst, row))
    if not due:
        emit("orchestrator", "No active listings to expire")
        return ExpiryOut(expired=[])

    async def close(lst: dict, row: dict) -> str:
        channel = marketplace.get_channel(lst["platform"])
        try:
            res = await channel.mark_sold(row, lst["price"], int(lst["listed_at"].timestamp()))
            if res["dry_run"] or res["relays_accepted"]:
                return ""
        except Exception:
            pass
        return f" (couldn't close the {channel.label} listing; it may still show)"

    notes = await asyncio.gather(*(close(lst, row) for lst, row in due))
    expired = []
    for (lst, row), note in zip(due, notes):
        db.update_item_status(row["id"], "available")
        expired.append(row["id"])
        emit("orchestrator", f"30 days unsold — {row['id']} moved to donation pool{note}",
             item_id=row["id"])
    return ExpiryOut(expired=expired)


def listings(status: str | None = None) -> list[Listing]:
    return [Listing.model_validate(r) for r in db.list_listings(status)]
