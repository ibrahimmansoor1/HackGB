"""Pydantic models. Mirror of docs/03-data-model.md and docs/05-agents.md.
If these disagree with the docs, the docs win."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

Category = Literal["outerwear", "tops", "bottoms", "footwear", "accessories",
                   "home", "electronics", "kids", "other"]
Condition = Literal["new", "like new", "good", "fair"]
ItemStatus = Literal["available", "listed", "reserved", "donated"]


# ---- Agent outputs ---------------------------------------------------------
class ParsedItem(BaseModel):
    """Parser agent output (D3)."""
    category: Category
    item: str
    brand: Optional[str] = None     # from a visible tag or the donor's text; never guessed
    color: str
    size: Optional[str] = None
    condition: Condition
    season: Optional[Literal["winter", "summer", "all"]] = None
    attributes: list[str] = Field(default_factory=list)
    summary: str


class StructuredQuery(BaseModel):
    """Requester agent output (R3)."""
    needs: list[str] = Field(min_length=1)
    inferred_context: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    size: Optional[str] = None
    search_text: str


# ---- API models ------------------------------------------------------------
class Item(ParsedItem):
    id: str
    donor_id: str
    note: Optional[str] = None
    zip: str
    image_url: Optional[str] = None
    status: ItemStatus = "available"
    created_at: datetime


class DraftOut(BaseModel):
    """POST /api/items/parse: parsed, not stored as an item until the donor chooses."""
    draft_id: str
    item: ParsedItem
    image_url: Optional[str] = None
    options: list[Literal["sell", "donate"]] = ["sell", "donate"]


class DonateIn(BaseModel):
    pickup_zip: Optional[str] = None   # defaults to the draft's zip


class DonateOut(BaseModel):
    item_id: str
    status: ItemStatus
    message: str
    waiting_requests: list[str] = Field(default_factory=list)   # matchmaker found these


class PostIn(BaseModel):
    price: Optional[float] = None   # USD; default = category x condition heuristic


class Price(BaseModel):
    low: float = Field(gt=0)
    high: float = Field(gt=0)
    currency: Literal["USD"] = "USD"

    @model_validator(mode="after")
    def _ordered(self):
        if self.low > self.high:
            raise ValueError("low must not exceed high")
        return self


class Comp(BaseModel):
    title: str
    price: float
    condition: Optional[str] = None
    source: Literal["ebay"] = "ebay"
    url: str


class ListingDraft(BaseModel):
    title: str
    description: str

    @field_validator("title")
    @classmethod
    def _max_80(cls, v: str) -> str:
        return v.strip()[:80]


class PriceQuote(BaseModel):
    """Pricing agent output (S5)."""
    suggested_price: Price
    comps: list[Comp] = Field(default_factory=list)
    listing_draft: ListingDraft


class SellOut(PriceQuote):
    draft_id: str
    basis: Literal["active listings", "estimate"]


class RequestIn(BaseModel):
    text: str
    zip: str
    requester_id: str = "demo_requester"


class Match(BaseModel):
    item_id: str
    title: str                  # item's `item`, brand prefixed when known
    rank: int
    score: float
    reason: str
    item: Item


class RequestOut(BaseModel):
    request_id: str
    status: Literal["open", "matched", "closed"]
    query: StructuredQuery
    matches: list[Match]


class AcceptIn(BaseModel):
    request_id: str
    item_id: str


class Handoff(BaseModel):
    method: Literal["pickup"] = "pickup"   # exchange method undecided (docs/02)
    zip: str
    message: str


class AcceptOut(BaseModel):
    match_id: str
    item_id: str
    status: Literal["reserved"] = "reserved"
    donor_notified: bool
    handoff: Handoff


class Listing(BaseModel):
    """Marketplace listing (docs/03 listings). platform `nostr` shows on Shopstr."""
    id: str
    item_id: str
    platform: Literal["nostr"]
    external_id: str          # Nostr event id (hex)
    price: float
    listed_at: datetime
    expires_at: datetime
    url: str
    status: Literal["active", "expired"]
    dry_run: bool
    relays_accepted: list[str] = Field(default_factory=list)


class ListItemOut(BaseModel):
    item: Item
    listing: Listing


class ExpiryOut(BaseModel):
    expired: list[str]


class CategoryImpact(BaseModel):
    category: str
    items_donated: int = 0
    matches_accepted: int = 0


class HourlyImpact(BaseModel):
    bucket: datetime
    event_type: str
    n: int


class ImpactOut(BaseModel):
    """GET /api/impact. totals keys = event_type values, pluralized."""
    totals: dict[str, int]
    by_category: list[CategoryImpact]
    hourly: list[HourlyImpact]     # last 24 h


class AgentEvent(BaseModel):
    id: int
    agent: Literal["orchestrator", "concierge", "parser", "pricing", "requester", "matchmaker"]
    event_type: Optional[Literal["item_parsed", "item_donated", "price_quoted",
                                 "request_made", "match_made", "match_accepted"]] = None
    category: Optional[str] = None
    message: str
    item_id: Optional[str] = None
    request_id: Optional[str] = None
    created_at: datetime
