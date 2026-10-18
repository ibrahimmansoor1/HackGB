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
│   │   ├── agents/
│   │   │   ├── orchestrator.py
│   │   │   ├── parser.py
│   │   │   ├── requester.py
│   │   │   └── events.py   ← activity feed logger
│   │   ├── integrations/
│   │   │   └── marketplace.py ← Nostr NIP-99 listings (Shopstr), pricing
│   │   └── routers/
│   │       ├── items.py
│   │       ├── requests.py
│   │       ├── admin.py    ← demo seed data, simulate-expiry
│   │       ├── listings.py
│   │       └── events.py
│   ├── scripts/
│   │   └── nostr_keygen.py ← one-time Nostr key setup
│   └── tests/
│       ├── test_api.py
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

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in keys
uvicorn app.main:app --reload --port 8000
# docs at http://localhost:8000/docs
```

**Frontend**
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

The frontend reads `PUBLIC_API_URL` (default `http://localhost:8000`).

## Working together

- `main` must always run. Work on branches, merge with a PR.
- Backend people never edit `frontend/`; frontend never edits `backend/`. The contract between them is `docs/04-api-contract.md`.
- Changing a schema or endpoint? Update the doc **first**, then the code, then add a line to `SOURCE_OF_TRUTH.md`.

## Before the model is wired up

With no `MODAL_ENDPOINT_URL` in `.env`, the backend runs in **stub mode**: agents return fake but valid data, so the frontend can be built end to end on day one. Load demo inventory with:

```bash
curl -X POST http://localhost:8000/api/admin/seed
```

`GET /api/health` reports `"stubs": true` while stub mode is on.

## Marketplace (Nostr/Shopstr)

`POST /api/items/{id}/list` prices an item and posts it as a [NIP-99](https://github.com/nostr-protocol/nips/blob/master/99.md) classified listing (Nostr event kind 30402), using [`nostr-sdk`](https://pypi.org/project/nostr-sdk/). Listings show publicly on [Shopstr](https://shopstr.store) and any other Nostr marketplace client. `POST /api/admin/simulate-expiry` fast-forwards 30 days: listings are closed (republished with `status=sold`) and the items go back to the donation pool. eBay, Etsy, and Shopify are on the roadmap behind the same `Channel` interface.

**Dry run is the default.** Without a key, or with `MARKETPLACE_DRY_RUN=true`, events are signed with a throwaway key and never sent; responses say `"dry_run": true`.

| Env var | Default | Meaning |
|---|---|---|
| `NOSTR_NSEC` | empty | Storefront secret key (`nsec1…`). Secret: `.env` only. |
| `NOSTR_RELAYS` | `wss://relay.damus.io,wss://nos.lol,wss://relay.primal.net` | Comma-separated relays to publish to |
| `MARKETPLACE_DRY_RUN` | `true` | Set to `false` to publish for real |
| `LISTING_LOCATION` | empty | Public `location` tag (falls back to the item's zip) |

**First live post**
```bash
cd backend
python scripts/nostr_keygen.py        # prints NOSTR_NSEC=nsec1... and your npub; run once
# in ../.env: NOSTR_NSEC=nsec1...   MARKETPLACE_DRY_RUN=false   LISTING_LOCATION=Boston, MA
uvicorn app.main:app --reload --port 8000
curl -X POST http://localhost:8000/api/admin/seed
curl -X POST http://localhost:8000/api/items/itm_0001/list
```
The response's `listing.url` (`https://shopstr.store/listing/<naddr>`) opens the listing; every listing from your key is also at `https://shopstr.store/marketplace/<npub>`. `relays_accepted` shows which relays stored it. If no relay accepts it, the API returns `502` and the item stays `available`. New listings can take a few seconds to appear on Shopstr. Items with uploaded photos only get an `image` tag when `image_url` is a public `http(s)` URL; local `/static/...` paths are skipped.
