"""Orchestrator: the ONLY module that reads/writes the database.
Flows and ranking rules are specified in docs/02 and docs/05."""
import asyncio
from datetime import datetime, timedelta, timezone
from app.agents import parser, pricing, requester, stub_rules
from app.agents.events import emit
from app.core import config, db, llm
from app.integrations import ebay, marketplace, websearch
from app.seed_data import SEED_ITEMS, summary as seed_summary
from app.schemas import (AcceptOut, AgentEvent, CategoryImpact, DonateOut, DraftOut, ExpiryOut,
                         Handoff, HourlyImpact, ImpactOut, Item, Listing, ListItemOut, Match, ParsedItem, PriceQuote, RequestOut,
                         SellOut)

REASON_PROMPT = """For each candidate item, write one reason (max 12 words) explaining why it
fits this request, or what it lacks. Return ONLY a JSON array of
{"item_id": "...", "reason": "..."}."""

LISTING_DAYS = 30
DRAFT_TTL = timedelta(hours=24)   # an unsold, undonated draft expires after this
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


def new_draft_id() -> str:
    return db.new_draft_id()


def items(status: str | None = None) -> list[Item]:
    return [_public(r) for r in db.list_items(status)]


def events(after: int = 0, run_id: str | None = None) -> list[AgentEvent]:
    return [AgentEvent.model_validate(e) for e in db.list_events(after, run_id=run_id)]


IMPACT_TOTALS = {"item_parsed": "items_parsed", "item_donated": "items_donated",
                 "price_quoted": "prices_quoted", "request_made": "requests_made",
                 "match_made": "matches_made", "match_accepted": "matches_accepted"}


def impact() -> ImpactOut:
    """Dashboard stats from impact_hourly (docs/04)."""
    totals = dict.fromkeys(IMPACT_TOTALS.values(), 0)
    by_cat: dict[str, CategoryImpact] = {}
    hourly: dict[tuple, int] = {}
    since = (db.now() - timedelta(hours=24)).replace(minute=0, second=0, microsecond=0)
    for r in db.impact_rows():
        key = IMPACT_TOTALS.get(r["event_type"])
        if key is None:
            continue
        totals[key] += r["n"]
        if r["category"] and key in ("items_donated", "matches_accepted"):
            cat = by_cat.setdefault(r["category"], CategoryImpact(category=r["category"]))
            setattr(cat, key, getattr(cat, key) + r["n"])
        if r["bucket"] >= since:
            k = (r["bucket"], r["event_type"])
            hourly[k] = hourly.get(k, 0) + r["n"]
    return ImpactOut(
        totals=totals,
        by_category=sorted(by_cat.values(), key=lambda c: (-c.items_donated, c.category)),
        hourly=[HourlyImpact(bucket=b, event_type=t, n=n) for (b, t), n in sorted(hourly.items())])


def db_backend() -> str:
    """`tiger` or `memory`, for /api/health."""
    return db.BACKEND


# ---- donor path: D1 -> D4, then sell (S) or donate (N) ---------------------
async def _parse(text: str | None, images: list[tuple[bytes, str]],
                 item_id: str | None = None) -> ParsedItem:
    emit("orchestrator", "New item received", item_id=item_id)
    try:
        parsed = await parser.parse_item(text, images)
    except Exception as e:
        emit("orchestrator", f"Couldn't read the item: {e}", item_id=item_id)
        raise FlowError(502, f"The parser couldn't read this item: {e}") from e
    emit("parser", f"Identified {_label(parsed)}", item_id=item_id,
         event_type="item_parsed", category=parsed.category)
    return parsed


async def parse_draft(text: str | None, zip_code: str, donor_id: str,
                      images: list[tuple[bytes, str]], image_url: str | None,
                      draft_id: str) -> DraftOut:
    """D1-D4: parse and keep it as a draft. Nothing goes to `items` yet."""
    parsed = await _parse(text, images)
    db.insert_draft({"id": draft_id, "donor_id": donor_id, "zip": zip_code, "note": text,
                     "image_url": image_url, "item": parsed.model_dump(),
                     "created_at": db.now()})
    return DraftOut(draft_id=draft_id, item=parsed, image_url=image_url)


