-- Tiger Data (Postgres + TimescaleDB + pgvector) schema. Mirror of docs/03.
-- Applied by scripts/init_db.py, which fills in {EMBED_DIM} and runs each
-- statement on its own (continuous aggregates can't run inside a transaction).
-- Safe to re-run.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE SEQUENCE IF NOT EXISTS item_seq;
CREATE SEQUENCE IF NOT EXISTS request_seq;
CREATE SEQUENCE IF NOT EXISTS match_seq;
CREATE SEQUENCE IF NOT EXISTS listing_seq;
CREATE SEQUENCE IF NOT EXISTS draft_seq;

-- Parsed uploads waiting for the donor to choose sell or donate.
CREATE TABLE IF NOT EXISTS drafts (
  id TEXT PRIMARY KEY,
  donor_id TEXT NOT NULL,
  zip TEXT,
  note TEXT,
  image_url TEXT,
  item JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  donor_id TEXT NOT NULL,
  image_url TEXT,
  note TEXT,
  zip TEXT,
  category TEXT,
  item TEXT,
  brand TEXT,
  color TEXT,
  size TEXT,
  condition TEXT,
  season TEXT,
  attributes TEXT[] NOT NULL DEFAULT '{}',
  summary TEXT,
  status TEXT NOT NULL DEFAULT 'available'
    CHECK (status IN ('available', 'listed', 'reserved', 'donated')),
  embedding VECTOR({EMBED_DIM}),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS items_embedding_idx ON items USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS items_status_idx ON items (status);

CREATE TABLE IF NOT EXISTS requests (
  id TEXT PRIMARY KEY,
  requester_id TEXT NOT NULL,
  raw_text TEXT NOT NULL,
  zip TEXT,
  needs TEXT[] NOT NULL DEFAULT '{}',
  inferred_context TEXT[] NOT NULL DEFAULT '{}',
  must_have TEXT[] NOT NULL DEFAULT '{}',
  nice_to_have TEXT[] NOT NULL DEFAULT '{}',
  size TEXT,
  search_text TEXT,
  embedding VECTOR({EMBED_DIM}),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'matched', 'closed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS matches (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL REFERENCES requests(id),
  item_id TEXT NOT NULL REFERENCES items(id),
  score REAL,
  rank INT,
  reason TEXT,
  status TEXT NOT NULL DEFAULT 'suggested' CHECK (status IN ('suggested', 'accepted'))
);
CREATE INDEX IF NOT EXISTS matches_request_idx ON matches (request_id);

CREATE TABLE IF NOT EXISTS listings (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL REFERENCES items(id),
  platform TEXT NOT NULL,
  external_id TEXT NOT NULL,
  price DOUBLE PRECISION NOT NULL,   -- REAL would turn 24.99 into 24.9899997
  listed_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  url TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired')),
  dry_run BOOLEAN NOT NULL,
  relays_accepted TEXT[] NOT NULL DEFAULT '{}'
);

-- Activity feed + impact stats. Hypertable on `time`; the feed polls by `id`.
CREATE TABLE IF NOT EXISTS events (
  time TIMESTAMPTZ NOT NULL DEFAULT now(),
  id BIGSERIAL,
  agent TEXT NOT NULL,
  event_type TEXT,
  item_id TEXT,
  request_id TEXT,
  category TEXT,
  message TEXT NOT NULL,
  PRIMARY KEY (time, id)
);
SELECT create_hypertable('events', by_range('time'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS events_id_idx ON events (id);

-- Live impact stats. materialized_only = false so the dashboard also sees
-- events newer than the last refresh (real-time aggregation).
CREATE MATERIALIZED VIEW IF NOT EXISTS impact_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket('1 hour', time) AS bucket,
       event_type, category, count(*) AS n
FROM events
WHERE event_type IS NOT NULL
GROUP BY bucket, event_type, category
WITH NO DATA;

SELECT add_continuous_aggregate_policy('impact_hourly',
  start_offset => INTERVAL '7 days',
  end_offset => INTERVAL '1 minute',
  schedule_interval => INTERVAL '1 minute',
  if_not_exists => TRUE);
