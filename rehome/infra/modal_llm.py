"""Rehome's model on Modal: GLM-5.3-Flash behind an OpenAI-compatible vLLM server.

One model serves every Modal agent: the concierge (tool calling), requester,
pricing, match reasons, and, until a GEMINI_API_KEY is set, the photo parser
(GLM-5.3-Flash reads images). Based on Modal's vLLM example
(https://modal.com/docs/examples/vllm_inference); flags follow vLLM's
GLM-5.3-Flash recipe (https://recipes.vllm.ai/zai-org/GLM-5.3-Flash).

    pip install modal && modal setup                 # once
    modal deploy infra/modal_llm.py                  # prints the URL (…modal.run)
    python infra/check_llm.py <URL>                  # warms it up, checks tools + images

Then in .env:
    MODAL_ENDPOINT_URL=<URL>/v1
    MODAL_VISION_MODEL=llm
    MODAL_AGENT_MODEL=llm

Cost: 4x H200 while a container is up; it scales to zero after SCALEDOWN
minutes idle. The first boot downloads ~306 GiB of FP8 weights into a Modal
Volume; later boots load them from there.
"""
import json
import subprocess

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
    # add_python: Modal can't detect the image's own Python; vLLM keeps using its
    # install (the `vllm` CLI below), Modal's runtime uses the added one.
    modal.Image.from_registry("vllm/vllm-openai:nightly", add_python="3.12")
    .entrypoint([])
    .env({"HF_XET_HIGH_PERFORMANCE": "1", "VLLM_ENGINE_READY_TIMEOUT_S": "3600"})
)
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

app = modal.App("rehome-llm")


# A web function (URL on *.modal.run) rather than @app.server (*.modal.direct):
# some campus networks block modal.direct, and web functions queue requests
# during a cold start instead of answering 503.
@app.function(
    image=vllm_image,
    gpu=f"H200:{N_GPU}",
    scaledown_window=SCALEDOWN * MINUTES,
    timeout=24 * 60 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache_vol, "/root/.cache/vllm": vllm_cache_vol},
)
@modal.concurrent(max_inputs=32)
@modal.web_server(port=VLLM_PORT, startup_timeout=60 * MINUTES)  # first boot downloads weights
def serve():
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
    subprocess.Popen(cmd)
