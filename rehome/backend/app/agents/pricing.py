"""Pricing agent: ParsedItem + eBay comps -> PriceQuote (S4 -> S5), on Modal.
Pure function: never touches the DB or eBay (the orchestrator fetches comps).
Prompt spec in docs/05-agents.md."""
import json
import statistics
from pydantic import ValidationError
from app.agents import stub_rules
from app.core import config, llm
from app.schemas import PriceQuote

SYSTEM_PROMPT = """You price secondhand items. You get an item and a list of active eBay
listings. Discard listings that are not the same kind of item. From the rest,
suggest a realistic resale range for this item's condition (asking prices run
higher than sale prices; aim below the median). Write a listing title
(<= 80 chars, brand + item + size + condition) and a 2-4 sentence description.
Return ONLY JSON with keys: suggested_price {low, high, currency}, comps,
listing_draft {title, description}. comps: the input listings you kept, unchanged.
No prose, no markdown fences."""


async def quote(item: dict, comps: list[dict]) -> PriceQuote:
    if config.USE_STUBS:
        return _stub(item, comps)
    user = f"Item: {json.dumps(item)}\nActive eBay listings: {json.dumps(comps)}"
    for attempt in range(2):  # one retry on bad JSON / schema mismatch
        try:
            return PriceQuote.model_validate(await llm.complete_json(SYSTEM_PROMPT, user))
        except (ValidationError, ValueError):
            if attempt == 1:
                raise


def listing_draft(item: dict) -> dict:
    """Template title + description (stub pricing and the estimate fallback)."""
    name = " ".join(w for w in (item.get("brand"), item.get("color"), item["item"]) if w)
    title = name.title()
    if item.get("size"):
        title += f", Size {item['size']}"
    title += f", {item['condition'].title()}"
    feats = ", ".join(item.get("attributes") or [])
    desc = f"{item['summary']} Condition: {item['condition']}."
    if feats:
        desc += f" Features: {feats}."
    return {"title": title[:80], "description": desc + " Priced to sell secondhand."}


def _comparable(item: dict, comps: list[dict]) -> list[dict]:
    """Stub check: the listing title names the same kind of thing (same
    category by keyword, or the item's head noun appears in it)."""
    head = (stub_rules.find_noun(item["item"])[0] or item["item"].split()[-1]).lower()
    return [c for c in comps if stub_rules.find_noun(c["title"])[1] == item["category"]
            or head in c["title"].lower()]


def _stub(item: dict, comps: list[dict]) -> PriceQuote:
    """Below the median asking price of comparable listings: 60-90 %."""
    kept = _comparable(item, comps)
    if kept:
        median = statistics.median(c["price"] for c in kept)
        low, high = max(1, round(median * 0.6)), max(1, round(median * 0.9))
    else:
        low = high = 1   # no comps kept; the orchestrator falls back to the estimate
    return PriceQuote.model_validate({"suggested_price": {"low": low, "high": high},
                                      "comps": kept, "listing_draft": listing_draft(item)})
