"""FastAPI entrypoint: uvicorn app.main:app --reload --port 8000"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.agents import orchestrator
from app.core import config
from app.routers import admin, events, impact, items, listings, matches, requests

app = FastAPI(title="Rehome API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,  # SvelteKit dev/preview; set CORS_ORIGINS in .env
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(items.router)
app.include_router(requests.router)
app.include_router(matches.router)
app.include_router(events.router)
app.include_router(impact.router)
app.include_router(admin.router)
app.include_router(listings.router)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.get("/api/health")
async def health():
    return {"status": "ok", "stubs": config.USE_STUBS, "db": orchestrator.db_backend()}
