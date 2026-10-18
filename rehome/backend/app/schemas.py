"""Pydantic models. Mirror of docs/03-data-model.md and docs/05-agents.md.
If these disagree with the docs, the docs win."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

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
    need: str
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


class RequestIn(BaseModel):
    text: str
    zip: str
    requester_id: str = "demo_requester"


class Match(BaseModel):
    item_id: str
    rank: int
    score: float
    reason: str
    item: Item


class RequestOut(BaseModel):
    request_id: str
    status: Literal["open", "matched", "closed"]
    query: StructuredQuery
    matches: list[Match]


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


class AgentEvent(BaseModel):
    id: int
    agent: Literal["orchestrator", "parser", "pricing", "requester"]
    event_type: Optional[Literal["item_parsed", "item_donated", "price_quoted",
                                 "request_made", "match_made", "match_accepted"]] = None
    category: Optional[str] = None
    message: str
    item_id: Optional[str] = None
    request_id: Optional[str] = None
    created_at: datetime