def _get_draft(draft_id: str) -> dict:
    row = db.get_draft(draft_id)
    if row is None or db.now() - row["created_at"] > DRAFT_TTL:
        raise FlowError(404, f"Draft {draft_id} not found, expired, or already used.")
    return row


async def sell_draft(draft_id: str) -> SellOut:
    """S2-S5: eBay comps -> pricing agent; heuristic estimate when eBay can't help.
    The draft is kept, so the donor can still donate it."""
    item = _get_draft(draft_id)["item"]
    found: list[dict] = []
    if ebay.configured():
        try:
            found = await ebay.search(_comps_query(item))
            emit("orchestrator", f"Found {len(found)} active eBay listings")
        except ebay.EbayError as e:
            emit("orchestrator", f"Couldn't reach eBay ({e}); using an estimate")

    quote, basis = None, "estimate"
    if found:
        try:
            quote = await pricing.quote(item, found)
        except Exception as e:
            emit("pricing", f"Pricing failed: {e}")
            raise FlowError(502, f"The pricing model failed: {e}") from e
        urls = {c["url"] for c in found}
        quote.comps = [c for c in quote.comps if c.url in urls]   # only real listings
        basis = "active listings" if quote.comps else "estimate"
    if basis == "estimate" and websearch.configured():
        quote, basis = await _web_quote(item) or (quote, basis)
    if basis == "estimate":
        quote = _estimate(item)

    p = quote.suggested_price
    label = {"active listings": "currently listed for", "web search": "listed online for",
             "estimate": "estimate"}[basis]
    emit("pricing", f"Suggested ${p.low:g}–{p.high:g} ({label})",
         event_type="price_quoted", category=item["category"])
    return SellOut(draft_id=draft_id, basis=basis, **quote.model_dump())


def _comps_query(item: dict) -> str:
    return " ".join(w for w in (item.get("brand"), item["item"]) if w)


async def _web_quote(item: dict) -> tuple[PriceQuote, str] | None:
    """Brave web search -> pricing agent reads the going rates. None when the
    search or the agent comes up empty (caller uses the estimate)."""
    query = f"used {_comps_query(item)} price"
    try:
        results = await websearch.search(query)
    except websearch.SearchError as e:
        emit("orchestrator", f"Couldn't search the web ({e}); using an estimate")
        return None
    emit("orchestrator", f"Searched the web for “{query}”: {len(results)} results")
    if not results:
        return None
    try:
        quote = await pricing.from_search(item, results)
    except Exception as e:
        emit("pricing", f"Couldn't read prices from the search results ({type(e).__name__})")
        return None
    if not quote.comps:
        emit("pricing", "No comparable prices in the search results; using an estimate")
        return None
    sites = ", ".join(dict.fromkeys(c.source for c in quote.comps))
    emit("pricing", f"Read {len(quote.comps)} going rates online ({sites})")
    return quote, "web search"


def _estimate(item: dict) -> PriceQuote:
    """docs/05 fallback: category x condition midpoint, +/- 20 %, no comps."""
    mid = marketplace.suggest_price(item)
    return PriceQuote.model_validate({
        "suggested_price": {"low": max(1, round(mid * 0.8)), "high": max(1, round(mid * 1.2))},
        "comps": [], "listing_draft": pricing.listing_draft(item)})


async def _draft_to_item(draft_id: str, pickup_zip: str | None,
                         donated: bool) -> tuple[ParsedItem, Item, list[float]]:
    """Embed, claim the draft atomically, insert it as an available item."""
    row = _get_draft(draft_id)
    parsed = ParsedItem.model_validate(row["item"])
    vec = await llm.embed(_embed_text(parsed.model_dump()))   # before claiming the draft
    if db.pop_draft(draft_id) is None:                         # a double-click got it first
        raise FlowError(404, f"Draft {draft_id} was already used.")
    item = await store(parsed, row["note"], (pickup_zip or "").strip() or row["zip"],
                       row["donor_id"], row["image_url"], db.new_item_id(), vec,
                       donated=donated)
    return parsed, item, vec


