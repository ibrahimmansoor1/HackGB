"""Input parser on Gemini (docs/05), with the HTTP call faked."""
import asyncio

import pytest
from pydantic import ValidationError

from app.agents import parser, stub_rules
from app.core import config, llm

GOOD = {"category": "outerwear", "item": "puffer jacket", "brand": "Columbia", "color": "black",
        "size": "M", "condition": "like new", "season": "winter",
        "attributes": ["insulated", "hooded"], "summary": "Black Columbia puffer, size M."}


@pytest.fixture
def gemini(monkeypatch):
    """Pretend GEMINI_API_KEY is set; replies come from the returned list."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    calls, replies = [], []

    async def fake(system, user, images):
        calls.append((system, user, images))
        return replies.pop(0)
    monkeypatch.setattr(llm, "gemini_json", fake)
    return calls, replies


def test_gemini_reply_becomes_parsed_item_with_brand(gemini):
    calls, replies = gemini
    replies.append(GOOD)
    out = asyncio.run(parser.parse_item("barely worn", [(b"img", "image/png"), (b"", "image/png")]))
    assert out.brand == "Columbia" and out.size == "M"
    system, user, images = calls[0]
    assert images == [(b"img", "image/png")]          # empty uploads dropped
    assert "barely worn" in user
    assert all(a in system for a in stub_rules.ATTRIBUTE_VOCAB)


def test_bad_reply_is_retried_once(gemini):
    calls, replies = gemini
    replies.extend([{"category": "spaceship"}, GOOD])
    assert asyncio.run(parser.parse_item("coat")).item == "puffer jacket"
    assert len(calls) == 2


def test_two_bad_replies_raise(gemini):
    _, replies = gemini
    replies.extend([{"item": "x"}, {"item": "y"}])
    with pytest.raises(ValidationError):
        asyncio.run(parser.parse_item("coat"))


def test_no_key_uses_stub_and_brand_is_null(monkeypatch):
    async def boom(*a):
        raise AssertionError("no key: Gemini must not be called")
    monkeypatch.setattr(llm, "gemini_json", boom)
    out = asyncio.run(parser.parse_item("Black puffer jacket, size M"))
    assert out.item == "puffer jacket" and out.brand is None
