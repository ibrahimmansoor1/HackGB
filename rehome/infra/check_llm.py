"""Warm up the deployed Modal model and check it does what the agents need.

    python infra/check_llm.py https://<workspace>--rehome-llm-server.us-east.modal.direct

Waits for /health (a cold first boot can take a while), then checks a tool call
and an image round-trip. Unlike `modal run`, this uses the deployed app, so no
second GPU replica starts.
"""
import json
import sys
import time

import httpx

TOOLS = [{"type": "function", "function": {
    "name": "get_price_quote", "description": "Price the donor's item.",
    "parameters": {"type": "object", "properties": {}}}}]
LOW = {"chat_template_kwargs": {"reasoning_effort": "low"}}
IMAGE = "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png"


def main(url: str, timeout_s: int = 3600) -> None:
    url = url.rstrip("/").removesuffix("/v1")
    start = time.time()
    with httpx.Client(base_url=url, timeout=300) as c:
        while True:
            try:
                if c.get("/health", timeout=60).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.time() - start > timeout_s:
                sys.exit("Server never became healthy")
            print(f"waiting for the server... {int(time.time() - start)}s", flush=True)
            time.sleep(15)
        print(f"healthy after {int(time.time() - start)}s")

        t = time.time()
        msg = c.post("/v1/chat/completions", json={
            "model": "llm", "max_tokens": 1024, "tools": TOOLS, **LOW,
            "messages": [{"role": "user", "content": "Price my used winter coat."}]}
        ).json()["choices"][0]["message"]
        ok = bool(msg.get("tool_calls"))
        print(f"tool call: {'OK' if ok else 'MISSING'} ({time.time() - t:.1f}s)",
              json.dumps(msg.get("tool_calls") or msg)[:400])

        t = time.time()
        reply = c.post("/v1/chat/completions", json={
            "model": "llm", "max_tokens": 1024, **LOW, "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": IMAGE}},
                {"type": "text", "text": "In one sentence, what is in this image?"}]}]}
        ).json()["choices"][0]["message"].get("content")
        print(f"image: ({time.time() - t:.1f}s) {reply}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1])