async def donate_draft(draft_id: str, pickup_zip: str | None = None) -> DonateOut:
    """N1-N3: embed, insert as available, consume the draft; then the
    matchmaker offers it to open requests it could fill."""
    parsed, item, vec = await _draft_to_item(draft_id, pickup_zip, donated=True)
    waiting = await matchmake(item.model_dump(), vec)
    msg = f"Thanks! Your {parsed.item} is now searchable."
    if waiting:
        msg += f" {len(waiting)} open request{'s' * (len(waiting) > 1)} nearby could use it."
    return DonateOut(item_id=item.id, status=item.status, message=msg,
                     waiting_requests=[w["request_id"] for w in waiting])


async def post_draft(draft_id: str, price: float | None = None) -> ListItemOut:
    """Sell path, step 2: the draft becomes an item and is listed on the
    marketplace at `price` (heuristic if None). Unsold after 30 days, the
    expiry rule moves it to the donation pool."""
    if price is not None and price <= 0:
        raise FlowError(422, "Price must be more than $0.")
    _, item, _ = await _draft_to_item(draft_id, None, donated=False)
    try:
        return await list_item(item.id, price=price)
    except FlowError as e:   # listing failed: it stays available, i.e. in the donation pool
        raise FlowError(e.status_code, f"{e.detail} {item.id} is in the donation pool.") from e


def draft_item(draft_id: str) -> dict:
    """The parsed item of a live draft (404 FlowError otherwise)."""
    return _get_draft(draft_id)["item"]


async def local_demand(item: dict, vec: list[float] | None = None) -> list[dict]:
    """Read-only matchmaker check: open requests this item could fill, best first."""
    if vec is None:
        vec = await llm.embed(_embed_text(item))
    threshold = _threshold()
    waiting = []
    for req, score in db.open_requests_near(vec, top_k=5):
        final = score
        if config.USE_STUBS:     # same stub re-ranking as handle_request
            final += stub_rules.stub_fit(req, item)
        if final >= threshold:
            waiting.append({"request_id": req["id"], "zip": req["zip"], "score": round(score, 3),
                            "needs": req.get("needs") or []})
    return waiting


async def matchmake(item: dict, vec: list[float]) -> list[dict]:
    """Matchmaker agent: open requests this new item could fill, best first.
    Each one gets the item as a suggested match it can claim with /accept."""
    waiting = await local_demand(item, vec)
    for w in waiting:
        db.insert_matches([{"request_id": w["request_id"], "item_id": item["id"],
                            "score": w["score"], "rank": 0, "status": "suggested",
                            "reason": "New donation that fits your request"}])
        if db.get_request(w["request_id"])["status"] == "open":
            db.update_request_status(w["request_id"], "matched")
        emit("matchmaker", f"{item['id']} may fit {w['request_id']} "
             f"({', '.join(w['needs']) or 'open request'}, zip {w['zip']})",
             item_id=item["id"], request_id=w["request_id"])
    if not waiting:
        emit("matchmaker", f"No open requests fit {item['id']} yet; it stays searchable",
             item_id=item["id"])
    return waiting


async def donate(note: str | None, zip_code: str, donor_id: str,
                 image_bytes: bytes | None, image_mime: str,
                 image_url: str | None, item_id: str) -> Item:
    """Legacy one-step POST /api/items: parse + donate."""
    parsed = await _parse(note, [(image_bytes, image_mime)] if image_bytes else [], item_id)
    return await store(parsed, note, zip_code, donor_id, image_url, item_id)


async def store(parsed: ParsedItem, note: str | None, zip_code: str,
                donor_id: str, image_url: str | None, item_id: str,
                vec: list[float] | None = None, donated: bool = True) -> Item:
    """Insert as available. `donated=False` (about to be listed for sale)
    skips the item_donated impact count."""
    if vec is None:
        vec = await llm.embed(_embed_text(parsed.model_dump()))
    row = {**parsed.model_dump(), "id": item_id, "donor_id": donor_id, "note": note,
           "zip": zip_code, "image_url": image_url, "status": "available",
           "embedding": vec, "created_at": db.now()}
    db.insert_item(row)
    if donated:
        emit("orchestrator", f"Saved {item_id} as available", item_id=item_id,
             event_type="item_donated", category=parsed.category)
    else:
        emit("orchestrator", f"Saved {item_id} to list for sale", item_id=item_id)
    return _public(row)


