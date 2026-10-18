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
├── backend/                ← FastAPI
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py         ← app + CORS + router registration
│   │   ├── schemas.py      ← Pydantic models (mirror of docs/03 and docs/05)
│   │   ├── core/
│   │   │   ├── config.py   ← env settings
│   │   │   ├── db.py       ← database access (in-memory stub until sponsor DB is wired)
│   │   │   └── llm.py      ← model client (Modal), embeddings
│   │   ├── seed_data.py    ← 18 demo items for POST /api/admin/seed
│   │   ├── agents/
│   │   │   ├── orchestrator.py
│   │   │   ├── parser.py
│   │   │   ├── requester.py
│   │   │   ├── stub_rules.py ← offline keyword rules used when no model is set
│   │   │   └── events.py   ← activity feed logger
│   │   ├── integrations/
│   │   │   └── marketplace.py ← Nostr NIP-99 listings (Shopstr), pricing
│   │   └── routers/
│   │       ├── items.py
│   │       ├── requests.py
│   │       ├── admin.py    ← demo seed data, simulate-expiry
│   │       ├── listings.py
│   │       ├── pages.py    ← HTML listing previews at /listings
│   │       └── events.py
│   ├── static/seed/        ← demo item photos (served at /static/seed/…)
│   ├── scripts/
│   │   ├── nostr_keygen.py ← one-time Nostr key setup
│   │   ├── make_seed_images.py ← redraws static/seed/
│   │   └── smoke_test.py   ← calls every endpoint on a running server, PASS/FAIL
│   └── tests/
│       ├── conftest.py     ← fresh in-memory DB per test
│       ├── test_api.py
│       ├── test_demo.py    ← the docs/07 demo end to end, offline
│       └── test_marketplace.py
└── frontend/               ← SvelteKit
    ├── package.json
    ├── svelte.config.js
    ├── vite.config.js
    └── src/
        ├── app.html
        ├── lib/
        │   ├── api.js      ← the ONLY file that calls the backend
        │   └── ActivityFeed.svelte
        └── routes/
            ├── +layout.svelte
            ├── +page.svelte        ← landing: donate or request
            ├── donate/+page.svelte
            ├── request/+page.svelte
            └── feed/+page.svelte   ← full-screen activity feed for the demo laptop
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

The frontend reads `PUBLIC_API_URL` (default `http://localhost:8000`).

**Two laptops (app + feed screen):** run the backend with `--host 0.0.0.0`, then in `.env` set `PUBLIC_BASE_URL=http://<backend laptop's IP>:8000` (so photo links work from the other laptop) and add the frontend's origin to `CORS_ORIGINS`.

## Working together

- `main` must always run. Work on branches, merge with a PR.
- Backend people never edit `frontend/`; frontend never edits `backend/`. The contract between them is `docs/04-api-contract.md`.
- Changing a schema or endpoint? Update the doc **first**, then the code, then add a line to `SOURCE_OF_TRUTH.md`.

## Before the model is wired up

With no `MODAL_ENDPOINT_URL` in `.env`, the backend runs in **stub mode**, and the whole demo still works offline with no keys. Deterministic keyword rules (`backend/app/agents/stub_rules.py`, described in `docs/05`) parse donor notes and infer context, so "need a warm coat, moving to Chicago in December" matches insulated, water-resistant outerwear with a reason for each match. `GET /api/health` reports `"stubs": true` while stub mode is on.

The in-memory DB resets when the backend restarts. Between demo rehearsals, either restart it or call `POST /api/admin/reset` (closes any live listings first, clears the inventory, keeps the activity feed), then seed again.

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
| [Modal](https://modal.com) | Hosts the vision + text model and embeddings behind `MODAL_ENDPOINT_URL` (OpenAI-compatible API). Without it, the app runs in offline stub mode. |
| [nostr-sdk](https://pypi.org/project/nostr-sdk/) (rust-nostr Python bindings) | Builds and signs NIP-99 classified listings (kind 30402) and sends them to relays |
| [Nostr](https://nostr.com) relays + [Shopstr](https://shopstr.store) | Public marketplace where listed items appear; NIP-99 is an open standard, so no API key or developer approval is needed |
| Google Gemini *(optional)* | Alternative model provider if credits arrive (`GEMINI_API_KEY`) |
