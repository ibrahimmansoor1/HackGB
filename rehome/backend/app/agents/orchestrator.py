"""Orchestrator: the ONLY module that reads/writes the database.
Flows and ranking rules are specified in docs/02 and docs/05."""
import asyncio
from datetime import datetime, timedelta, timezone
from app.agents import parser, requester
from app.agents.events import emit
from app.core import config, db, llm
from app.integrations import marketplace
from app.schemas import (ExpiryOut, Item, Listing, ListItemOut, Match, ParsedItem,
                         RequestOut)

REASON_PROMPT = """For each candidate item, write one reason (max 12 words) explaining why it
fits this request, or what it lacks. Return ONLY a JSON array of
{"item_id": "...", "reason": "..."}."""

# Stub embeddings score much lower than real ones.
THRESHOLD = 0.15 if config.USE_STUBS else config.MATCH_THRESHOLD
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


# ---- donor path: D1 -> D4 --------------------------------------------------
async def donate(note: str | None, zip_code: str, donor_id: str,
                 image_bytes: bytes | None, image_mime: str,
                 image_url: str | None, item_id: str) -> Item:
    emit("orchestrator", "New donation received", item_id=item_id)
    parsed = await parser.parse_item(note, image_bytes, image_mime)
    emit("parser", f"Identified {parsed.color} {parsed.item}"
         + (f", size {parsed.size}" if parsed.size else ""), item_id=item_id)
    return await store(parsed, note, zip_code, donor_id, image_url, item_id)


async def store(parsed: ParsedItem, note: str | None, zip_code: str,
                donor_id: str, image_url: str | None, item_id: str) -> Item:
    vec = await llm.embed(f"{parsed.summary} {' '.join(parsed.attributes)} {parsed.item}")
    row = {**parsed.model_dump(), "id": item_id, "donor_id": donor_id, "note": note,
           "zip": zip_code, "image_url": image_url, "status": "available",
           "embedding": vec, "created_at": db.now()}
    db.insert_item(row)
    emit("orchestrator", f"Saved {item_id} as available", item_id=item_id)
    return _public(row)


# ---- requester path: R1 -> R6 ----------------------------------------------
async def handle_request(text: str, zip_code: str, requester_id: str) -> RequestOut:
    req_id = db.new_request_id()
    emit("orchestrator", f"New request from {zip_code}", request_id=req_id)

    query = await requester.parse_request(text, zip_code)
    ctx = ", ".join(query.inferred_context) or "no extra context"
    need = ", ".join(query.must_have) or "nothing specific"
    emit("requester", f"Inferred {ctx}; needs {need}", request_id=req_id)

    qvec = await llm.embed(query.search_text)
    # Items mid-listing are still `available` in the DB; never reserve one.
    candidates = [(r, s) for r, s in db.vector_search(qvec, top_k=config.TOP_K + len(_listing_now))
                  if r["id"] not in _listing_now][:config.TOP_K]
    emit("orchestrator", f"Found {len(candidates)} candidates", request_id=req_id)

    # threshold + must_have boost
    ranked = []
    for row, score in candidates:
        if score < THRESHOLD:
            continue
        hits = sum(a in row["attributes"] for a in query.must_have)
        ranked.append((row, score, score + 0.05 * hits))
    ranked.sort(key=lambda x: x[2], reverse=True)

    reasons = await _reasons(query, [r for r, _, _ in ranked])
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
             request_id=req_id, item_id=matches[0].item_id)
    else:
        emit("orchestrator", "No good match yet; request left open", request_id=req_id)

    return RequestOut(request_id=req_id, status=status, query=query, matches=matches)


async def _reasons(query, rows: list[dict]) -> dict[str, str]:
    if not rows:
        return {}
    if config.USE_STUBS:
        return {r["id"]: f"{r['item'].capitalize()}: {', '.join(r['attributes'][:3])}" for r in rows}
    cands = [{"item_id": r["id"], "summary": r["summary"], "attributes": r["attributes"]}
             for r in rows]
    try:
        out = await llm.complete_json(REASON_PROMPT,
                                      f"Request: {query.model_dump_json()}\nCandidates: {cands}")
        return {o["item_id"]: o["reason"] for o in out}
    except Exception:
        return {}


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
