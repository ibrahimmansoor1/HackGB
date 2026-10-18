"""Marketplace channel: Nostr classified listings (NIP-99, kind 30402).

Listings signed here show up publicly on Shopstr (https://shopstr.store) and
any other NIP-99 client. Called ONLY by the orchestrator; never touches the DB.

Adding another platform (eBay, Etsy, Shopify) later = one more class with the
same `Channel` shape, registered in CHANNELS. The orchestrator doesn't change.

Safety: nothing is sent to relays unless NOSTR_NSEC is set AND
MARKETPLACE_DRY_RUN=false. Dry runs sign with a throwaway key and stay local.
"""
import asyncio
import ipaddress
from datetime import timedelta
from typing import Protocol
from urllib.parse import urlparse

from nostr_sdk import (Client, Coordinate, EventBuilder, Keys, Kind, Nip19Coordinate,
                       RelayUrl, Tag, Timestamp)

from app.core import config

KIND_LISTING = 30402
CURRENCY = "USD"
SHOPSTR_LISTING_URL = "https://shopstr.store/listing/{naddr}"   # seller: /marketplace/<npub>
NJUMP_URL = "https://njump.me/{naddr}"   # plain Nostr viewer; works when Shopstr is down
CONNECT_WAIT_S = 4     # wait for relay sockets before sending
OK_WAIT_S = 4          # wait for each relay's OK after sending
TIMEOUT_S = 10         # hard backstop on connect + send, so the API never hangs
NADDR_RELAY_HINTS = 3

SUSTAINABILITY_NOTE = ("Buying secondhand keeps this out of a landfill. If it doesn't sell in "
                       "30 days, Rehome gives it free to a neighbor who needs it.")


class MarketplaceError(Exception):
    """Channel misconfigured or unreachable (e.g. invalid NOSTR_NSEC)."""


# ---- pricing ---------------------------------------------------------------
# Isolated on purpose: a comps-based pricer can replace suggest_price later.
BASE_PRICE = {"outerwear": 30, "tops": 12, "bottoms": 15, "footwear": 25,
              "accessories": 10, "home": 20, "electronics": 35, "kids": 12, "other": 10}
CONDITION_MULTIPLIER = {"new": 1.0, "like new": 0.85, "good": 0.65, "fair": 0.45}


def suggest_price(item: dict) -> int:
    """Whole-dollar price from category default × condition multiplier, min $1."""
    base = BASE_PRICE.get(item.get("category"), BASE_PRICE["other"])
    mult = CONDITION_MULTIPLIER.get(item.get("condition"), CONDITION_MULTIPLIER["good"])
    return max(1, int(base * mult))


# ---- event building (pure) -------------------------------------------------
def _title(item: dict) -> str:
    name = " ".join(p for p in (item.get("color"), item.get("item")) if p).strip() or "Item"
    title = name[0].upper() + name[1:]
    if item.get("size"):
        title += f", size {item['size']}"
    return title[:80]


def _content(item: dict) -> str:
    lines = []
    if item.get("summary"):
        lines += [item["summary"], ""]
    details = [("Condition", item.get("condition")), ("Size", item.get("size")),
               ("Color", item.get("color")), ("Season", item.get("season")),
               ("Features", ", ".join(item.get("attributes") or []))]
    lines += [f"- **{label}:** {value}" for label, value in details if value]
    lines += ["", f"_{SUSTAINABILITY_NOTE}_"]
    return "\n".join(lines).strip()


def _is_public_image(url: str | None) -> bool:
    """Only URLs other people can open: http(s) and not localhost / a private LAN
    address (those would be broken images on Shopstr)."""
    if not url:
        return False
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not host:
        return False
    if host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True   # a real hostname
    return ip.is_global


def has_public_image(item: dict) -> bool:
    """Shopstr hides listings without a photo it can load."""
    return _is_public_image(item.get("image_url"))


def build_listing_event(item: dict, price: int | float, status: str = "active",
                        published_at: int | None = None, keys: Keys | None = None,
                        created_at: int | None = None):
    """Signed NIP-99 event for one item. Pure: no network, no DB.

    Reads only catalog fields; donor_id, note, and other personal data never
    leave the server. `d` = item id, so republishing replaces the listing."""
    if status not in ("active", "sold"):
        raise ValueError(f"status must be active or sold, not {status!r}")
    keys = keys or _signing_keys()
    published = published_at or Timestamp.now().as_secs()
    amount = f"{price:g}" if isinstance(price, float) else str(price)

    tags = [["d", item["id"]],
            ["title", _title(item)],
            ["summary", item.get("summary") or _title(item)],
            ["price", amount, CURRENCY],
            ["published_at", str(published)],
            ["status", status]]
    location = config.LISTING_LOCATION or item.get("zip")
    if location:
        tags.append(["location", location])
    topics = []
    for t in [item.get("category"), *(item.get("attributes") or [])]:
        t = (t or "").strip().lower()
        if t and t not in topics:
            topics.append(t)
    tags += [["t", t] for t in topics]
    if _is_public_image(item.get("image_url")):
        tags.append(["image", item["image_url"]])

    builder = EventBuilder(Kind(KIND_LISTING), _content(item)).tags(
        [Tag.parse(t) for t in tags])
    if created_at:
        builder = builder.custom_created_at(Timestamp.from_secs(created_at))
    return builder.finalize(keys)


