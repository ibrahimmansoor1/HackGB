"""Database access. ONLY the orchestrator and events logger import this.

In-memory stub for now so everyone can build in parallel. The DB owner
replaces these functions with the sponsor database; keep the signatures.
"""
from datetime import datetime, timezone
import itertools
import numpy as np

_items: dict[str, dict] = {}
_requests: dict[str, dict] = {}
_matches: list[dict] = []
_events: list[dict] = []
_listings: dict[str, dict] = {}
_item_ids = itertools.count(1)
_req_ids = itertools.count(1)
_event_ids = itertools.count(1)
_listing_ids = itertools.count(1)


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_item_id() -> str:
    return f"itm_{next(_item_ids):04d}"


def new_request_id() -> str:
    return f"req_{next(_req_ids):04d}"


# ---- items -----------------------------------------------------------------
def insert_item(row: dict) -> dict:
    _items[row["id"]] = row
    return row


def get_item(item_id: str) -> dict | None:
    return _items.get(item_id)


def list_items(status: str | None = None) -> list[dict]:
    return [r for r in _items.values() if status is None or r["status"] == status]


def update_item_status(item_id: str, status: str) -> None:
    _items[item_id]["status"] = status


def vector_search(query_vec: list[float], top_k: int,
                  status: str = "available") -> list[tuple[dict, float]]:
    """Cosine similarity over items with the given status.
    Replace with the sponsor DB's native vector search."""
    q = np.asarray(query_vec)
    scored = []
    for row in list_items(status):
        v = np.asarray(row["embedding"])
        score = float(q @ v / (np.linalg.norm(q) * np.linalg.norm(v) + 1e-9))
        scored.append((row, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


# ---- requests & matches ----------------------------------------------------
def insert_request(row: dict) -> dict:
    _requests[row["id"]] = row
    return row


def insert_matches(rows: list[dict]) -> None:
    _matches.extend(rows)


# ---- listings (marketplace) ------------------------------------------------
def new_listing_id() -> str:
    return f"lst_{next(_listing_ids):04d}"


def insert_listing(row: dict) -> dict:
    _listings[row["id"]] = row
    return row


def list_listings(status: str | None = None) -> list[dict]:
    return [r for r in _listings.values() if status is None or r["status"] == status]


def update_listing(listing_id: str, **fields) -> None:
    _listings[listing_id].update(fields)


# ---- events ----------------------------------------------------------------
def insert_event(row: dict) -> dict:
    row["id"] = next(_event_ids)
    _events.append(row)
    return row


def list_events(after: int = 0, limit: int = 50) -> list[dict]:
    return [e for e in _events if e["id"] > after][:limit]
