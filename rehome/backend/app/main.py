"""FastAPI entrypoint: uvicorn app.main:app --reload --port 8000"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core import config
from app.routers import admin, events, items, requests

app = FastAPI(title="Rehome API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # SvelteKit dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(items.router)
app.include_router(requests.router)
app.include_router(events.router)
app.include_router(admin.router)
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parents[1] / "static"),
          name="static")


@app.get("/api/health")
async def health():
    return {"status": "ok", "stubs": config.USE_STUBS}
