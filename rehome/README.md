# Rehome

> Working name — rename before submission.

Snap a photo of something you no longer need; AI agents describe it, store it, and match it to someone who needs it. People who need things just say what they need ("warm coat, moving to Chicago in December") and get matched with donated items.

**Tracks:** Sustainability · database sponsor · Modal

## Repo layout

```
rehome/
├── README.md               ← you are here
├── SOURCE_OF_TRUTH.md      ← read before every change (humans and AI assistants)
├── .gitignore
├── .env.example            ← copy to .env, never commit .env
├── docs/
│   ├── 01-overview.md      ← problem, solution, pitch
│   ├── 02-architecture.md  ← components and data flow
│   ├── 03-data-model.md    ← tables / collections
│   ├── 04-api-contract.md  ← every endpoint, request and response
│   ├── 05-agents.md        ← agent prompts and JSON schemas
│   ├── 06-mvp-scope.md     ← what's in, what's stretch, build order, owners
│   └── 07-demo-script.md   ← expo table walkthrough
├── infra/modal_llm.py      ← Modal vLLM server (tool calling) for the agents
├── backend/                ← FastAPI
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py         ← app + CORS + router registration
│   │   ├── schemas.py      ← Pydantic models (mirror of docs/03 and docs/05)
│   │   ├── core/
│   │   │   ├── config.py   ← env settings
│   │   │   ├── db.py       ← database access (in-memory stub; Tiger when DATABASE_URL is set)
│   │   │   ├── db_pg.py    ← Tiger Data (Postgres + pgvector) version of db.py
│   │   │   └── llm.py      ← model clients (Gemini parser, Modal text + embeddings)
│   │   ├── seed_data.py    ← 18 demo items for POST /api/admin/seed
│   │   ├── agents/
│   │   │   ├── concierge.py ← LangGraph agent: prices, checks demand, lists or donates
│   │   │   ├── orchestrator.py ← deterministic service layer; owns the DB; matchmaker
│   │   │   ├── parser.py   ← photo/text → ParsedItem (Gemini)
│   │   │   ├── pricing.py  ← item + eBay comps → price range + listing draft (Modal)
│   │   │   ├── requester.py
│   │   │   ├── stub_rules.py ← offline keyword rules used when no model is set
│   │   │   └── events.py   ← activity feed logger
│   │   ├── integrations/
│   │   │   ├── ebay.py     ← Browse API search (active listings as comps)
│   │   │   └── marketplace.py ← Nostr NIP-99 listings (Shopstr), heuristic price
│   │   └── routers/
│   │       ├── items.py    ← parse, sell, donate (+ legacy one-step donate, list)
│   │       ├── requests.py
│   │       ├── matches.py  ← accept a match
│   │       ├── impact.py   ← dashboard stats
│   │       ├── admin.py    ← demo seed data, simulate-expiry
│   │       ├── listings.py
│   │       ├── pages.py    ← HTML listing previews at /listings
│   │       └── events.py
│   ├── db/schema.sql       ← Tiger tables, hypertable, continuous aggregate
│   ├── static/seed/        ← demo item photos (served at /static/seed/…)
│   ├── scripts/
│   │   ├── init_db.py      ← creates the Tiger tables from db/schema.sql
│   │   ├── db_status.py    ← read-only: is the database in DATABASE_URL ready for this code?
│   │   ├── nostr_keygen.py ← one-time Nostr key setup
│   │   ├── make_seed_images.py ← redraws static/seed/
│   │   └── smoke_test.py   ← calls every endpoint on a running server, PASS/FAIL
│   └── tests/
│       ├── conftest.py     ← fresh in-memory DB per test
│       ├── test_api.py
│       ├── test_demo.py    ← the docs/07 demo end to end, offline
│       ├── test_drafts.py  ← parse → donate
│       ├── test_matches.py ← request → accept
│       ├── test_concierge.py ← concierge agent (rules + faked Modal model)
│       ├── test_matchmaker.py ← donations filling waiting requests
│       ├── test_impact.py  ← /api/impact
│       ├── test_parser.py  ← Gemini parser (HTTP faked)
│       ├── test_pricing.py ← sell: eBay comps, pricing agent, estimate fallback
│       ├── test_marketplace.py
│       └── test_tiger.py   ← Postgres backend; runs only with TEST_DATABASE_URL
└── frontend/               ← SvelteKit + Tailwind CSS v4 + Lucide icons
    ├── package.json
    ├── svelte.config.js
    ├── vite.config.js
    └── src/
        ├── app.html
        ├── app.css         ← Tailwind entry + color/font tokens (light and dark)
        ├── lib/
        │   ├── api.js      ← the ONLY file that calls the backend
        │   ├── pending.js  ← hands a photo picked on the landing page to /donate
        │   ├── ActivityFeed.svelte
        │   ├── ImpactStats.svelte ← /api/impact tiles + per-category table
        │   ├── ListingInfo.svelte ← price, live/practice/expired badge, listing links
        │   ├── components/SiteHeader.svelte
        │   └── landing/
        │       ├── ascii-home.js       ← three.js scene redrawn as ASCII (hero)
        │       ├── AsciiHome.svelte
        │       ├── figures.js          ← isometric line drawings for "How it works"
        │       ├── WireFigure.svelte
        │       ├── ItemTag.svelte      ← inventory item as a hang tag
        │       └── LiveActivity.svelte ← compact agent feed
        └── routes/
            ├── +layout.svelte      ← fonts, header
            ├── +page.svelte        ← landing: give or get help
            └── (app)/              ← task pages share a narrow layout
                ├── +layout.svelte
                ├── donate/+page.svelte      ← photo/text → sell (quote, list on Shopstr) or donate
                ├── request/+page.svelte     ← need → matches → claim
                ├── marketplace/+page.svelte ← listings + "simulate 30 days"
                └── feed/+page.svelte        ← impact dashboard + activity feed for the demo laptop
```