# ---- requester path: R1 -> R6 ----------------------------------------------
async def handle_request(text: str, zip_code: str, requester_id: str) -> RequestOut:
    req_id = db.new_request_id()
    emit("orchestrator", f"New request from {zip_code}", request_id=req_id,
         event_type="request_made")

    try:
        query = await requester.parse_request(text, zip_code)
    except Exception as e:   # model down or unusable reply: keyword rules keep the demo going
        emit("requester", f"Model reply unusable ({type(e).__name__}); using keyword rules",
             request_id=req_id)
        query = requester._stub(text, zip_code)
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
    threshold = _threshold()
    for row, score in candidates:
        if score < threshold:
            continue
        hits = sum(stub_rules.satisfies(row["attributes"], a) for a in query.must_have)
        final = score + 0.05 * hits
        if config.USE_STUBS:
            final += stub_rules.stub_fit(query.model_dump(), row)
            if final < threshold:
                continue
        ranked.append((row, score, final))
    ranked.sort(key=lambda x: x[2], reverse=True)
    ranked = ranked[:config.TOP_K]

    reasons = await _reasons(query, [r for r, _, _ in ranked])
    # The reasons call can take seconds with a real model; drop anything that
    # got listed or reserved meanwhile so we never suggest an unavailable item.
    ranked = [(row, score, final) for row, score, final in ranked
              if _still_available(row["id"])]
    matches = [Match(item_id=row["id"], title=_title(row), rank=i + 1, score=round(score, 3),
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
    if matches:   # suggestions only: nothing is reserved until accept
        emit("orchestrator", f"Top match {matches[0].item_id} ({matches[0].score})",
             request_id=req_id, item_id=matches[0].item_id,
             event_type="match_made", category=matches[0].item.category)
    else:
        emit("orchestrator", "No good match yet; request left open", request_id=req_id)

    return RequestOut(request_id=req_id, status=status, query=query, matches=matches)


async def accept_match(request_id: str, item_id: str) -> AcceptOut:
    """A1-A2: claim one suggested match. Re-checks the item is still available."""
    req = db.get_request(request_id)
    if req is None:
        raise FlowError(404, f"Request {request_id} not found.")
    match = db.get_match(request_id, item_id)
    if match is None:
        raise FlowError(404, f"{item_id} isn't one of the matches for {request_id}.")
    if req["status"] == "closed":
        raise FlowError(409, f"Request {request_id} already has an accepted match.")
    if item_id in _listing_now or not db.reserve_item(item_id):
        raise FlowError(409, f"Item {item_id} is no longer available.")
    db.update_match_status(match["id"], "accepted")
    db.update_request_status(request_id, "closed")
    row = db.get_item(item_id)
    emit("orchestrator", f"{item_id} reserved; donor notified, pickup in {row['zip']}",
         request_id=request_id, item_id=item_id, event_type="match_accepted",
         category=row["category"])
    return AcceptOut(match_id=match["id"], item_id=item_id, donor_notified=True,
                     handoff=Handoff(zip=row["zip"], message="Reserved. The donor has been "
                                     f"notified; pickup in {row['zip']}."))


def _title(row: dict) -> str:
    return f"{row['brand']} {row['item']}" if row.get("brand") else row["item"]


def _threshold() -> float:
    """Hashed stub embeddings score much lower than real ones, so they get their
    own cutoff; that holds even when the Modal text model is configured."""
    return 0.2 if llm.stub_embeddings() else config.MATCH_THRESHOLD


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
async def list_item(item_id: str, platform: str = "nostr",
                    price: float | None = None) -> ListItemOut:
    row = db.get_item(item_id)
    if row is None:
        raise FlowError(404, f"Item {item_id} not found.")
    if row["status"] != "available" or item_id in _listing_now:
        status = "being listed" if item_id in _listing_now else row["status"]
        raise FlowError(409, f"Item {item_id} is {status}; only available items can be listed.")
    channel = marketplace.get_channel(platform)
    _listing_now.add(item_id)
    try:
        if price is None:
            price = marketplace.suggest_price(row)
            how = f"{row['category']}, {row['condition']}"
        else:
            price, how = round(float(price), 2), "from the price quote"
        emit("orchestrator", f"Priced {item_id} at ${price:g} ({how})", item_id=item_id)
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
