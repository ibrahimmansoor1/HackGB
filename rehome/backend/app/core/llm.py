"""Model client. Everything that calls an LLM or embedding model goes
through here, so switching Modal <-> Gemini is a one-file change.

Assumes the Modal endpoint is OpenAI-compatible (vLLM-style /chat/completions
and /embeddings). Adjust if your deployment differs.
"""
import base64
import hashlib
import json
import re
import httpx
import numpy as np
from app.core import config

EMBED_DIM = 384


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


async def embed(text: str) -> list[float]:
    """Embedding vector for similarity search."""
    if config.USE_STUBS or not config.MODAL_EMBED_MODEL:
        return _stub_embed(text)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{config.MODAL_ENDPOINT_URL}/embeddings",
                              json={"model": config.MODAL_EMBED_MODEL, "input": text},
                              headers=_headers())
        r.raise_for_status()
    return r.json()["data"][0]["embedding"]


def _stub_embed(text: str) -> list[float]:
    """Bag-of-words hashing so stub matching is roughly sensible offline."""
    v = np.zeros(EMBED_DIM)
    for word in re.findall(r"[a-z]+", text.lower()):
        v[int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBED_DIM] += 1
    n = np.linalg.norm(v)
    return (v / n if n else v).tolist()
