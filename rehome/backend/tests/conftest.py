"""Every test starts with an empty in-memory DB (ids keep counting up)."""
import pytest

from app.agents import orchestrator
from app.core import db


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    for name in ("_items", "_requests", "_listings"):
        monkeypatch.setattr(db, name, {})
    for name in ("_matches", "_events"):
        monkeypatch.setattr(db, name, [])
    monkeypatch.setattr(orchestrator, "_seeded", [])
    monkeypatch.setattr(orchestrator, "_listing_now", set())
