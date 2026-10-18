# 08 · Database (Tiger Data)

Owner: Shayan. Files: `backend/app/core/db.py`, `backend/app/core/db_tiger.py`, `backend/db/schema.sql`, `backend/scripts/init_db.py`.

## What we use

[Tiger Cloud](https://console.cloud.tigerdata.com) is managed PostgreSQL from Tiger Data (formerly Timescale). We use three of its extensions:

| Extension | What for |
|---|---|
| **pgvector** | `vector(EMBED_DIM)` columns on `items` and `requests`; cosine distance `<=>` |
| **pgvectorscale** | StreamingDiskANN index on `items.embedding` for the requester search (R4) |
| **TimescaleDB** | `agent_events` is a hypertable (time-partitioned event log for the activity feed) |

If `vectorscale` or `timescaledb` is missing (plain Postgres), the schema falls back to a pgvector HNSW index and a normal table, so the code runs on any Postgres that has pgvector.

## How it plugs in

`core/db.py` keeps the in-memory stub. At the bottom it checks `config.DB_BACKEND`:

- `DATABASE_URL` blank → `memory` (the stub, nothing persists)
- `DATABASE_URL` set → `tiger`: every function is replaced by the one in `core/db_tiger.py`

The function names, arguments and return shapes are identical, so the orchestrator, routers and `events.py` don't change. Rows are dicts with the keys from `docs/03`; `embedding` is a `list[float]`.

| Function | SQL |
|---|---|
| `new_item_id` / `new_request_id` / `new_listing_id` | `nextval()` on a sequence → `itm_0001`, `req_0001`, `lst_0001` |
| `insert_item`, `get_item`, `list_items`, `update_item_status` | `items` table |
| `vector_search(vec, top_k, status)` | `ORDER BY embedding <=> vec LIMIT k`, filtered by `status`; score = `1 - distance` (same cosine number the stub computed) |
| `insert_request`, `insert_matches` | `requests`, `matches` |
| `insert_event`, `list_events(after, limit)` | `agent_events` hypertable, `id > after ORDER BY id` |
| `insert_listing`, `list_listings`, `update_listing` | `listings` (marketplace stretch) |
| `reset()`, `info()` | admin helpers: wipe rows / report extensions, index type, row counts |

The first DB call creates any missing tables (`DB_AUTO_INIT=true`, idempotent), then opens a small connection pool (`DB_POOL_MAX`, default 5).

## Setup (once per person)

1. Sign up at [mlh.link/tigerdata-quickstart](https://mlh.link/tigerdata-quickstart) and create a **service** (PostgreSQL 17+, so pgvectorscale is preinstalled). Pick the region closest to the demo (US East).
2. In the console, open the service → **Connect**, copy the connection string (it ends in `?sslmode=require`).
3. In `rehome/.env` (never commit it):
   ```
   DATABASE_URL=postgres://tsdbadmin:<password>@<host>:<port>/tsdb?sslmode=require
   EMBED_DIM=384
   ```
4. Install and create the tables:
   ```bash
   cd backend
   pip install -r requirements.txt
   python scripts/init_db.py          # creates extensions, tables, indexes
   python scripts/init_db.py --check  # should show vector_index: diskann, agent_events_hypertable: true
   ```
5. Run the backend as usual. `curl -X POST localhost:8000/api/admin/seed` now writes to Tiger Cloud.

To share one database with the team, give teammates the same `DATABASE_URL` privately (not in git or chat channels that are public).

## Day-to-day

| Need | Command |
|---|---|
| Fresh demo (empty inventory, ids from 0001) | `python scripts/init_db.py --clear` |
| Changed `EMBED_DIM` or the embedding model | `python scripts/init_db.py --reset` (drops and recreates; old vectors are useless anyway) |
| See what's in there | `python scripts/init_db.py --check`, or the SQL editor in Tiger Console |
| Run without the DB | leave `DATABASE_URL` blank, or `DB_BACKEND=memory` |
| Test the Tiger layer | `TEST_DATABASE_URL=... pytest tests/test_db_tiger.py` (wipes that DB; use a separate service) |

## Things to know

- **Data persists now.** Items stay `reserved` after a restart. Use `--clear` before the demo.
- **Embedding size is fixed by the column.** If `MODAL_EMBED_MODEL` returns, say, 768 numbers, set `EMBED_DIM=768` and run `--reset`. Stub vectors and real-model vectors don't mix: reset when you switch from stub mode to the real model.
- **Photos are not in the DB.** `image_url` points at `static/uploads/` (or a bucket later).
- **Free credits:** $1,000 for 30 days through the MLH link, enough for the event.

## Possible next step: hybrid search

Tiger Cloud also ships `pg_textsearch` (BM25 keyword ranking). Combining BM25 with the vector search (Reciprocal Rank Fusion) would help when a requester types an exact word like a brand or size. Not wired in yet, because the orchestrator thresholds on a 0–1 cosine score and RRF scores aren't on that scale.
