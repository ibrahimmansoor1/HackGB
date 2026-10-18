"""Settings loaded from the repo-root .env. Never hardcode keys elsewhere."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "modal")
MODAL_ENDPOINT_URL = os.getenv("MODAL_ENDPOINT_URL", "")
MODAL_API_KEY = os.getenv("MODAL_API_KEY", "")
MODAL_VISION_MODEL = os.getenv("MODAL_VISION_MODEL", "")
MODAL_EMBED_MODEL = os.getenv("MODAL_EMBED_MODEL", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.70"))
TOP_K = int(os.getenv("TOP_K", "3"))

# True when no model endpoint is configured: agents return stub data so the
# frontend can be built before the model is wired up.
USE_STUBS = not MODAL_ENDPOINT_URL or "your-workspace" in MODAL_ENDPOINT_URL

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
