"""Tiger Data backend for app.core.db (PostgreSQL + pgvector/pgvectorscale).

Loaded by db.py when DATABASE_URL is set. Every public function here has the
same name, arguments and return shape as the in-memory stub in db.py, so the
orchestrator, routers and events logger don't change.

Rows come back as plain dicts (same keys as docs/03-data-model.md);
`embedding` comes back as a list[float].
"""
from __future__ import annotations

import atexit
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core import config

BACKEND = "tiger"
SCHEMA_FILE = Path(__file__).resolve().parents[2] / "db" / "schema.sql"

ITEM_COLS = ("id", "donor_id", "image_url", "note", "zip", "category", "item", "color",
             "size", "condition", "season", "attributes", "summary", "embedding",
             "status", "created_at")
REQUEST_COLS = ("id", "requester_id", "raw_text", "zip", "need", "inferred_context",
                "must_have", "nice_to_have", "size", "search_text", "embedding",
                "status", "created_at")
MATCH_COLS = ("request_id", "item_id", "score", "rank", "reason", "status")
EVENT_COLS = ("agent", "item_id", "request_id", "message", "created_at")
LISTING_COLS = ("id", "item_id", "platform", "external_id", "price", "listed_at",
                "expires_at", "url", "status", "dry_run", "relays_accepted")
TABLES = ("listings", "matches", "requests", "agent_events", "items")
SEQUENCES = ("item_id_seq", "request_id_seq", "listing_id_seq")

_pool: ConnectionPool | None = None
_lock = threading.Lock()


# ---- connection & schema -------------------------------------------------------
def schema_sql() -> str:
    return SCHEMA_FILE.read_text().replace("__EMBED_DIM__", str(config.EMBED_DIM))


