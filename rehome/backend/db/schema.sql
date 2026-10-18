-- Rehome schema for Tiger Data (Tiger Cloud = PostgreSQL + TimescaleDB +
-- pgvector + pgvectorscale). Mirrors docs/03-data-model.md.
--
-- Safe to run more than once: every statement is IF NOT EXISTS.
-- __EMBED_DIM__ is replaced with config.EMBED_DIM by app/core/db_tiger.py
-- (and by scripts/init_db.py). To paste this into the Tiger Console SQL
-- editor by hand, replace __EMBED_DIM__ with your embedding size (e.g. 384).

-- ---- extensions -------------------------------------------------------------
-- pgvector: the vector type and cosine distance (<=>).
CREATE EXTENSION IF NOT EXISTS vector;

-- pgvectorscale: StreamingDiskANN index (Tiger Data). Preinstalled on Tiger
-- Cloud services running PostgreSQL 17+. Falls back to pgvector HNSW below.
DO $$ BEGIN
  CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pgvectorscale not available; using pgvector HNSW instead';
END $$;

-- TimescaleDB: hypertable for the agent activity feed.
DO $$ BEGIN
  CREATE EXTENSION IF NOT EXISTS timescaledb;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'timescaledb not available; agent_events stays a plain table';
END $$;

-- ---- id sequences (itm_0001, req_0001, lst_0001) ------------------------------
CREATE SEQUENCE IF NOT EXISTS item_id_seq;
CREATE SEQUENCE IF NOT EXISTS request_id_seq;
CREATE SEQUENCE IF NOT EXISTS listing_id_seq;

-- ---- items ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,                       -- itm_xxxx
    donor_id    TEXT NOT NULL DEFAULT 'demo_donor',
    image_url   TEXT,
    note        TEXT,
    zip         TEXT NOT NULL,
    category    TEXT NOT NULL,
    item        TEXT NOT NULL,
    color       TEXT NOT NULL,
    size        TEXT,
    condition   TEXT NOT NULL,
    season      TEXT,
    attributes  TEXT[] NOT NULL DEFAULT '{}',
    summary     TEXT NOT NULL,
    embedding   VECTOR(__EMBED_DIM__),
    status      TEXT NOT NULL DEFAULT 'available'
                CHECK (status IN ('available', 'listed', 'reserved', 'donated')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS items_status_idx ON items (status);

-- Vector index for the requester path (R4). Cosine, to match the scores the
-- orchestrator thresholds on (score = 1 - cosine distance).
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vectorscale') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS items_embedding_idx
             ON items USING diskann (embedding vector_cosine_ops)';
  ELSE
    EXECUTE 'CREATE INDEX IF NOT EXISTS items_embedding_idx
             ON items USING hnsw (embedding vector_cosine_ops)';
  END IF;
END $$;

-- ---- requests ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS requests (
    id                TEXT PRIMARY KEY,                 -- req_xxxx
    requester_id      TEXT NOT NULL DEFAULT 'demo_requester',
    raw_text          TEXT NOT NULL,
    zip               TEXT NOT NULL,
    need              TEXT NOT NULL,
    inferred_context  TEXT[] NOT NULL DEFAULT '{}',
    must_have         TEXT[] NOT NULL DEFAULT '{}',
    nice_to_have      TEXT[] NOT NULL DEFAULT '{}',
    size              TEXT,
    search_text       TEXT NOT NULL,
    embedding         VECTOR(__EMBED_DIM__),
    status            TEXT NOT NULL DEFAULT 'open'
                      CHECK (status IN ('open', 'matched', 'closed')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- matches ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS matches (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id  TEXT NOT NULL REFERENCES requests (id) ON DELETE CASCADE,
    item_id     TEXT NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    score       DOUBLE PRECISION NOT NULL,
    rank        INT NOT NULL,
    reason      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'suggested'
                CHECK (status IN ('suggested', 'accepted'))
);
CREATE INDEX IF NOT EXISTS matches_request_idx ON matches (request_id);

-- ---- agent_events (activity feed) -----------------------------------------------
-- The feed polls GET /api/events?after=<id>, so id must keep increasing.
-- No FK on item_id/request_id: events are emitted before those rows exist.
CREATE TABLE IF NOT EXISTS agent_events (
    id          BIGINT GENERATED ALWAYS AS IDENTITY,
    agent       TEXT NOT NULL,
    item_id     TEXT,
    request_id  TEXT,
    message     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, created_at)          -- hypertables need the time column in the PK
);
CREATE INDEX IF NOT EXISTS agent_events_id_idx ON agent_events (id);

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
    PERFORM create_hypertable('agent_events', by_range('created_at', INTERVAL '1 day'),
                              if_not_exists => TRUE);
  END IF;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'could not make agent_events a hypertable: %', SQLERRM;
END $$;

-- ---- listings (marketplace stretch; matches the cloud/marketplace-nostr branch) --
CREATE TABLE IF NOT EXISTS listings (
    id               TEXT PRIMARY KEY,                  -- lst_xxxx
    item_id          TEXT NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    platform         TEXT NOT NULL,                     -- nostr (roadmap: ebay, etsy, shopify)
    external_id      TEXT,                              -- Nostr event id (hex)
    price            DOUBLE PRECISION,
    listed_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at       TIMESTAMPTZ,
    url              TEXT,
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'expired')),
    dry_run          BOOLEAN NOT NULL DEFAULT TRUE,
    relays_accepted  TEXT[] NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS listings_status_idx ON listings (status);
