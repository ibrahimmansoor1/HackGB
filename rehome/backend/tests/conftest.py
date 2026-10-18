"""Every test starts with an empty in-memory DB (ids keep counting up).
Tests never touch Tiger or Gemini, even if .env configures them; test_tiger.py
covers the Postgres backend against TEST_DATABASE_URL."""
import os

# Before app imports; load_dotenv won't override variables that are already set.
os.environ["DATABASE_URL"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["EBAY_APP_ID"] = os.environ["EBAY_CERT_ID"] = ""
os.environ["SEED_IMAGE_BASE_URL"] = ""

import pytest  # noqa: E402

from app.agents import orchestrator  # noqa: E402
from app.core import db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    for name in ("_items", "_requests", "_listings", "_drafts"):
        monkeypatch.setattr(db, name, {})
    for name in ("_matches", "_events"):
        monkeypatch.setattr(db, name, [])
    monkeypatch.setattr(orchestrator, "_seeded", [])
    monkeypatch.setattr(orchestrator, "_listing_now", set())
