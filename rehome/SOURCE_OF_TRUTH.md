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
- 2026-10-18 · shuja · build step 2, Gemini parser: `ParsedItem.brand` (null unless on a tag or in the text); parser calls Gemini `generateContent` when `GEMINI_API_KEY` is set (`GEMINI_MODEL`, default `gemini-2.5-flash`), else the keyword stub, independent of Modal; accepts several photos; shared `ATTRIBUTE_VOCAB` in both parser and requester prompts · `backend/app/agents/{parser,requester,stub_rules,orchestrator}.py`, `core/{llm,config}.py`, `schemas.py`, `tests/{conftest,test_parser}.py`, `.env.example`, `README.md`
- 2026-10-18 · shuja · build step 3, sell/donate split (donate side): `POST /api/items/parse` (multi-photo `images`, `text`) stores a draft (Tiger `drafts` table + `draft_seq`, JSONB `item`; 24 h TTL) and returns `DraftOut`; `POST /api/items/{draft_id}/donate` (optional `pickup_zip`) embeds, inserts, consumes the draft atomically; parser failure is `502` on both parse routes; "New item received" replaces "New donation received"; donate page uses parse → donate · `docs/03`, `docs/04`, `backend/app/{schemas,routers/items}.py`, `agents/orchestrator.py`, `core/{db,db_pg}.py`, `db/schema.sql`, `scripts/init_db.py`, `tests/{conftest,test_drafts,test_demo,test_tiger}.py`, `frontend/src/lib/api.js`, `frontend/src/routes/donate/+page.svelte`
- 2026-10-18 · shuja · build step 4, requester + accept: `StructuredQuery.need` → `needs: list` (min 1); `Match.title` (brand + item); `POST /api/requests` no longer reserves ("Top match itm_x (0.89)" event); `POST /api/matches/accept` reserves atomically, marks the match `accepted` and the request `closed`, emits `match_accepted`; `409` also when the request is already closed; request page gets a Claim button · `docs/04`, `backend/app/{schemas,main}.py`, `routers/matches.py`, `agents/{orchestrator,requester,stub_rules}.py`, `core/{db,db_pg}.py`, `tests/{test_matches,test_demo,test_tiger}.py`, `frontend/src/lib/api.js`, `frontend/src/routes/request/+page.svelte`
- 2026-10-18 · shuja · build step 5, pricing + eBay: `POST /api/items/{draft_id}/sell` → `SellOut` (`suggested_price`, `comps`, `listing_draft`, `basis`); `integrations/ebay.py` (Browse API, app-only OAuth, `EBAY_APP_ID`/`EBAY_CERT_ID`/`EBAY_ENV`/`EBAY_MARKETPLACE`); `agents/pricing.py` (Modal; stub = 60–90 % of the comparable comps' median); comps the model returns are kept only if they were real input listings; no keys / eBay error / no comparable comps → estimate (`suggest_price` ±20 %); `price_quoted` event; draft is not consumed · `backend/app/{schemas,core/config}.py`, `agents/{pricing,orchestrator}.py`, `integrations/ebay.py`, `routers/items.py`, `tests/{conftest,test_pricing}.py`, `.env.example`, `README.md`, `frontend/src/lib/api.js`, `frontend/src/routes/donate/+page.svelte`
- 2026-10-18 · shuja · build step 6, impact: `GET /api/impact` → `ImpactOut` (`totals` always has all six keys, `by_category` sorted by items_donated, `hourly` last 24 h summed over categories); reads `impact_hourly` on Tiger, the in-memory events otherwise (`db.impact_rows`); `/feed` shows impact tiles + per-category table above the activity feed · `docs/04`, `backend/app/{schemas,main}.py`, `routers/impact.py`, `agents/orchestrator.py`, `core/{db,db_pg}.py`, `tests/{test_impact,test_tiger}.py`, `README.md`, `frontend/src/lib/{api.js,ImpactStats.svelte,ActivityFeed.svelte}`, `frontend/src/routes/feed/+page.svelte`
- 2026-10-18 · shuja · Modal text model: `infra/modal_llm.py` (vLLM, Gemma 4 26B-A4B, tool calling via `--tool-call-parser gemma4`, served as `llm`); `MODAL_AGENT_MODEL` env (defaults to `MODAL_VISION_MODEL`); match threshold follows the embeddings (stub cutoff 0.2 whenever `MODAL_EMBED_MODEL` is blank, even with a real text model) · `infra/modal_llm.py`, `backend/app/core/{config,llm}.py`, `agents/orchestrator.py`, `tests/test_api.py`, `.env.example`, `README.md`
- 2026-10-18 · shuja · matchmaker agent + post a draft: after `/donate`, the matchmaker checks non-closed requests (`db.open_requests_near`, pgvector on Tiger), adds the item as a `suggested` match, moves `open` → `matched`, emits `matchmaker` events; `DonateOut.waiting_requests`; `POST /api/items/{draft_id}/post` (`{price?}`) turns a draft into a listed item (no `item_donated` count); `list_item` takes an optional price; agents `concierge` + `matchmaker` allowed in events · `docs/04`, `backend/app/{schemas,routers/items}.py`, `agents/orchestrator.py`, `core/{db,db_pg}.py`, `tests/{test_matchmaker,test_drafts,test_tiger}.py`
- 2026-10-18 · shuja · concierge agent (LangGraph): `POST /api/items/{draft_id}/handle` (`{preference: auto|sell|donate}`) → `HandleOut` (`action`, `item_id`, `summary`, `brain` modal|rules, `steps`, `price_quote`, `waiting_requests`, `listing`); tools `get_price_quote`, `check_local_demand`, `list_for_sale(price)`, `donate_item`; model = `MODAL_AGENT_MODEL` via `langchain-openai` on `MODAL_ENDPOINT_URL`; rule policy offline or on model failure (donate if someone is waiting or worth < $15, else list at the quote midpoint); acts once per draft; recursion limit 12 · `backend/app/agents/concierge.py`, `routers/items.py`, `schemas.py`, `agents/orchestrator.py`, `tests/test_concierge.py`, `requirements.txt`
