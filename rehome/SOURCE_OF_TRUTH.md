# Source of truth

Read this before making any change. If you are an AI coding assistant, read this file and the relevant doc in `docs/` before editing code, and append to the change log when you change a contract.

## Rules that must not break

1. **The orchestrator is the only code that touches the database.** Agents return JSON; they never read or write the DB. Routers call the orchestrator, not the DB.
2. **`frontend/src/lib/api.js` is the only frontend file that calls the backend.**
3. **Schemas live in one place per side:** `backend/app/schemas.py` and `docs/03`, `docs/04`, `docs/05`. If they disagree, the docs win; fix the code.
4. **Item status values:** `available`, `listed`, `reserved`, `donated`. Nothing else.
5. **Every agent step emits an event** via `agents/events.py` so the activity feed stays complete.
6. **No API keys in code.** Read them from `.env` through `core/config.py`.
7. **Frontend and backend stay in their folders.** Don't edit the other side's code without telling its owner.

## Current decisions

| Decision | Choice | Status |
|---|---|---|
| Frontend | SvelteKit | Decided |
| Backend | FastAPI | Decided |
| Model provider | Modal (vision-capable model) | Decided, Gemini optional |
| Database | Sponsor DB with vector search; in-memory stub until wired | Open |
| Marketplace listing | Nostr NIP-99 classifieds (kind 30402), shown on Shopstr; dry run by default. eBay/Etsy/Shopify on the roadmap | Decided |
| Kiosk | Stretch | Open |
| Project name | "Rehome" (placeholder) | Open |

## Change log

Add one line per contract change: date, who, what, which files.

- 2026-10-17 · scaffold · initial structure, schemas, and docs
- 2026-10-18 · ibrahim · marketplace via Nostr NIP-99 (Shopstr): `POST /api/items/{id}/list`, `POST /api/admin/simulate-expiry`, `GET /api/listings`; listings.platform = `nostr` + `url`, `status`, `dry_run`, `relays_accepted` · `docs/02`, `docs/03`, `docs/04`, `docs/06`, `backend/app/integrations/marketplace.py`, `agents/orchestrator.py`, `core/db.py`, `core/config.py`, `schemas.py`, `routers/items.py`, `routers/admin.py`, `routers/listings.py`, `.env.example`
- 2026-10-18 · ibrahim · offline demo + API hardening: `PUBLIC_BASE_URL` makes `items.image_url` absolute (Nostr `image` tag only for public URLs); `CORS_ORIGINS`; `POST /api/items` returns `415` for non-JPG/PNG/WebP; `status` query params validated (`422`); `POST /api/admin/seed` loads 18 items once and returns `{"seeded": n}`; keyword stub agents + stub ranking documented; routers no longer import `db` · `docs/03`, `docs/04`, `docs/05`, `.env.example`, `README.md`, `backend/app/agents/stub_rules.py`, `agents/orchestrator.py`, `seed_data.py`, `core/config.py`, `core/llm.py`, `main.py`, `routers/*`, `integrations/marketplace.py`
- 2026-10-18 · ibrahim · listings gain `nostr_url` (njump); `GET /api/listings` returns each listing with its `item`, newest first; HTML preview pages `GET /listings` and `GET /listings/{item_id}`; `SEED_IMAGE_BASE_URL` for public seed photos · `docs/03`, `docs/04`, `schemas.py`, `agents/orchestrator.py`, `integrations/marketplace.py`, `routers/pages.py`, `main.py`