def init_schema() -> None:
    """Create extensions, tables and indexes if missing, then check that the
    vector columns match EMBED_DIM."""
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as conn:
        conn.execute(schema_sql())
        dim = conn.execute(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'items'::regclass AND attname = 'embedding'").fetchone()[0]
    if dim != config.EMBED_DIM:
        raise RuntimeError(
            f"items.embedding is vector({dim}) but EMBED_DIM={config.EMBED_DIM}. "
            "Run `python scripts/init_db.py --reset` to rebuild the tables "
            "(this deletes all rows).")


def _pool_or_open() -> ConnectionPool:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                if config.DB_AUTO_INIT:
                    init_schema()
                _pool = ConnectionPool(
                    config.DATABASE_URL, min_size=1, max_size=config.DB_POOL_MAX,
                    kwargs={"autocommit": True, "row_factory": dict_row},
                    configure=register_vector, open=True, timeout=15)
    return _pool


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


atexit.register(close)


def _all(sql: str, params: dict | tuple = ()) -> list[dict]:
    with _pool_or_open().connection() as conn:
        return conn.execute(sql, params).fetchall()


def _one(sql: str, params: dict | tuple = ()) -> dict | None:
    with _pool_or_open().connection() as conn:
        return conn.execute(sql, params).fetchone()


def _vec(v) -> np.ndarray | None:
    return None if v is None else np.asarray(v, dtype=np.float32)


def _clean(row: dict | None) -> dict | None:
    """DB row -> plain dict like the stub stores (embedding as a list)."""
    if row is None:
        return None
    if isinstance(row.get("embedding"), np.ndarray):
        row["embedding"] = row["embedding"].tolist()
    return row


def _insert_sql(table: str, cols: tuple[str, ...], returning: str = "") -> str:
    names = ", ".join(cols)
    values = ", ".join(f"%({c})s" for c in cols)
    return f"INSERT INTO {table} ({names}) VALUES ({values}){returning}"


def _params(row: dict, cols: tuple[str, ...]) -> dict:
    p = {c: row.get(c) for c in cols}
    if "embedding" in p:
        p["embedding"] = _vec(p["embedding"])
    for c in ("attributes", "inferred_context", "must_have", "nice_to_have",
              "relays_accepted"):
        if c in p and p[c] is None:
            p[c] = []
    if "created_at" in p and p["created_at"] is None:
        p["created_at"] = now()
    return p


# ---- ids & time -------------------------------------------------------------
def now() -> datetime:
    return datetime.now(timezone.utc)


def _next(seq: str) -> int:
    return _one(f"SELECT nextval('{seq}') AS n")["n"]


def new_item_id() -> str:
    return f"itm_{_next('item_id_seq'):04d}"


def new_request_id() -> str:
    return f"req_{_next('request_id_seq'):04d}"


def new_listing_id() -> str:
    return f"lst_{_next('listing_id_seq'):04d}"


# ---- items -----------------------------------------------------------------
_ITEM_SELECT = f"SELECT {', '.join(ITEM_COLS)} FROM items"


def insert_item(row: dict) -> dict:
    _one(_insert_sql("items", ITEM_COLS, " RETURNING id"), _params(row, ITEM_COLS))
    return row


def get_item(item_id: str) -> dict | None:
    return _clean(_one(f"{_ITEM_SELECT} WHERE id = %s", (item_id,)))


def list_items(status: str | None = None) -> list[dict]:
    if status is None:
        rows = _all(f"{_ITEM_SELECT} ORDER BY created_at, id")
    else:
        rows = _all(f"{_ITEM_SELECT} WHERE status = %s ORDER BY created_at, id", (status,))
    return [_clean(r) for r in rows]


def update_item_status(item_id: str, status: str) -> None:
    _one("UPDATE items SET status = %s WHERE id = %s RETURNING id", (status, item_id))


def vector_search(query_vec: list[float], top_k: int,
                  status: str = "available") -> list[tuple[dict, float]]:
    """Top-k items by cosine similarity (1 - cosine distance), best first.
    Uses the DiskANN (pgvectorscale) or HNSW index on items.embedding."""
    rows = _all(
        f"SELECT {', '.join(ITEM_COLS)}, 1 - (embedding <=> %(q)s) AS score "
        "FROM items WHERE status = %(s)s AND embedding IS NOT NULL "
        "ORDER BY embedding <=> %(q)s LIMIT %(k)s",
        {"q": _vec(query_vec), "s": status, "k": top_k})
    out = []
    for r in rows:
        score = r.pop("score")
        out.append((_clean(r), float(score) if score == score else 0.0))  # NaN -> 0
    return out


# ---- requests & matches ----------------------------------------------------
def insert_request(row: dict) -> dict:
    _one(_insert_sql("requests", REQUEST_COLS, " RETURNING id"), _params(row, REQUEST_COLS))
    return row


def insert_matches(rows: list[dict]) -> None:
    if not rows:
        return
    with _pool_or_open().connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(_insert_sql("matches", MATCH_COLS),
                            [_params({"status": "suggested", **r}, MATCH_COLS) for r in rows])


# ---- listings (marketplace) ------------------------------------------------
_LISTING_SELECT = f"SELECT {', '.join(LISTING_COLS)} FROM listings"


def insert_listing(row: dict) -> dict:
    _one(_insert_sql("listings", LISTING_COLS, " RETURNING id"), _params(row, LISTING_COLS))
    return row


def list_listings(status: str | None = None) -> list[dict]:
    if status is None:
        return _all(f"{_LISTING_SELECT} ORDER BY listed_at, id")
    return _all(f"{_LISTING_SELECT} WHERE status = %s ORDER BY listed_at, id", (status,))


def update_listing(listing_id: str, **fields) -> None:
    bad = set(fields) - set(LISTING_COLS) - {"id"}
    if bad:
        raise ValueError(f"Unknown listing fields: {sorted(bad)}")
    fields.pop("id", None)
    if not fields:
        return
    sets = ", ".join(f"{c} = %({c})s" for c in fields)
    _one(f"UPDATE listings SET {sets} WHERE id = %(_id)s RETURNING id",
         {**fields, "_id": listing_id})


# ---- events ----------------------------------------------------------------
def insert_event(row: dict) -> dict:
    out = _one(_insert_sql("agent_events", EVENT_COLS, " RETURNING id"),
               _params(row, EVENT_COLS))
    row["id"] = out["id"]
    return row


def list_events(after: int = 0, limit: int = 50) -> list[dict]:
    return _all(
        f"SELECT id, {', '.join(EVENT_COLS)} FROM agent_events "
        "WHERE id > %s ORDER BY id LIMIT %s", (after, limit))


# ---- admin -----------------------------------------------------------------
def reset() -> None:
    """Delete every row and restart the id counters (itm_0001 again).
    Keeps tables and indexes. For demo resets only."""
    with _pool_or_open().connection() as conn:
        conn.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
        for s in SEQUENCES:
            conn.execute(f"ALTER SEQUENCE {s} RESTART WITH 1")


def drop_all() -> None:
    """Drop every Rehome table and sequence (used by init_db.py --reset)."""
    close()
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as conn:
        conn.execute(f"DROP TABLE IF EXISTS {', '.join(TABLES)} CASCADE")
        conn.execute(f"DROP SEQUENCE IF EXISTS {', '.join(SEQUENCES)}")


def info() -> dict:
    """What the database has: version, extensions, row counts, index types."""
    exts = {r["extname"]: r["extversion"] for r in _all(
        "SELECT extname, extversion FROM pg_extension "
        "WHERE extname IN ('vector', 'vectorscale', 'timescaledb')")}
    counts = {t: _one(f"SELECT count(*) AS n FROM {t}")["n"] for t in TABLES}
    index = _one("SELECT am.amname FROM pg_class c JOIN pg_am am ON am.oid = c.relam "
                 "WHERE c.relname = 'items_embedding_idx'")
    hyper = False
    if "timescaledb" in exts:
        hyper = bool(_one("SELECT count(*) AS n FROM timescaledb_information.hypertables "
                          "WHERE hypertable_name = 'agent_events'")["n"])
    return {"backend": BACKEND,
            "server": _one("SHOW server_version")["server_version"],
            "extensions": exts, "rows": counts,
            "vector_index": index["amname"] if index else None,
            "embed_dim": config.EMBED_DIM,
            "agent_events_hypertable": hyper}


__all__ = ["BACKEND", "now", "new_item_id", "new_request_id", "new_listing_id",
           "insert_item", "get_item", "list_items", "update_item_status", "vector_search",
           "insert_request", "insert_matches", "insert_listing", "list_listings",
           "update_listing", "insert_event", "list_events", "reset", "info",
           "init_schema", "close"]
