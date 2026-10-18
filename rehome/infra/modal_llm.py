"""Rehome's model on Modal: Qwen3-VL-8B-Instruct behind an OpenAI-compatible vLLM server.

One model serves every Modal agent: the concierge (tool calling), requester,
pricing, match reasons, and, until a GEMINI_API_KEY is set, the photo parser
(Qwen3-VL reads images). Based on Modal's vLLM example
(https://modal.com/docs/examples/vllm_inference).

    pip install modal && modal setup                 # once
    modal deploy infra/modal_llm.py                  # prints the URL (…modal.run)
    python infra/check_llm.py <URL>                  # warms it up, checks tools + images

Then in .env:
    MODAL_ENDPOINT_URL=<URL>/v1
    MODAL_VISION_MODEL=llm
    MODAL_AGENT_MODEL=llm
    MODAL_REASONING_EFFORT=          # blank: Qwen3-VL Instruct doesn't use it

Cost: one L40S (~$1.95/hour) while a container is up; it scales to zero after
SCALEDOWN minutes idle. The first boot downloads ~17 GB of weights into a
Modal Volume; later boots load them from there. (We started on GLM-5.3-Flash:
4x H200, ~$18/hour, a 306 GB download. This is ~9x cheaper for the same jobs.)
"""
import json
import subprocess

import modal

MODEL_NAME = "Qwen/Qwen3-VL-8B-Instruct"   # 8B, vision + tool calling
MODEL_REVISION = "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"   # pin: no surprise repo updates
SERVED_NAME = "llm"                        # what MODAL_VISION_MODEL / MODAL_AGENT_MODEL point at
GPU = "L40S"                               # 48 GB: weights (~17 GB) + KV cache fit on one
VLLM_PORT = 8000
MAX_MODEL_LEN = 32768                      # our prompts are short; keeps KV cache and boot small
MINUTES = 60
SCALEDOWN = 10                             # minutes idle before the GPU shuts down

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
    gpu=GPU,
    scaledown_window=SCALEDOWN * MINUTES,
    timeout=24 * 60 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache_vol, "/root/.cache/vllm": vllm_cache_vol},
)
@modal.concurrent(max_inputs=32)
@modal.web_server(port=VLLM_PORT, startup_timeout=30 * MINUTES)  # first boot downloads weights
def serve():
    cmd = [
        "vllm", "serve", MODEL_NAME, "--revision", MODEL_REVISION,
        "--served-model-name", MODEL_NAME, SERVED_NAME,
        "--host", "0.0.0.0", "--port", str(VLLM_PORT),
        "--max-model-len", str(MAX_MODEL_LEN),
        "--enforce-eager",                   # skip CUDA graph capture: faster cold starts
        # tool calling: what the concierge agent needs (Qwen3 uses the hermes format)
        "--enable-auto-tool-choice", "--tool-call-parser", "hermes",
        "--limit-mm-per-prompt", json.dumps({"image": 4, "video": 0}),
    ]
    print(*cmd)
    subprocess.Popen(cmd)
