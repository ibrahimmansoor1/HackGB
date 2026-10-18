"""Rehome's text model on Modal: an OpenAI-compatible vLLM server with tool calling.

Serves the concierge agent (tool calling), the requester, pricing, and
match-reason agents. Adapted from Modal's official example
(https://modal.com/docs/examples/vllm_inference); same model, pins, and flags.

    pip install modal && modal setup     # once
    modal deploy infra/modal_llm.py      # prints the server URL
    modal run infra/modal_llm.py         # optional: health check + a tool-calling request

Then in .env:
    MODAL_ENDPOINT_URL=<printed URL>/v1
    MODAL_VISION_MODEL=llm
    MODAL_AGENT_MODEL=llm

Cost: one H200 while it's up; it scales to zero after SCALEDOWN minutes idle.
To use a smaller GPU, swap MODEL_NAME for a smaller tool-calling model and its
vLLM --tool-call-parser (e.g. Qwen3 + "hermes").
"""
import json

import modal

MODEL_NAME = "google/gemma-4-26B-A4B-it"
MODEL_REVISION = "47b6801b24d15ff9bcd8c96dfaea0be9ed3a0301"   # avoid surprise repo updates
SPECULATIVE_MODEL_NAME = "google/gemma-4-26B-A4B-it-assistant"
SPECULATIVE_MODEL_REVISION = "f188f476dc11dd5bb3014dc861529d316bce49d3"
SERVED_NAME = "llm"            # what MODAL_VISION_MODEL / MODAL_AGENT_MODEL point at
VLLM_PORT = 8000
MINUTES = 60
SCALEDOWN = 15                 # minutes idle before the GPU shuts down
FAST_BOOT = True               # skip torch compile: faster cold starts for a demo

vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.21.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

app = modal.App("rehome-llm")


@app.server(
    image=vllm_image,
    gpu="H200:1",
    scaledown_window=SCALEDOWN * MINUTES,
    startup_timeout=10 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache_vol, "/root/.cache/vllm": vllm_cache_vol},
    port=VLLM_PORT,
    routing_region="us-east",
    target_concurrency=32,
    unauthenticated=True,      # demo only: anyone with the URL can call it
)
class Server:
    @modal.enter()
    def start(self):
        import subprocess

        cmd = [
            "vllm", "serve", MODEL_NAME, "--revision", MODEL_REVISION,
            "--served-model-name", MODEL_NAME, SERVED_NAME,
            "--host", "0.0.0.0", "--port", str(VLLM_PORT),
            "--uvicorn-log-level=info", "--async-scheduling",
            "--enforce-eager" if FAST_BOOT else "--no-enforce-eager",
            "--limit-mm-per-prompt", json.dumps({"image": 0, "video": 0, "audio": 0}),
            # tool calling: what the concierge agent needs
            "--enable-auto-tool-choice", "--tool-call-parser", "gemma4",
            "--reasoning-parser", "gemma4",
            "--speculative-config", json.dumps({"model": SPECULATIVE_MODEL_NAME,
                                                "revision": SPECULATIVE_MODEL_REVISION,
                                                "num_speculative_tokens": 4}),
        ]
        print(*cmd)
        self.process = subprocess.Popen(cmd)

    @modal.exit()
    def stop(self):
        self.process.terminate()


@app.local_entrypoint()
async def test(timeout_s: int = 15 * MINUTES):
    """Wait for the server, then check it answers with a tool call."""
    import asyncio
    import time

    import aiohttp

    url = await Server.get_url.aio()
    print(f"Server URL: {url}\nSet MODAL_ENDPOINT_URL={url}/v1")
    async with aiohttp.ClientSession(base_url=url) as session:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            async with session.get("/health", timeout=aiohttp.ClientTimeout(total=60)) as r:
                if r.status == 200:
                    break
            await asyncio.sleep(2)
        else:
            raise SystemExit("Server never became healthy")
        payload = {
            "model": SERVED_NAME,
            "messages": [{"role": "user", "content": "What is a used winter coat worth?"}],
            "tools": [{"type": "function", "function": {
                "name": "get_price_quote", "description": "Price the donor's item.",
                "parameters": {"type": "object", "properties": {}}}}],
        }
        async with session.post("/v1/chat/completions", json=payload) as r:
            body = await r.json()
    calls = body["choices"][0]["message"].get("tool_calls")
    print("Tool call returned:" if calls else "No tool call (check the parser flags):",
          json.dumps(calls or body["choices"][0]["message"], indent=2))
