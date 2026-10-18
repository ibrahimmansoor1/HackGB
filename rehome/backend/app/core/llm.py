"""Model client. Everything that calls an LLM or embedding model goes
through here, so switching Modal <-> Gemini is a one-file change.

Modal (requester, pricing, reasons, embeddings) is assumed OpenAI-compatible
(vLLM-style /chat/completions and /embeddings); adjust if your deployment
differs. Gemini (input parser) uses the generateContent REST API.
"""
import base64
import hashlib
import json
import re
import httpx
import numpy as np
from app.core import config

EMBED_DIM = config.EMBED_DIM


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.MODAL_API_KEY}"} if config.MODAL_API_KEY else {}


def _strip_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()


async def complete_json(system: str, user_text: str,
                        image_bytes: bytes | None = None,
                        image_mime: str = "image/jpeg") -> dict | list:
    """Call the model and parse its JSON reply."""
    content: list[dict] = [{"type": "text", "text": user_text}]
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode()
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:{image_mime};base64,{b64}"}})
    payload = {
        "model": config.MODAL_VISION_MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": content}],
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{config.MODAL_ENDPOINT_URL}/chat/completions",
                              json=payload, headers=_headers())
        r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return json.loads(_strip_fences(text))


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


async def gemini_json(system: str, user_text: str,
                      images: list[tuple[bytes, str]] | None = None) -> dict | list:
    """Call Gemini with text + (bytes, mime) images and parse its JSON reply."""
    parts: list[dict] = [{"text": user_text}]
    for data, mime in images or []:
        parts.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}})
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(GEMINI_URL.format(model=config.GEMINI_MODEL), json=payload,
                              headers={"x-goog-api-key": config.GEMINI_API_KEY})
        r.raise_for_status()
    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:   # blocked by safety filters, or empty
        raise ValueError(f"Gemini returned no text: {r.text[:200]}") from e
    return json.loads(_strip_fences(text))


def stub_embeddings() -> bool:
    """True when embeddings are the hashed bag of words (no Modal embed model),
    even if the Modal text model is configured."""
    return config.USE_STUBS or not config.MODAL_EMBED_MODEL


async def embed(text: str) -> list[float]:
    """Embedding vector for similarity search."""
    if stub_embeddings():
        return _stub_embed(text)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{config.MODAL_ENDPOINT_URL}/embeddings",
                              json={"model": config.MODAL_EMBED_MODEL, "input": text},
                              headers=_headers())
        r.raise_for_status()
    return r.json()["data"][0]["embedding"]


# Stub only: fold common synonyms together so "pots and pans" finds cookware
# and "coat" finds a parka. Real embeddings don't need this.
_SYNONYMS = {"pot": "cookware", "pan": "cookware", "skillet": "cookware",
             "jacket": "coat", "parka": "coat", "peacoat": "coat", "puffer": "coat",
             "sneaker": "shoe", "trainer": "shoe", "hat": "beanie", "toque": "beanie",
             "trouser": "pant", "jean": "pant", "comforter": "blanket", "throw": "blanket"}


def _stub_token(word: str) -> str:
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return _SYNONYMS.get(word, word)


def _stub_embed(text: str) -> list[float]:
    """Bag-of-words hashing so stub matching is roughly sensible offline."""
    v = np.zeros(EMBED_DIM)
    for word in re.findall(r"[a-z]+", text.lower()):
        word = _stub_token(word)
        v[int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBED_DIM] += 1
    n = np.linalg.norm(v)
    return (v / n if n else v).tolist()