## Run it

Needs **Python 3.11 or 3.12** (the pinned numpy/pydantic don't install on 3.14) and **Node 18+**. Every command below starts from the `rehome/` folder:

```bash
git clone https://github.com/shuja-waraich-03/HackGB.git
cd HackGB/rehome
```

**Backend: macOS / Linux**
```bash
cp .env.example .env            # works as is: no keys needed for the demo
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Backend: Windows PowerShell**
```powershell
Copy-Item .env.example .env     # works as is: no keys needed for the demo
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs. Run the tests from `backend/` with the venv active: `python -m pytest`. To check every endpoint on the running server, open a second terminal in `backend/` (venv active) and run `python scripts/smoke_test.py`: it prints PASS/FAIL per endpoint.

**Load the demo inventory** (18 items with photos) in a second terminal:
```bash
curl -X POST http://localhost:8000/api/admin/seed                       # macOS / Linux
```
```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/admin/seed     # Windows PowerShell
```

**Frontend** (new terminal, from `rehome/`)
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

The frontend reads `PUBLIC_API_URL` (default `http://localhost:8000`) from `frontend/.env` (copy `frontend/.env.example`).

**Feature-check page (Streamlit, no Node needed).** Clicks through every endpoint: parse → sell / donate, request → claim, inventory, listing + 30-day expiry, impact, activity feed. With the backend running, from `backend/` with the venv active:
```bash
pip install -r requirements-verify.txt
streamlit run tools/verify_app.py   # http://localhost:8501
```
Set `REHOME_API` (or the sidebar field) to check another backend.

**Two laptops (app + feed screen):** laptop 1 runs everything; laptop 2 only opens a browser.
1. Laptop 1, backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000`. In `rehome/.env` set `PUBLIC_BASE_URL=http://<laptop 1 IP>:8000` (photo links) and add `http://<laptop 1 IP>:5173` to `CORS_ORIGINS`.
2. Laptop 1, frontend: in `frontend/.env` set `PUBLIC_API_URL=http://<laptop 1 IP>:8000`, then `npm run dev -- --host`.
3. Laptop 2: open `http://<laptop 1 IP>:5173/feed`.
If laptop 1's firewall asks, allow Python and Node on private networks. Find the IP with `ipconfig` (Windows) or `ipconfig getifaddr en0` (macOS).

**Between rehearsals:** `POST /api/admin/reset` then `POST /api/admin/seed` (both in `/docs`). If you restart the backend instead, reload `/feed` and the landing page.

## Working together

- `main` must always run. Work on branches, merge with a PR.
- Backend people never edit `frontend/`; frontend never edits `backend/`. The contract between them is `docs/04-api-contract.md`.
- Changing a schema or endpoint? Update the doc **first**, then the code, then add a line to `SOURCE_OF_TRUTH.md`.

## Before the model is wired up

With no `MODAL_ENDPOINT_URL` in `.env`, the backend runs in **stub mode**, and the whole demo still works offline with no keys. Each provider stubs on its own: no `GEMINI_API_KEY` → keyword parser; no `MODAL_ENDPOINT_URL` → stub requester, pricing, reasons, and embeddings. Deterministic keyword rules (`backend/app/agents/stub_rules.py`, described in `docs/05`) parse donor notes and infer context, so "need a warm coat, moving to Chicago in December" matches insulated, water-resistant outerwear with a reason for each match. `GET /api/health` reports `"stubs": true` while stub mode is on.

The in-memory DB resets when the backend restarts. Between demo rehearsals, either restart it or call `POST /api/admin/reset` (closes any live listings first, clears the inventory, keeps the activity feed), then seed again.

## Models on Modal

`infra/modal_llm.py` serves the text model as an OpenAI-compatible vLLM server with tool calling turned on, adapted from [Modal's vLLM example](https://modal.com/docs/examples/vllm_inference) (Gemma 4 26B-A4B on one H200, scales to zero after 15 minutes idle).

```bash
pip install modal && modal setup     # once
modal deploy infra/modal_llm.py      # prints the server URL
modal run infra/modal_llm.py         # optional: waits for it, checks a tool call works
```
In `.env`: `MODAL_ENDPOINT_URL=<URL>/v1`, `MODAL_VISION_MODEL=llm`, `MODAL_AGENT_MODEL=llm`. The first request after idle waits for a cold start (a few minutes); send one before the demo.

## Database (Tiger Data)

With `DATABASE_URL` blank the backend uses the in-memory DB. To use Tiger:

1. Create a service at [console.cloud.timescale.com](https://console.cloud.timescale.com) and copy its connection string (`postgres://tsdbadmin:...?sslmode=require`).
2. In `.env`, set `DATABASE_URL` to it, and `EMBED_DIM` to the embedding model's vector size (leave `384` for stub embeddings).
3. From `backend/` with the venv active, create the tables once:
   ```bash
   python scripts/db_status.py         # read-only check: READY, or which command to run
   python scripts/init_db.py           # safe to re-run
   python scripts/init_db.py --reset   # drop everything and start over (wipes data)
   ```
4. Restart the backend. `GET /api/health` reports `"db": "tiger"`.

Data now survives restarts; `POST /api/admin/seed` won't load the demo items twice. Between demo rehearsals, `POST /api/admin/reset` (in `/docs`) clears the demo data and keeps the tables.

- **Already have a Tiger DB from before this merge?** Run `python scripts/db_status.py`. If it says `run: init_db.py`, run that (it adds `listings.nostr_url` and keeps data). If it says `--reset`, the tables are from another schema version: `--reset` wipes them.
- **Changed `PUBLIC_BASE_URL` or `SEED_IMAGE_BASE_URL`** (for example a new tunnel URL)? Seeded rows keep the photo links they were saved with, so call `POST /api/admin/reset`, then seed again.

Postgres tests run in a throwaway `rehome_test` schema, so they're safe against the team's service:
```powershell
$env:TEST_DATABASE_URL = "postgres://..."; python -m pytest tests/test_tiger.py
```

## Marketplace (Nostr/Shopstr)

`POST /api/items/{id}/list` prices an item and posts it as a [NIP-99](https://github.com/nostr-protocol/nips/blob/master/99.md) classified listing (Nostr event kind 30402), using [`nostr-sdk`](https://pypi.org/project/nostr-sdk/). Listings show publicly on [Shopstr](https://shopstr.store) and any other Nostr marketplace client. `POST /api/admin/simulate-expiry` fast-forwards 30 days: listings are closed (republished with `status=sold`) and the items go back to the donation pool. eBay, Etsy, and Shopify are on the roadmap behind the same `Channel` interface.

**Dry run is the default.** Without a key, or with `MARKETPLACE_DRY_RUN=true`, events are signed with a throwaway key and never sent; responses say `"dry_run": true`.

| Env var | Default | Meaning |
|---|---|---|
| `NOSTR_NSEC` | empty | Storefront secret key (`nsec1…`). Secret: `.env` only. |
| `NOSTR_RELAYS` | `wss://relay.damus.io,wss://nos.lol,wss://relay.primal.net` | Comma-separated relays to publish to |
| `MARKETPLACE_DRY_RUN` | `true` | Set to `false` to publish for real |
| `LISTING_LOCATION` | empty | Public `location` tag (falls back to the item's zip) |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Base for photo URLs. Set it to a public URL (e.g. a tunnel) so listings carry a photo |

**First live post**
```bash
cd backend
python scripts/nostr_keygen.py        # prints NOSTR_NSEC=nsec1... and your npub; run once
# in ../.env: NOSTR_NSEC=nsec1...   MARKETPLACE_DRY_RUN=false   LISTING_LOCATION=Green Bay, WI
uvicorn app.main:app --reload --port 8000
curl -X POST http://localhost:8000/api/admin/seed
curl -X POST http://localhost:8000/api/items/itm_0001/list
```
The response's `listing.url` (`https://shopstr.store/listing/<naddr>`) opens the listing; every listing from your key is also at `https://shopstr.store/marketplace/<npub>`. `relays_accepted` shows which relays stored it. If no relay accepts it, the API returns `502` and the item stays `available`. New listings can take a few seconds to appear on Shopstr. **Shopstr hides listings without a photo**, and it refuses photo links on `localhost` or private LAN addresses. Photo URLs are built from `PUBLIC_BASE_URL`, so for a listing to show up, the backend has to be reachable from the internet. With a free Cloudflare quick tunnel (no account needed):

```powershell
winget install --id Cloudflare.cloudflared      # once (macOS: brew install cloudflared)
cloudflared tunnel --url http://localhost:8000  # leave running; prints https://<random>.trycloudflare.com
```

**No tunnel, seeded items only:** once the GitHub repo is public, set `SEED_IMAGE_BASE_URL=https://raw.githubusercontent.com/shuja-waraich-03/HackGB/<branch>/rehome/backend/static/seed` in `.env` (the branch must contain those photos). Seeded items then use photos hosted by GitHub. Photos donated during the demo still need the tunnel.

**With a tunnel:** put the tunnel URL in `.env` as `PUBLIC_BASE_URL=https://<random>.trycloudflare.com`, restart the backend, seed, then list. Keep the backend and the tunnel running while people view the listings: Shopstr loads the photo from your laptop. Relisting an item replaces its old listing (same `d` tag). If a live listing goes out without a public photo, the activity feed says so.

**See your listings:** open http://localhost:8000/listings for a storefront of everything listed (photos, prices, live/dry-run badges), or `http://localhost:8000/listings/<item_id>` for one listing with links to Shopstr and to njump.me (a plain Nostr viewer that works even when Shopstr's site is down). Your frontend can build the same cards from `GET /api/listings`, which includes each listing's item.

## AI tools and APIs used

Disclosed per HackGB rules.

| Tool / API | What we used it for |
|---|---|
| [Claude Code](https://claude.com/claude-code) (Anthropic) | AI coding assistant: helped write and review backend code, tests, and docs. Every change was reviewed and committed by the team. |
| [LangGraph](https://langchain-ai.github.io/langgraph/) + [langchain-openai](https://pypi.org/project/langchain-openai/) | The concierge agent's loop: a Modal tool-calling model chooses which specialist agent (pricing, matchmaker, Shopstr listing, donation) to call, then acts for the donor |
| [Google Gemini API](https://ai.google.dev) | Input parser: reads donor photos and text into a catalog item, brand and size from visible tags (`GEMINI_API_KEY`, `GEMINI_MODEL`) |
| [Modal](https://modal.com) | Hosts the text model (requester, pricing, match reasons) and embeddings behind `MODAL_ENDPOINT_URL` (OpenAI-compatible API). Without it, the app runs in offline stub mode. |
| [eBay Browse API](https://developer.ebay.com/api-docs/buy/browse/overview.html) | Active listings as pricing comps for the Sell path (`EBAY_APP_ID`, `EBAY_CERT_ID`); prices shown as "currently listed for". Without keys, Sell uses a category × condition estimate. |
| [nostr-sdk](https://pypi.org/project/nostr-sdk/) (rust-nostr Python bindings) | Builds and signs NIP-99 classified listings (kind 30402) and sends them to relays |
| [Nostr](https://nostr.com) relays + [Shopstr](https://shopstr.store) | Public marketplace where listed items appear; NIP-99 is an open standard, so no API key or developer approval is needed |
