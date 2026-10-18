"""Rehome's model on Modal: GLM-5.3-Flash behind an OpenAI-compatible vLLM server.

One model serves every Modal agent: the concierge (tool calling), requester,
pricing, match reasons, and, until a GEMINI_API_KEY is set, the photo parser
(GLM-5.3-Flash reads images). Server shape follows Modal's vLLM example
(https://modal.com/docs/examples/vllm_inference); flags follow vLLM's
GLM-5.3-Flash recipe (https://recipes.vllm.ai/zai-org/GLM-5.3-Flash).

    pip install modal && modal setup     # once
    modal deploy infra/modal_llm.py      # prints the server URL
    modal run infra/modal_llm.py         # waits for it, checks a tool call + an image

Then in .env:
    MODAL_ENDPOINT_URL=<printed URL>/v1
    MODAL_VISION_MODEL=llm
    MODAL_AGENT_MODEL=llm

Cost: 4x H200 while a replica is up; it scales to zero after SCALEDOWN minutes
idle. The first boot downloads ~306 GiB of FP8 weights into a Modal Volume;
later boots load them from there.
"""
import json

import modal

MODEL_NAME = "zai-org/GLM-5.3-Flash"   # 320B MoE, 18B active, native FP8, multimodal
SERVED_NAME = "llm"                    # what MODAL_VISION_MODEL / MODAL_AGENT_MODEL point at
N_GPU = 4                              # recipe-validated on 4x H200 (TP=4)
VLLM_PORT = 8000
MAX_MODEL_LEN = 32768                  # our prompts are short; keeps KV cache and boot small
MINUTES = 60
SCALEDOWN = 15                         # minutes idle before the GPUs shut down

# The recipe says to use vLLM's nightly image until GLM-5.3-Flash support is in
# a pip release (vLLM 0.29.0+). Swap to a pinned tag once one is out.
vllm_image = (
    modal.Image.from_registry("vllm/vllm-openai:nightly")
    .entrypoint([])
    .env({"HF_XET_HIGH_PERFORMANCE": "1", "VLLM_ENGINE_READY_TIMEOUT_S": "3600"})
)
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

app = modal.App("rehome-llm")


@app.server(
    image=vllm_image,
    gpu=f"H200:{N_GPU}",
    scaledown_window=SCALEDOWN * MINUTES,
    startup_timeout=60 * MINUTES,      # first boot includes the weight download
    volumes={"/root/.cache/huggingface": hf_cache_vol, "/root/.cache/vllm": vllm_cache_vol},
    port=VLLM_PORT,
    routing_region="us-east",
    target_concurrency=16,
    unauthenticated=True,              # demo only: anyone with the URL can call it
)
class Server:
    @modal.enter()
    def start(self):
        import subprocess

        cmd = [
            "vllm", "serve", MODEL_NAME,
            "--served-model-name", MODEL_NAME, SERVED_NAME,
            "--host", "0.0.0.0", "--port", str(VLLM_PORT),
            "--tensor-parallel-size", str(N_GPU),
            "--max-model-len", str(MAX_MODEL_LEN),
            "--no-enable-flashinfer-autotune",   # faster boot (from the recipe)
            "--enforce-eager",                   # skip CUDA graph capture: faster cold starts
            # tool calling + reasoning: what the concierge agent needs
            "--enable-auto-tool-choice", "--tool-call-parser", "glm47",
            "--reasoning-parser", "glm47",
            "--limit-mm-per-prompt", json.dumps({"image": 4, "video": 0}),
        ]
        print(*cmd)
        self.process = subprocess.Popen(cmd)

    @modal.exit()
    def stop(self):
        self.process.terminate()


@app.local_entrypoint()
async def test(timeout_s: int = 60 * MINUTES):
    """Wait for the server, then check a tool call and an image both work."""
    import asyncio
    import time

    import aiohttp

    url = await Server.get_url.aio()
    print(f"Server URL: {url}\nSet MODAL_ENDPOINT_URL={url}/v1")
    low = {"chat_template_kwargs": {"reasoning_effort": "low"}}
    async with aiohttp.ClientSession(base_url=url) as session:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                async with session.get("/health", timeout=aiohttp.ClientTimeout(total=60)) as r:
                    if r.status == 200:
                        break
            except aiohttp.ClientError:
                pass
            print("waiting for the server (first boot downloads the weights)...")
            await asyncio.sleep(15)
        else:
            raise SystemExit("Server never became healthy")

        tool_req = {"model": SERVED_NAME, "max_tokens": 1024, **low,
                    "messages": [{"role": "user", "content": "Price my used winter coat."}],
                    "tools": [{"type": "function", "function": {
                        "name": "get_price_quote", "description": "Price the donor's item.",
                        "parameters": {"type": "object", "properties": {}}}}]}
        async with session.post("/v1/chat/completions", json=tool_req) as r:
            msg = (await r.json())["choices"][0]["message"]
        print("Tool call:" if msg.get("tool_calls") else "NO tool call (check parser flags):",
              json.dumps(msg.get("tool_calls") or msg, indent=2))

        image_req = {"model": SERVED_NAME, "max_tokens": 1024, **low, "messages": [{
            "role": "user", "content": [
                {"type": "image_url", "image_url": {
                    "url": "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png"}},
                {"type": "text", "text": "In one sentence, what is in this image?"}]}]}
        async with session.post("/v1/chat/completions", json=image_req) as r:
            print("Image:", (await r.json())["choices"][0]["message"].get("content"))
