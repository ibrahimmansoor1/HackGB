"""Every test starts with an empty in-memory DB (ids keep counting up).
Tests never touch Tiger, Gemini, or Modal, even if .env configures them; test_tiger.py
covers the Postgres backend against TEST_DATABASE_URL."""
import os

# Before app imports; load_dotenv won't override variables that are already set.
os.environ["DATABASE_URL"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["MODAL_ENDPOINT_URL"] = ""     # stub mode; tests fake model calls explicitly
os.environ["EBAY_APP_ID"] = os.environ["EBAY_CERT_ID"] = ""
os.environ["SEED_IMAGE_BASE_URL"] = ""
os.environ["BRAVE_API_KEY"] = ""

import pytest  # noqa: E402

from app.agents import orchestrator  # noqa: E402
from app.core import db  # noqa: E402


@pytest.fixture
def modal_mode(monkeypatch):
    """Act as if Modal is configured (tests fake the model calls), but keep
    the photo parser on its offline stub so drafts parse without a network."""
    from app.agents import parser
    from app.core import config
    monkeypatch.setattr(config, "USE_STUBS", False)

    async def offline_parse(text, images=None):
        return parser._stub(text, bool(images))
    monkeypatch.setattr(parser, "parse_item", offline_parse)


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    for name in ("_items", "_requests", "_listings", "_drafts"):
        monkeypatch.setattr(db, name, {})
    for name in ("_matches", "_events"):
        monkeypatch.setattr(db, name, [])
    monkeypatch.setattr(orchestrator, "_seeded", [])
    monkeypatch.setattr(orchestrator, "_listing_now", set())