# ---- keys & mode -----------------------------------------------------------
_throwaway: Keys | None = None


def is_live() -> bool:
    return bool(config.NOSTR_NSEC) and not config.MARKETPLACE_DRY_RUN


def _signing_keys() -> Keys:
    """Real key only in live mode; a per-process throwaway key otherwise."""
    global _throwaway
    if is_live():
        try:
            return Keys.parse(config.NOSTR_NSEC)
        except Exception as e:
            raise MarketplaceError("NOSTR_NSEC is not a valid nsec/hex secret key") from e
    if _throwaway is None:
        _throwaway = Keys.generate()
    return _throwaway


def _naddr(ev, relays: list[str]) -> str:
    """`naddr` = kind + author + d tag (+ relay hints). Viewers resolve it to the
    newest version, so links keep working after the listing is republished."""
    hints = []
    for url in relays[:NADDR_RELAY_HINTS]:
        try:
            hints.append(RelayUrl.parse(url))
        except Exception:
            continue
    d_tag = next(t[1] for t in _tags(ev) if t[0] == "d")
    coord = Coordinate(ev.kind(), ev.author(), d_tag)
    return Nip19Coordinate(coord, hints).to_bech32()


def _tags(ev) -> list[list[str]]:
    return [t.to_vec() for t in ev.tags()]


# ---- relays ----------------------------------------------------------------
def _norm(url) -> str:
    return str(url).rstrip("/").lower()


def _new_client() -> Client:
    """Factory so tests can swap in a fake client (no network in tests)."""
    return Client()


async def _broadcast(ev, relays: list[str]) -> tuple[list[str], list[str]]:
    """Send a signed event. Returns (accepted, failed) relay URLs; never raises,
    never takes longer than ~TIMEOUT_S."""
    client = _new_client()
    accepted: list[str] = []
    failed: list[str] = []
    added: dict[str, str] = {}   # normalized relay URL -> URL as configured
    for url in relays:
        try:
            parsed = RelayUrl.parse(url)
            await client.add_relay(parsed)
            added[_norm(parsed)] = url
        except Exception:
            failed.append(url)

    async def _send():
        await client.connect(timedelta(seconds=CONNECT_WAIT_S))
        # Relays that don't answer within ok_timeout count as failed.
        return await client.send_event(ev, ok_timeout=timedelta(seconds=OK_WAIT_S))

    if added:
        try:
            out = await asyncio.wait_for(_send(), timeout=TIMEOUT_S)
            ok = {_norm(u) for u in out.success}
            accepted = [url for key, url in added.items() if key in ok]
        except Exception:   # timeout or SDK error: nothing confirmed
            accepted = []
        failed += [url for url in added.values() if url not in accepted]
    try:
        await asyncio.wait_for(client.disconnect(), timeout=2)
    except Exception:
        pass
    return accepted, failed


async def _publish(item: dict, price: int | float, status: str,
                   published_at: int | None = None, created_at: int | None = None) -> dict:
    ev = build_listing_event(item, price, status, published_at=published_at,
                             created_at=created_at)
    relays = list(config.NOSTR_RELAYS)
    live = is_live()
    if live:
        accepted, failed = await _broadcast(ev, relays)
    else:
        accepted, failed = [], []
    naddr = _naddr(ev, relays)
    return {"event_id": ev.id().to_hex(),
            "npub": ev.author().to_bech32(),
            "relays_accepted": accepted,
            "relays_failed": failed,
            "url": SHOPSTR_LISTING_URL.format(naddr=naddr),
            "nostr_url": NJUMP_URL.format(naddr=naddr),
            "published_at": int(next(t[1] for t in _tags(ev) if t[0] == "published_at")),
            "dry_run": not live}


async def publish_listing(item: dict, price: int | float) -> dict:
    """Post a new active listing. Returns {event_id, npub, relays_accepted,
    relays_failed, url, published_at, dry_run}."""
    return await _publish(item, price, "active")


async def mark_sold(item: dict, price: int | float, published_at: int | None = None) -> dict:
    """Republish the same `d` tag with status=sold so clients drop it from
    active listings. Pass the original published_at to keep NIP-99 semantics."""
    # Replaceable events: the newer created_at wins, so never tie the original.
    created = max(Timestamp.now().as_secs(), (published_at or 0) + 1)
    return await _publish(item, price, "sold", published_at=published_at, created_at=created)


# ---- channel interface -----------------------------------------------------
class Channel(Protocol):
    platform: str   # stored in listings.platform
    label: str      # shown in the activity feed

    async def publish(self, item: dict, price: int | float) -> dict: ...

    async def mark_sold(self, item: dict, price: int | float,
                        published_at: int | None = None) -> dict: ...


class NostrChannel:
    platform = "nostr"
    label = "Shopstr"

    async def publish(self, item, price):
        return await publish_listing(item, price)

    async def mark_sold(self, item, price, published_at=None):
        return await mark_sold(item, price, published_at)


# Roadmap: "ebay": EbayChannel(), "etsy": ..., "shopify": ...
CHANNELS: dict[str, Channel] = {"nostr": NostrChannel()}


def get_channel(platform: str = "nostr") -> Channel:
    return CHANNELS[platform]
