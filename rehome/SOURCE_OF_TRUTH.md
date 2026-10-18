# Source of truth

Read this before making any change. If you are an AI coding assistant, read this file and the relevant doc in `docs/` before editing code, and append to the change log when you change a contract.

**HackGB 2026 · Devpost deadline 12:00 PM CDT, Sun Oct 18.** Repo: `github.com/shuja-waraich-03/HackGB`. Work on branches, merge via PR. Never commit `.env`.

## Rules that must not break

1. **The orchestrator is the only code that touches the database.** Agents are pure prompt → JSON functions; they never read or write the DB. Routers call the orchestrator, not the DB.
2. **`frontend/src/lib/api.js` is the only frontend file that calls the backend.**
3. **Schemas live in one place per side:** `backend/app/schemas.py` and `docs/03`, `docs/04`, `docs/05`. If they disagree, the docs win; fix the code.
4. **Item status values:** `available`, `listed`, `reserved`, `donated`. Nothing else.
5. **Every agent step emits an event** via `agents/events.py` (feeds the activity feed and the Tiger `events` hypertable).
6. **No API keys in code.** Read them from `.env` through `core/config.py`.
7. **Frontend and backend stay in their folders.** Don't edit the other side's code without telling its owner.
8. **Parser and requester share one attribute vocabulary** so both sides align in vector space.
9. **Reserve on accept, not on search.**

## Current decisions

| Decision | Choice | Status |
|---|---|---|
| Frontend | SvelteKit (Svelte 5), served on a **GoDaddy Registry** domain | Decided |
| Frontend styling | Tailwind CSS v4, Lucide icons (`@lucide/svelte`), bundled fonts; three.js only on the landing hero | Decided |
| Backend | FastAPI on **Vultr or DigitalOcean** | Decided; host not picked |
| Orchestrator | Deterministic Python, not an LLM loop; UI choice decides sell vs donate | Decided |
| Input parser | Gemini API (vision) | Decided |
| Requester, pricing, reasons, embeddings | Modal | Decided |
| Donation step | Plain function: Modal embedding → DB insert | Decided |
| Database | Tiger Data: pgvector + `events` hypertable + `impact_hourly` continuous aggregate; in-memory stub until wired | Decided |
| Price comps | eBay **Browse API** (active listings), labeled "currently listed for"; heuristic fallback | Decided; confirm API access |
| Donor flow | `parse` → draft → **Sell** or **Donate** | Decided |
| Handoff method | Pickup / drop-off / shipping | **Open**; demo says "reserved, donor notified, pickup in `<zip>`" |
| Marketplace listing | Nostr NIP-99 (Shopstr), dry run by default; stretch | Decided; linking sell drafts to it is **open** (ibrahim) |
| Kiosk | Webcam + distance sensor | Stretch |
| Project name | "Rehome" (placeholder) | Open |

## Change log

Add one line per contract change: date, who, what, which files.

- 2026-10-17 · scaffold · initial structure, schemas, and docs
- 2026-10-18 · ibrahim · marketplace via Nostr NIP-99 (Shopstr): `POST /api/items/{id}/list`, `POST /api/admin/simulate-expiry`, `GET /api/listings`; listings.platform = `nostr` + `url`, `status`, `dry_run`, `relays_accepted` · `docs/02`, `docs/03`, `docs/04`, `docs/06`, `backend/app/integrations/marketplace.py`, `agents/orchestrator.py`, `core/db.py`, `core/config.py`, `schemas.py`, `routers/items.py`, `routers/admin.py`, `routers/listings.py`, `.env.example`
- 2026-10-18 · ibrahim · offline demo + API hardening: `PUBLIC_BASE_URL` makes `items.image_url` absolute (Nostr `image` tag only for public URLs); `CORS_ORIGINS`; `POST /api/items` returns `415` for non-JPG/PNG/WebP; `status` query params validated (`422`); `POST /api/admin/seed` loads 18 items once and returns `{"seeded": n}`; keyword stub agents + stub ranking documented; routers no longer import `db` · `docs/03`, `docs/04`, `docs/05`, `.env.example`, `README.md`, `backend/app/agents/stub_rules.py`, `agents/orchestrator.py`, `seed_data.py`, `core/config.py`, `core/llm.py`, `main.py`, `routers/*`, `integrations/marketplace.py`
- 2026-10-18 · shuja · HackGB design (docs only; **code not yet updated**): sell/donate split (`POST /api/items/parse`, `/{draft_id}/sell`, `/{draft_id}/donate`; `POST /api/items` kept as legacy shortcut); `POST /api/matches/accept` (reserve on accept, not search); `GET /api/impact`; `ParsedItem.brand`; `StructuredQuery.need` → `needs: list`; match `title`; events gain `event_type`, `category`, agent `pricing`; Gemini parser, Modal requester/pricing/embeddings, eBay Browse comps, Tiger Data schema; drafts + `requests.closed` on accept · `docs/01`–`07`, `SOURCE_OF_TRUTH.md`
- 2026-10-18 · shuja · build step 1, Tiger DB: `core/db_pg.py` (psycopg + pgvector) replaces the in-memory stub when `DATABASE_URL` is set; `db/schema.sql` + `scripts/init_db.py`; `EMBED_DIM` env; events carry `event_type` + `category` (item_parsed, item_donated, request_made, match_made emitted); `/api/health` adds `db`; seed won't duplicate after a restart · `backend/app/core/{db,db_pg,config,llm}.py`, `agents/{events,orchestrator}.py`, `schemas.py`, `main.py`, `tests/{conftest,test_tiger}.py`, `requirements.txt`, `.env.example`, `README.md`, `docs/03`, `docs/04`
- 2026-10-18 · ibrahim · listings gain `nostr_url` (njump); `GET /api/listings` returns each listing with its `item`, newest first; HTML preview pages `GET /listings` and `GET /listings/{item_id}`; `SEED_IMAGE_BASE_URL` for public seed photos · `docs/03`, `docs/04`, `schemas.py`, `agents/orchestrator.py`, `integrations/marketplace.py`, `routers/pages.py`, `main.py`
- 2026-10-18 · ibrahim · `POST /api/admin/reset` (closes active listings, clears demo inventory, keeps events) · `docs/04`, `core/db.py`, `agents/orchestrator.py`, `routers/admin.py`
- 2026-10-18 · ibrahim · `/api/health` adds `marketplace` (`live`/`dry_run`); listing `502` detail names each relay's reason · `docs/04`, `main.py`, `agents/orchestrator.py`, `integrations/marketplace.py`
