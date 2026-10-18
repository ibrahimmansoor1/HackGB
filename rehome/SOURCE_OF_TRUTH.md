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
| eBay listing | Stretch | Open |
| Kiosk | Stretch | Open |
| Project name | "Rehome" (placeholder) | Open |

## Change log

Add one line per contract change: date, who, what, which files.

- 2026-10-17 · scaffold · initial structure, schemas, and docs
