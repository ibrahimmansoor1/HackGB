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
│   │   └── routers/
│   │       ├── items.py
│   │       ├── requests.py
│   │       ├── admin.py    ← demo seed data
│   │       └── events.py
│   └── tests/
│       └── test_api.py
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
