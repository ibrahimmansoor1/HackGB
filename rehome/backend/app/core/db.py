"""Database access. ONLY the orchestrator and events logger import this.

With DATABASE_URL set, every function below is replaced by its Tiger Data
version in core/db_pg.py (same signatures). Without it, this in-memory stub
runs, so the demo and tests work offline.
"""
from datetime import datetime, timezone
import itertools
import numpy as np
from app.core import config

_items: dict[str, dict] = {}
_requests: dict[str, dict] = {}
_matches: list[dict] = []
_events: list[dict] = []
_listings: dict[str, dict] = {}
_drafts: dict[str, dict] = {}
_item_ids = itertools.count(1)
_draft_ids = itertools.count(1)
_match_ids = itertools.count(1)
_req_ids = itertools.count(1)
_event_ids = itertools.count(1)
_listing_ids = itertools.count(1)


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_item_id() -> str:
    return f"itm_{next(_item_ids):04d}"


def new_request_id() -> str:
    return f"req_{next(_req_ids):04d}"


def new_draft_id() -> str:
    return f"drf_{next(_draft_ids):04d}"


# ---- drafts (parsed, not yet sold or donated) ------------------------------
def insert_draft(row: dict) -> dict:
    _drafts[row["id"]] = row
    return row


def get_draft(draft_id: str) -> dict | None:
    return _drafts.get(draft_id)


def pop_draft(draft_id: str) -> dict | None:
    """Remove and return the draft; None if it was already taken."""
    return _drafts.pop(draft_id, None)


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


def open_requests_near(query_vec: list[float], top_k: int = 5) -> list[tuple[dict, float]]:
    """Not-yet-closed requests by cosine similarity to an item's vector."""
    q = np.asarray(query_vec)
    scored = []
    for row in _requests.values():
        if row["status"] == "closed" or row.get("embedding") is None:
            continue
        v = np.asarray(row["embedding"])
        scored.append((row, float(q @ v / (np.linalg.norm(q) * np.linalg.norm(v) + 1e-9))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def get_request(request_id: str) -> dict | None:
    return _requests.get(request_id)


def update_request_status(request_id: str, status: str) -> None:
    _requests[request_id]["status"] = status


def insert_matches(rows: list[dict]) -> None:
    for r in rows:
        _matches.append({**r, "id": r.get("id") or f"mat_{next(_match_ids):04d}"})


def get_match(request_id: str, item_id: str) -> dict | None:
    return next((m for m in _matches
                 if m["request_id"] == request_id and m["item_id"] == item_id), None)


def update_match_status(match_id: str, status: str) -> None:
    for m in _matches:
        if m["id"] == match_id:
            m["status"] = status


def reserve_item(item_id: str) -> bool:
    """available -> reserved in one step; False if it wasn't available."""
    row = _items.get(item_id)
    if row is None or row["status"] != "available":
        return False
    row["status"] = "reserved"
    return True


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


def impact_rows() -> list[dict]:
    """Same rows as Tiger's impact_hourly: hourly counts per event_type + category."""
    counts: dict[tuple, int] = {}
    for e in _events:
        if e.get("event_type"):
            bucket = e["created_at"].replace(minute=0, second=0, microsecond=0)
            key = (bucket, e["event_type"], e.get("category"))
            counts[key] = counts.get(key, 0) + 1
    return [{"bucket": b, "event_type": t, "category": c, "n": n}
            for (b, t, c), n in counts.items()]


BACKEND = "tiger" if config.DATABASE_URL else "memory"
if config.DATABASE_URL:
    from app.core.db_pg import *  # noqa: E402,F401,F403  (overrides the stubs above)
