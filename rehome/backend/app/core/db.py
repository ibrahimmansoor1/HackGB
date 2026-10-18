"""Database access. ONLY the orchestrator and events logger import this.

Two backends with the same functions:
- DATABASE_URL blank (or DB_BACKEND=memory): the in-memory stub below.
- DATABASE_URL set: Tiger Data (Postgres + pgvector/pgvectorscale), see
  db_tiger.py. The functions below are swapped out at the end of this file.
"""
from datetime import datetime, timezone
import itertools
import numpy as np

_items: dict[str, dict] = {}
_requests: dict[str, dict] = {}
_matches: list[dict] = []
_events: list[dict] = []
_item_ids = itertools.count(1)
_req_ids = itertools.count(1)
_event_ids = itertools.count(1)


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


# ---- events ----------------------------------------------------------------
def insert_event(row: dict) -> dict:
    row["id"] = next(_event_ids)
    _events.append(row)
    return row


def list_events(after: int = 0, limit: int = 50) -> list[dict]:
    return [e for e in _events if e["id"] > after][:limit]


# ---- admin (stub) ------------------------------------------------------------
BACKEND = "memory"


def reset() -> None:
    """Delete every row and restart the id counters."""
    global _item_ids, _req_ids, _event_ids
    _items.clear(); _requests.clear(); _matches.clear(); _events.clear()
    _item_ids, _req_ids, _event_ids = (itertools.count(1) for _ in range(3))


def info() -> dict:
    return {"backend": BACKEND, "rows": {"items": len(_items), "requests": len(_requests),
                                         "matches": len(_matches), "agent_events": len(_events)}}


# ---- Tiger Data ----------------------------------------------------------------
# With DATABASE_URL set, every function above is replaced by the Tiger Data
# version (same names and signatures). Callers keep using db.<function>.
from app.core import config as _config  # noqa: E402

if _config.DB_BACKEND == "tiger":
    from app.core.db_tiger import *  # noqa: E402,F401,F403
