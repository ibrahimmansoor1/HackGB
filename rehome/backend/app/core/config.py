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
# Tiger Data (Postgres) connection string. Blank = in-memory stub DB.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
# Vector size of the embedding model; the items/requests columns are created
# with it (scripts/init_db.py). Changing it means re-running init_db --reset.
EMBED_DIM = int(os.getenv("EMBED_DIM", "384"))
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.70"))
TOP_K = int(os.getenv("TOP_K", "3"))

# True when no model endpoint is configured: agents return stub data so the
# frontend can be built before the model is wired up.
USE_STUBS = not MODAL_ENDPOINT_URL or "your-workspace" in MODAL_ENDPOINT_URL

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Where this backend is reachable from outside, so photo URLs are absolute
# (frontend on another laptop, Nostr image tags). For a public tunnel, set it
# to the tunnel URL, e.g. https://rehome-demo.ngrok.app
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").strip().rstrip("/")


def public_url(path: str) -> str:
    """'/static/uploads/x.jpg' -> 'http://localhost:8000/static/uploads/x.jpg'."""
    return f"{PUBLIC_BASE_URL}/{path.lstrip('/')}"


# Browser origins allowed to call the API (SvelteKit dev + preview by default).
CORS_ORIGINS = [o.strip().rstrip("/") for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"
).split(",") if o.strip()]

# Marketplace: Nostr classified listings (NIP-99), shown on Shopstr.
# Posts go live only when NOSTR_NSEC is set AND MARKETPLACE_DRY_RUN=false.
NOSTR_NSEC = os.getenv("NOSTR_NSEC", "").strip()
NOSTR_RELAYS = [r.strip() for r in os.getenv(
    "NOSTR_RELAYS", "wss://relay.damus.io,wss://nos.lol,wss://relay.primal.net").split(",")
    if r.strip()]
MARKETPLACE_DRY_RUN = os.getenv("MARKETPLACE_DRY_RUN", "true").strip().lower() not in (
    "false", "0", "no", "off")
LISTING_LOCATION = os.getenv("LISTING_LOCATION", "").strip()
